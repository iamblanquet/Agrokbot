"""ERP transport, catalog synchronization and responsible normalization."""
import json
import urllib.parse
import urllib.request
import urllib.error
import secrets

from backend.http_client import RemoteFailure


def task_responsible(task):
    value = task.get("responsible") if isinstance(task, dict) else None
    if not isinstance(value, dict):
        return {"assignmentId": "", "employeeNumber": "", "name": (task.get("responsibleName", "") if isinstance(task, dict) else "")}
    return {"assignmentId": str(value.get("assignmentId") or ""), "employeeNumber": str(value.get("employeeNumber") or ""), "name": str(value.get("fullName") or task.get("responsibleName") or "")}


class ErpClient:
    def __init__(self, remote, connection, lock, employees, now, settings):
        self.remote = remote
        self.connection = connection
        self.lock = lock
        self.employees = employees
        self.now = now
        self.settings = settings

    def request(self, path, payload=None):
        settings = self.settings()
        url = settings["url"]
        if not ((url.startswith("https://") or (url.startswith("http://") and settings["allow_http"])) and settings["key"]):
            raise RemoteFailure("Configura ERP_API_URL con HTTPS y ERP_API_KEY en el servidor.")
        return self.remote(url + path, payload, {"Authorization": f"Bearer {settings['key']}"})

    def catalog(self, refresh=True):
        settings = self.settings()
        with self.lock:
            if settings["mode"] == "live" and refresh:
                try:
                    projects = self.request("/external/projects")["projects"]
                    tasks = []
                    try:
                        all_tasks = self.request("/external/project-tasks").get("tasks", [])
                    except Exception:
                        all_tasks = []
                    if all_tasks:
                        tasks = all_tasks
                    else:
                        for project in projects:
                            tasks.extend(self.request("/external/project-tasks?" + urllib.parse.urlencode({"projectId": project["id"]}))["tasks"])
                    with self.connection() as db:
                        db.execute("DELETE FROM catalog")
                        for kind, items in (("project", projects), ("task", tasks)):
                            for item in items:
                                db.execute("INSERT INTO catalog VALUES (?,?,?)", (kind, item["id"], json.dumps(item)))
                except (RemoteFailure, KeyError, TypeError) as error:
                    raise RemoteFailure(getattr(error, "message", "Formato inesperado de la API ERP.")) from None
            with self.connection() as db:
                rows = db.execute("SELECT kind,payload FROM catalog").fetchall()
            return {"projects": [json.loads(row[1]) for row in rows if row[0] == "project"], "tasks": [json.loads(row[1]) for row in rows if row[0] == "task"], "employees": self.employees(), "fetchedAt": self.now()}

    def upload_attachment(self, log_id, photo):
        settings = self.settings()
        url = settings['url']
        if not settings['key'] or not (url.startswith('https://') or (url.startswith('http://') and settings['allow_http'])):
            raise RemoteFailure('Configura ERP_API_URL y ERP_API_KEY.')
        boundary = 'Campo' + secrets.token_hex(16)
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{photo["id"]}.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
                + photo['data'] + f'\r\n--{boundary}--\r\n'.encode())
        request = urllib.request.Request(url + '/external/project-operation-logs/' + urllib.parse.quote(log_id, safe='') + '/attachments', data=body,
            headers={'Authorization': 'Bearer ' + settings['key'], 'Content-Type': 'multipart/form-data; boundary=' + boundary})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                if response.status != 201:
                    raise RemoteFailure('Respuesta inesperada al guardar evidencia.', True)
                attachments = json.load(response)['attachments']
            if len(attachments) != 1 or not attachments[0].get('id') or attachments[0].get('operationLogId') != log_id:
                raise RemoteFailure('Referencia de evidencia inesperada.', True)
            return attachments[0]['id']
        except urllib.error.HTTPError as error:
            raise RemoteFailure(f'ERP evidencias respondió HTTP {error.code}.', error.code >= 500) from None
        except (OSError, ValueError, KeyError, TypeError):
            raise RemoteFailure('No se pudo confirmar la carga de evidencia.', True) from None

    def attachments(self, project_id, log_id):
        project = self.request('/external/projects/' + urllib.parse.quote(project_id, safe=''))['project']
        return [attachment for activity in project.get('activities', []) for task in activity.get('tasks', [])
                for log in task.get('operationLogs', []) if log.get('id') == log_id for attachment in log.get('attachments', [])]

    def attachment_file(self, attachment_id):
        settings = self.settings()
        url = settings['url']
        if not settings['key'] or not (url.startswith('https://') or (url.startswith('http://') and settings['allow_http'])):
            raise RemoteFailure('Configura ERP_API_URL y ERP_API_KEY.')
        # Original JPEG preserves the content type served by the local route.
        request = urllib.request.Request(url + '/external/reference-attachments/' + urllib.parse.quote(attachment_id, safe='') + '/file',
            headers={'Authorization': 'Bearer ' + settings['key']})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(15000001)
            if len(data) > 15000000 or not data.startswith(b'\xff\xd8\xff'):
                raise RemoteFailure('Archivo de evidencia inválido.')
            return data
        except (OSError, ValueError):
            raise RemoteFailure('No fue posible consultar la fotografía en el ERP.') from None

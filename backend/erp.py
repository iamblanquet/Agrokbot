"""ERP transport, catalog synchronization and responsible normalization."""
import json
import urllib.parse

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

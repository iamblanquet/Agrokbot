"""Read-only ERP journal. No local persistence or external writes."""
import urllib.parse
import re


def presentation(log, metadata, field):
    """Only unwrap our complete generated envelope; preserve unknown notes verbatim."""
    notes = log.get('notes') or ''
    match = re.fullmatch(
        r'(?:📅\s*)?Fecha Operativa: [^\n]+\n(?:⏰\s*)?Hora Captura [^\n]+\n'
        r'(?P<body>.*?)\n\nTarea: [^\n]+\nAvance acumulado: [^\n]+\n'
        r'Capturado: (?P<captured>[^\n]+)\n\n(?P<notes>.*?)\n\nRef: (?P<reference>[^\n]+)',
        notes, re.DOTALL)
    result = {'observations': notes, 'parsed': False, 'resources': []}
    if not match:
        return result
    # Keep every header line available, including legacy fields absent from metadata.
    connection = re.search(r'^(?:⏰\s*)?Hora Captura \(([^\n)]+)\):', notes, re.MULTILINE)
    resources = ([{'label': 'Conectividad al capturar', 'value': connection[1]}]
                 if connection else [])
    for line in match['body'].splitlines():
        clean = line.strip().lstrip('👤📊👥🚜☂• ').strip()
        key, separator, value = clean.partition(':')
        if separator:
            if key in ('Responsable', 'Autor'):
                result['reportedBy'] = value.strip()
            else:
                k = key.strip()
                v = value.strip()
                crew_m = re.match(r'^Cuadrilla\s*\(([^)]+)\)$', k, re.IGNORECASE)
                if crew_m and (not v or v.lower() == 'sin detalle'):
                    k = 'Cuadrilla'
                    v = crew_m.group(1).strip()
                resources.append({'label': k, 'value': v})
        elif clean:
            resources.append({'label': 'Información adicional', 'value': clean})
    result.update(observations=match['notes'], parsed=True, resources=resources,
                  capturedAt=field.get('capturedAt') or match['captured'],
                  clientReference=metadata.get('clientReportId') or match['reference'])
    return result


class JournalService:
    def __init__(self, erp):
        self.erp = erp

    def projects(self):
        projects = self.erp.request('/external/projects')['projects']
        return {'projects': [{k: p.get(k) for k in ('id', 'folio', 'code', 'name')} for p in projects]}

    def entries(self, project_id):
        if not project_id or len(project_id) > 200:
            raise ValueError('Selecciona un proyecto válido.')
        project = self.erp.request('/external/projects/' + urllib.parse.quote(project_id, safe=''))['project']
        entries = []
        for activity in project.get('activities', []):
            for task in activity.get('tasks', []):
                for log in task.get('operationLogs', []):
                    metadata = log.get('metadataJson')
                    metadata = metadata if isinstance(metadata, dict) else {}
                    field = metadata.get('fieldReport')
                    field = field if isinstance(field, dict) else {}
                    attachments = [{k: a.get(k) for k in ('id', 'originalFileName', 'mimeType', 'sizeBytes', 'uploadedAt')} for a in log.get('attachments', [])]
                    entries.append({
                        'id': log['id'], 'operationDate': log.get('operationDate'),
                        'createdAt': log.get('createdAt'), 'source': log.get('source'),
                        'status': log.get('status'), 'progressBps': log.get('progressBps'),
                        'notes': log.get('notes') or '',
                        'presentation': presentation(log, metadata, field),
                        'author': log.get('reporterName') or field.get('author') or 'Sin autor informado',
                        'taskId': task['id'], 'taskName': task.get('name'), 'taskCode': task.get('code'),
                        'activityName': activity.get('name'), 'responsible': task.get('responsibleName') or '',
                        'attachments': attachments,
                    })
        entries.sort(key=lambda row: (row['operationDate'] or '', row['createdAt'] or '', row['id']), reverse=True)
        return {'project': {k: project.get(k) for k in ('id', 'folio', 'code', 'name')}, 'entries': entries}

    def attachment(self, project_id, log_id, attachment_id, preview=True):
        # Validate membership using the ERP on every access; no arbitrary file proxy.
        entries = self.entries(project_id)['entries']
        attachment = next((a for row in entries if row['id'] == log_id for a in row['attachments'] if a['id'] == attachment_id), None)
        if not attachment:
            raise LookupError('Evidencia no encontrada en este asiento.')
        return self.erp.reference_image(attachment_id, preview)

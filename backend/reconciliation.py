"""Conservative read-only ERP lookup; never reconstruct a missing diary entry."""
import json
import urllib.parse


def verified_log(erp, report, log_id):
    if not isinstance(log_id,str) or not 1<=len(log_id)<=200:
        raise ValueError('Indica el operationLog.id del ERP.')
    project=erp.request('/external/projects/'+urllib.parse.quote(report['project_id'],safe=''))['project']
    payload=json.loads(report['payload'])
    matches=[log for activity in project.get('activities',[]) for task in activity.get('tasks',[])
             if task.get('id')==report['task_id'] for log in task.get('operationLogs',[]) if log.get('id')==log_id]
    if len(matches)!=1:
        raise ValueError('El asiento no existe en la tarea y proyecto de este reporte.')
    log=matches[0]
    metadata=log.get('metadataJson') or {}
    if isinstance(metadata,str):
        try: metadata=json.loads(metadata)
        except ValueError: metadata={}
    reference=metadata.get('clientReportId') if isinstance(metadata,dict) else None
    if reference!=report['id']:
        raise ValueError('El asiento no acredita el clientReportId original. No se enlazará por similitud.')
    if (log.get('operationDate') or '')[:10]!=payload['operationDate'] or log.get('progressBps')!=payload['progressBps']:
        raise ValueError('La fecha o avance del asiento no coincide con el reporte original.')
    return log

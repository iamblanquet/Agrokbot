"""Durable project dossier publication. Never deletes topics, reports or photos."""
import hashlib
import json
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from backend.http_client import RemoteFailure
from backend.reminders import Reminders
from backend.project_pdf import render_dossier


class NotReady(ValueError):
    pass


def finished(project):
    progress = project.get('progressBps')
    return type(progress) in (int,float) and progress >= 10000 and project.get('status') not in ('CANCELLED','CANCELED')


class ProjectArchives:
    def __init__(self, connection, erp, telegram, document, chat_id, now, renderer=render_dossier):
        self.connection, self.erp, self.telegram = connection, erp, telegram
        self.document, self.chat_id, self.now, self.renderer = document, chat_id, now, renderer
        self.lock = threading.RLock()
        self.topic = Reminders(connection,None,telegram,chat_id,'completed_projects_topic','Proyectos finalizados')

    def initialize(self):
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS project_archives(project_id TEXT PRIMARY KEY,state TEXT NOT NULL,
                    snapshot TEXT,pdf BLOB,sha256 TEXT,source_hash TEXT,error TEXT,updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS project_archive_actions(project_id TEXT,step TEXT,state TEXT NOT NULL,
                    receipt TEXT,error TEXT,PRIMARY KEY(project_id,step));
            ''')
            db.execute("UPDATE project_archive_actions SET state='review',error='Interrupted' WHERE state='sending'")

    def listing(self):
        with self.connection() as db:
            rows = [dict(r) for r in db.execute('SELECT project_id,state,sha256,error,updated FROM project_archives ORDER BY updated DESC')]
            for row in rows:
                row['actions'] = [dict(r) for r in db.execute('SELECT step,state,receipt,error FROM project_archive_actions WHERE project_id=?',(row['project_id'],))]
            topic = db.execute("SELECT value FROM settings WHERE key='completed_projects_topic'").fetchone()
        return {'archives':rows,'topic':topic[0] if topic else None}

    def source(self, project_id):
        project = self.erp.request('/external/projects/'+quote(project_id,safe=''))['project']
        if project.get('id') != project_id or not finished(project):
            raise NotReady('El ERP no confirma el 100 % del proyecto completo.')
        if not isinstance(project.get('activities'),list):
            raise NotReady('El ERP omitió las actividades del proyecto.')
        tasks, logs, seen = [], [], set()
        for activity in project['activities']:
            if not isinstance(activity.get('tasks'),list):
                raise NotReady('El ERP omitió tareas.')
            for task in activity['tasks']:
                tasks.append({**task,'activityName':activity.get('name')})
                if not isinstance(task.get('operationLogs'),list):
                    raise NotReady('El ERP omitió el diario de una tarea.')
                for entry in task['operationLogs']:
                    if not isinstance(entry.get('attachments'),list):
                        raise NotReady('El ERP omitió el listado de evidencias.')
                    if entry['id'] not in seen:
                        seen.add(entry['id'])
                        logs.append({**entry,'taskId':task['id'],'taskName':task.get('name',task['id']),
                                     'attachments':[dict(a) for a in entry['attachments']]})
        logs_by_id = {item['id']:item for item in logs}
        with self.connection() as db:
            reports = [dict(r) for r in db.execute('SELECT * FROM reports WHERE project_id=? ORDER BY created,id',(project_id,))]
            for report in reports:
                if report['state'] != 'published' or report['erp_log_id'] not in seen:
                    raise NotReady('Hay reportes pendientes o no conciliados con el diario ERP.')
                payload = json.loads(report['payload'])
                if (payload.get('details') or {}).get('incident') and not db.execute('SELECT 1 FROM incidents WHERE id=?',(report['id'],)).fetchone():
                    raise NotReady('Hay incidencias pendientes de incorporar al seguimiento.')
                log = logs_by_id[report['erp_log_id']]
                log['local'] = {'id':report['id'],'user':report['user'],'created':report['created'],'payload':payload}
                attachments = {a['id'] for a in log['attachments']}
                for photo_id in payload.get('photos',[]):
                    photo=db.execute('SELECT id,attachment_id,upload_state,message_id FROM photos WHERE id=? AND report_id=?',(photo_id,report['id'])).fetchone()
                    if not photo or photo['upload_state'] != 'confirmed' or not photo['message_id'] or not photo['attachment_id']:
                        raise NotReady('Hay fotografías pendientes de confirmación.')
                    if photo['attachment_id'] not in attachments:
                        log['attachments'].append({'id':photo['attachment_id'] or photo_id,'localPhoto':photo_id,
                                                   'originalFileName':'Evidencia local '+photo_id})
            incidents=[dict(r) for r in db.execute('SELECT * FROM incidents WHERE project_id=? ORDER BY created,id',(project_id,))]
            for incident in incidents:
                incident['payload']=json.loads(incident['payload'])
                incident['events']=[dict(r) for r in db.execute('SELECT actor,status,note,created FROM incident_events WHERE incident_id=? ORDER BY created,id',(incident['id'],))]
            clarifications=[dict(r) for r in db.execute('SELECT c.* FROM clarifications c JOIN reports r ON r.id=c.report_id WHERE r.project_id=? ORDER BY c.created,c.id',(project_id,))]
            topic=db.execute('SELECT thread_id FROM topics WHERE project_id=?',(project_id,)).fetchone()
        # Consistent ordering even if ERP changes list order across requests.
        for item in logs:
            item['attachments'].sort(key=lambda a:str(a['id']))
        logs.sort(key=lambda x:(x.get('operationDate') or '',x.get('createdAt') or '',x['id']))
        tasks.sort(key=lambda x:x['id'])
        summary={k:v for k,v in project.items() if k != 'activities'}
        return {'project':summary,'tasks':[{k:v for k,v in t.items() if k!='operationLogs'} for t in tasks],
                'logs':logs,'incidents':incidents,'clarifications':clarifications,'originalTopic':topic[0] if topic else None}

    @staticmethod
    def digest(source):
        return hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def image(self, attachment):
        if attachment.get('localPhoto'):
            with self.connection() as db:
                row=db.execute('SELECT data FROM photos WHERE id=?',(attachment['localPhoto'],)).fetchone()
            if row and row[0]:
                return row[0]
        return self.erp.reference_image(attachment['id'],preview=False)[0]

    def status(self, project_id, state, error=None):
        with self.connection() as db:
            db.execute('UPDATE project_archives SET state=?,error=?,updated=? WHERE project_id=?',
                       (state,error,self.now(),project_id))

    def action(self, project_id, step, operation):
        with self.connection() as db:
            db.execute("DELETE FROM project_archive_actions WHERE project_id=? AND step=? AND state='retry'",(project_id,step))
            claimed=db.execute("INSERT OR IGNORE INTO project_archive_actions VALUES (?,?,'sending',NULL,NULL)",(project_id,step)).rowcount
            old=db.execute('SELECT state,receipt FROM project_archive_actions WHERE project_id=? AND step=?',(project_id,step)).fetchone()
        if not claimed:
            return json.loads(old['receipt']) if old['state']=='sent' else None
        try:
            receipt=operation()
            if step in ('document','summary') and (not isinstance(receipt,dict) or type(receipt.get('message_id')) is not int):
                raise RemoteFailure('Telegram no confirmó el identificador del mensaje.',True)
            if step in ('rename','close') and receipt is not True:
                raise RemoteFailure('Telegram no confirmó la operación.',True)
        except Exception as error:
            state='retry' if isinstance(error,RemoteFailure) and not error.ambiguous else 'review'
            with self.connection() as db:
                db.execute('UPDATE project_archive_actions SET state=?,error=? WHERE project_id=? AND step=?',(state,type(error).__name__,project_id,step))
            return None
        with self.connection() as db:
            db.execute("UPDATE project_archive_actions SET state='sent',receipt=?,error=NULL WHERE project_id=? AND step=?",(json.dumps(receipt),project_id,step))
        return receipt

    def process(self, project_id):
        with self.lock:
            with self.connection() as db:
                db.execute("INSERT OR IGNORE INTO project_archives(project_id,state,updated) VALUES (?,'waiting',?)",(project_id,self.now()))
                row=dict(db.execute('SELECT * FROM project_archives WHERE project_id=?',(project_id,)).fetchone())
            if row['state']=='closed':
                return
            try:
                source=self.source(project_id)
                fingerprint=self.digest(source)
                if row['pdf'] is not None and row['source_hash'] != fingerprint:
                    with self.connection() as db:
                        delivery=db.execute("SELECT state FROM project_archive_actions WHERE project_id=? AND step='document'",(project_id,)).fetchone()
                    # Rebuild only when no upload could have succeeded.
                    if delivery is None or delivery['state']=='retry':
                        row['pdf']=None
                if row['pdf'] is None:
                    snapshot={**source,'cutoff':datetime.now(ZoneInfo('America/Mexico_City')).isoformat()}
                    pdf,warnings=self.renderer(snapshot,self.image)
                    snapshot['imageWarnings']=warnings
                    sha=hashlib.sha256(pdf).hexdigest()
                    with self.connection() as db:
                        db.execute("UPDATE project_archives SET snapshot=?,pdf=?,sha256=?,source_hash=?,state='ready',error=NULL,updated=? WHERE project_id=?",
                                   (json.dumps(snapshot,ensure_ascii=False),pdf,sha,fingerprint,self.now(),project_id))
                    row.update(pdf=pdf,snapshot=json.dumps(snapshot),source_hash=fingerprint,sha256=sha)
                if row['source_hash'] != fingerprint:
                    self.status(project_id,'review','La información cambió después del corte. Revisar expediente; no se cerró el tema.')
                    return
                if hashlib.sha256(row['pdf']).hexdigest()!=row['sha256']:
                    raise ValueError('La integridad del PDF no coincide.')
                target=self.topic.topic()
                snapshot=json.loads(row['snapshot'])
                name=str(source['project'].get('name') or project_id)
                caption=f"Expediente de cierre · {name[:180]}\n{len(source['logs'])} reportes · {len(source['incidents'])} incidencias\nImágenes no disponibles: {len(snapshot['imageWarnings'])}\nCorte: {snapshot['cutoff']}"
                receipt=self.action(project_id,'document',lambda:self.document(row['pdf'],target,'expediente-'+hashlib.sha256(project_id.encode()).hexdigest()[:16]+'.pdf',caption))
                if receipt is None:
                    self.status(project_id,'review','Envío del PDF pendiente de confirmación. Revisar acciones.')
                    return
                # Fetch again: no closure based on a snapshot that changed during PDF upload.
                if self.digest(self.source(project_id)) != row['source_hash']:
                    self.status(project_id,'review','Los datos cambiaron durante el envío; el tema permanece abierto.')
                    return
                original=source['originalTopic']
                if original:
                    message=f"Proyecto finalizado: {name[:300]}\nExpediente enviado a Proyectos finalizados (mensaje {receipt['message_id']}).\n{len(source['logs'])} reportes, {len(source['incidents'])} incidencias.\nSe conserva el historial de este tema; no se borra ninguna evidencia."
                    actions=[('summary',lambda:self.telegram('sendMessage',{'chat_id':self.chat_id,'message_thread_id':int(original),'text':message})),
                             ('rename',lambda:self.telegram('editForumTopic',{'chat_id':self.chat_id,'message_thread_id':int(original),'name':('✅ Finalizado · '+name)[:128]})),
                             ('close',lambda:self.telegram('closeForumTopic',{'chat_id':self.chat_id,'message_thread_id':int(original)}))]
                    for step,operation in actions:
                        if self.action(project_id,step,operation) is None:
                            self.status(project_id,'review','Paso pendiente: '+step)
                            return
                    with self.connection() as db:
                        db.execute('UPDATE topics SET title=? WHERE project_id=?',(('✅ Finalizado · '+name)[:128],project_id))
                self.status(project_id,'closed')
            except NotReady as error:
                self.status(project_id,'waiting',str(error))
            except Exception as error:
                # No external action is replayed when its delivery was ambiguous.
                self.status(project_id,'error',type(error).__name__)

    def tick(self):
        projects=self.erp.request('/external/projects')['projects']
        for project in projects:
            if finished(project):
                self.process(project['id'])

    def resolve(self, body):
        if body.get('verified') is not True or not isinstance(body.get('note'),str) or not 1<=len(body['note'].strip())<=2000:
            raise ValueError('Verifica el resultado en Telegram y escribe una nota.')
        with self.lock, self.connection() as db:
            if body.get('step')=='topic':
                value=body.get('topicId')
                if type(value) is not int or value<0:
                    raise ValueError('Tema inválido. Usa 0 solo si verificaste que no se creó.')
                if value:
                    changed=db.execute("UPDATE settings SET value=? WHERE key='completed_projects_topic' AND value='creating'",(str(value),)).rowcount
                else:
                    changed=db.execute("DELETE FROM settings WHERE key='completed_projects_topic' AND value='creating'").rowcount
                return {'ok':bool(changed)}
            step=body.get('step')
            if step not in ('document','summary','rename','close') or body.get('decision') not in ('sent','retry'):
                raise ValueError('Acción inválida.')
            receipt=True
            if body['decision']=='sent' and step in ('document','summary'):
                if type(body.get('messageId')) is not int or body['messageId']<=0:
                    raise ValueError('Indica el mensaje confirmado en Telegram.')
                receipt={'message_id':body['messageId']}
            changed=db.execute("UPDATE project_archive_actions SET state=?,receipt=?,error=NULL WHERE project_id=? AND step=? AND state IN ('review','retry')",
                               (body['decision'],json.dumps(receipt),body.get('projectId'),step)).rowcount
        return {'ok':bool(changed)}

"""Incident tracking linked to the immutable ERP daily report; no separate ERP API."""
import json
from backend.reminders import Reminders
from backend.http_client import RemoteFailure


class IncidentService:
    def __init__(self, connection, now, telegram, chat_id, problem, telegram_photo=None, attachment_file=None):
        self.connection, self.now, self.telegram, self.chat_id, self.problem = connection, now, telegram, chat_id, problem
        self.delivery = Reminders(connection, None, telegram, chat_id, 'incident_topic', 'Incidencias')
        self.telegram_photo = telegram_photo
        self.attachment_file = attachment_file

    def allowed(self, user):
        with self.connection() as db:
            return bool(db.execute('''SELECT 1 FROM user_permissions p JOIN app_users u ON u.username=p.user
                WHERE p.user=? AND p.incidents=1 AND u.active=1''', (user,)).fetchone())

    def set_permission(self, body, actor):
        if type(body.get('enabled')) is not bool or not isinstance(body.get('user'),str):
            raise self.problem(400,'Permiso inválido.')
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM app_users WHERE username=?',(body['user'],)).fetchone():
                raise self.problem(404,'Usuario no encontrado.')
            db.execute('INSERT INTO user_permissions VALUES (?,?) ON CONFLICT(user) DO UPDATE SET incidents=excluded.incidents',(body['user'],int(body['enabled'])))
        return {'ok':True}

    def ingest(self):
        # ERP confirmation is mandatory. Uncertain/rejected submissions never become incidents.
        with self.connection() as db:
            rows = db.execute('''SELECT r.* FROM reports r LEFT JOIN incidents i ON i.id=r.id
                WHERE i.id IS NULL AND r.erp_log_id IS NOT NULL AND r.state NOT IN ('erp_sending','erp_review','erp_rejected')''').fetchall()
            for row in rows:
                payload=json.loads(row['payload'])
                details=payload.get('details') or {}
                if not details.get('incident'):
                    continue
                incident={**details['incident'],'author':details.get('author') or row['user'], 'operationDate':payload['operationDate']}
                for kind, key in [('project','project_id'),('task','task_id')]:
                    item=db.execute('SELECT payload FROM catalog WHERE kind=? AND id=?',(kind,row[key])).fetchone()
                    incident[kind]=json.loads(item[0]).get('name',row[key]) if item else row[key]
                created=db.execute('''INSERT OR IGNORE INTO incidents(id,user,erp_log_id,project_id,task_id,payload,created,updated)
                    VALUES (?,?,?,?,?,?,?,?)''',(row['id'],row['user'],row['erp_log_id'],row['project_id'],row['task_id'],json.dumps(incident),row['created'],self.now())).rowcount
                if created:
                    db.execute('INSERT INTO incident_events(incident_id,actor,status,note,created) VALUES (?,?,?,?,?)',(row['id'],row['user'],'open','Incidencia registrada en el diario ERP.',self.now()))

    def listing(self, offset=0, limit=500):
        with self.connection() as db:
            limit = min(500,max(1,limit))
            rows=[dict(r) for r in db.execute('SELECT * FROM incidents ORDER BY created DESC,id DESC LIMIT ? OFFSET ?', (limit,max(0,offset)))]
            for row in rows:
                row['payload']=json.loads(row['payload'])
                row['events']=[dict(e) for e in db.execute('SELECT actor,status,note,created FROM incident_events WHERE incident_id=? ORDER BY id',(row['id'],))]
                sent=db.execute('SELECT state FROM reminder_deliveries WHERE id=?',('incident:'+row['id'],)).fetchone()
                row['telegramState']=sent[0] if sent else 'pending'
                report=db.execute('SELECT payload FROM reports WHERE id=?',(row['id'],)).fetchone()
                ids=json.loads(report[0]).get('photos',[]) if report else []
                states=[]
                for pid in ids:
                    receipt=db.execute('SELECT state FROM reminder_deliveries WHERE id=?',(f"incident:{row['id']}:photo:{pid}",)).fetchone()
                    states.append(receipt[0] if receipt else 'pending')
                row['telegramPhotos']={'total':len(ids),'sent':states.count('sent')}
                if row['telegramState']=='sent' and any(s!='sent' for s in states):
                    row['telegramState']='review' if any(s in ('sending','review') for s in states) else 'pending'
        return {'incidents':rows, 'nextOffset':offset+len(rows) if len(rows)==limit else None}

    def update(self, body, actor):
        status, note=body.get('status'),body.get('note')
        if status not in ('open','in_progress','resolved') or not isinstance(note,str) or not 1<=len(note.strip())<=1000 or type(body.get('version')) is not int:
            raise self.problem(400,'Selecciona estado y escribe un comentario (1 a 1000 caracteres).')
        with self.connection() as db:
            changed=db.execute('UPDATE incidents SET status=?,version=version+1,updated=? WHERE id=? AND version=?',(status,self.now(),body.get('id'),body['version'])).rowcount
            if not changed:
                raise self.problem(409,'La incidencia cambió o no existe. Actualiza la lista antes de guardar.')
            db.execute('INSERT INTO incident_events(incident_id,actor,status,note,created) VALUES (?,?,?,?,?)',(body['id'],actor,status,note.strip(),self.now()))
        return {'ok':True}

    def tick(self, live):
        self.ingest()
        if not live:
            return
        with self.connection() as db:
            # The ERP diary must be confirmed, but urgent notices do not wait for photos.
            rows=db.execute("""SELECT i.*,r.payload AS report_payload FROM incidents i JOIN reports r ON r.id=i.id
                LEFT JOIN reminder_deliveries d ON d.id='incident:'||i.id
                WHERE r.erp_log_id IS NOT NULL AND r.state NOT IN ('erp_sending','erp_review','erp_rejected','demo_published','evidence_review')
                AND (d.id IS NULL OR d.state='retry' OR (d.state='sent' AND EXISTS (
                    SELECT 1 FROM json_each(r.payload,'$.photos') declared
                    LEFT JOIN reminder_deliveries photo_delivery
                      ON photo_delivery.id='incident:'||i.id||':photo:'||declared.value
                    WHERE photo_delivery.id IS NULL OR photo_delivery.state='retry'
                )))""").fetchall()
        for row in rows:
            data=json.loads(row['payload'])
            text=(f"INCIDENCIA · {row['id']}\nProyecto: {data['project']}\nTarea: {data['task']}\n"
                  f"Reportó: {data['author']}\nFecha: {data['operationDate']}\nPrioridad: {data['priority']}\n"
                  f"Detiene actividad: {'Sí' if data['stopsWork'] else 'No'}\n\n{data['description']}\n\n"
                  f"Asiento ERP: {row['erp_log_id']}\nConsulta el estado actual en la ventana Incidencias.")
            self.delivery.send_notice('incident:'+row['id'],{
                'chat_id':self.chat_id,'message_thread_id':self.delivery.topic(),'text':text[:2000]})
            with self.connection() as db:
                sent=db.execute('SELECT state FROM reminder_deliveries WHERE id=?',('incident:'+row['id'],)).fetchone()
            if sent and sent[0]=='sent':
                self._photos(row)

    def _photos(self, incident):
        if not self.telegram_photo:
            return
        ids=json.loads(incident['report_payload']).get('photos',[])
        for index,pid in enumerate(ids,1):
            key=f"incident:{incident['id']}:photo:{pid}"
            with self.connection() as db:
                photo=db.execute('SELECT * FROM photos WHERE id=? AND report_id=? AND user=?',
                                 (pid,incident['id'],incident['user'])).fetchone()
            # Wait for the existing ERP upload, never initiate a second upload.
            if not photo or photo['upload_state']!='confirmed' or not photo['attachment_id'] or photo['attachment_id'].startswith('demo-'):
                continue
            def send(photo=dict(photo),index=index):
                if not photo['data']:
                    # Read purged evidence from ERP in memory; do not keep extra copies.
                    try:
                        if not self.attachment_file:
                            raise ValueError('No evidence reader')
                        photo['data']=self.attachment_file(photo['attachment_id'])
                    except Exception:
                        raise RemoteFailure('No se pudo consultar la evidencia ERP; se reintentará.',False) from None
                self.telegram_photo(photo,self.delivery.topic(),caption=
                    f"Incidencia · {incident['id']}\nFoto {index}/{len(ids)} · {json.loads(incident['payload'])['task']}")
            # Separate receipt per photo: uncertain sends require manual verification.
            self.delivery.once(key,send)

"""Durable ERP evidence outbox. Ambiguous POSTs are reconciled, never blindly repeated."""
import json
from backend.http_client import RemoteFailure


class EvidenceService:
    def __init__(self, connection, lock, erp, mode):
        self.connection, self.lock, self.erp, self.mode = connection, lock, erp, mode

    def process(self):
        with self.lock:
            with self.connection() as db:
                cursor = db.execute("SELECT value FROM settings WHERE key='evidence_cursor'").fetchone()
                cursor = cursor[0] if cursor else ''
                reports = db.execute("SELECT * FROM reports WHERE state IN ('photos_pending','photos_review') ORDER BY CASE WHEN id>? THEN 0 ELSE 1 END,id LIMIT 15", (cursor,)).fetchall()
                if reports:
                    db.execute("INSERT INTO settings VALUES ('evidence_cursor',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (reports[-1]['id'],))
            for report in reports:
                if not report['erp_log_id']:
                    continue
                try:
                    ids = json.loads(report['payload']).get('photos', [])
                    for pid in ids:
                        with self.connection() as db:
                            photo = db.execute('SELECT * FROM photos WHERE id=? AND report_id=? AND user=?', (pid, report['id'], report['user'])).fetchone()
                        if not photo:
                            break
                        if photo['attachment_id']:
                            continue
                        if self.mode() == 'demo':
                            attachment_id = 'demo-' + pid
                        elif photo['upload_state'] in ('review', 'sending'):
                            matches = [a for a in self.erp.attachments(report['project_id'], report['erp_log_id']) if a.get('originalFileName') == pid + '.jpg' and a.get('mimeType') == 'image/jpeg' and str(a.get('sizeBytes')) == str(len(photo['data']))]
                            if len(matches) != 1:
                                raise RemoteFailure('Carga incierta: verifica la evidencia en ERP; no se repetirá automáticamente.', True)
                            attachment_id = matches[0]['id']
                        else:
                            with self.connection() as db:
                                db.execute("UPDATE photos SET upload_state='sending' WHERE id=?", (pid,))
                            try:
                                attachment_id = self.erp.upload_attachment(report['erp_log_id'], photo)
                            except RemoteFailure as error:
                                with self.connection() as db:
                                    db.execute('UPDATE photos SET upload_state=? WHERE id=?', ('review' if error.ambiguous else 'pending', pid))
                                raise
                        with self.connection() as db:
                            db.execute("UPDATE photos SET attachment_id=?,upload_state='confirmed' WHERE id=?", (attachment_id, pid))
                    else:
                        if self.mode() == 'live':
                            remote_ids = {a['id'] for a in self.erp.attachments(report['project_id'], report['erp_log_id'])}
                            with self.connection() as db:
                                local_ids = {db.execute('SELECT attachment_id FROM photos WHERE id=?', (pid,)).fetchone()[0] for pid in ids}
                            if not local_ids <= remote_ids:
                                raise RemoteFailure('Las evidencias todavía no aparecen en el proyecto ERP.')
                        with self.connection() as db:
                            db.execute("UPDATE reports SET state='telegram_pending',error=NULL WHERE id=?", (report['id'],))
                except (RemoteFailure, KeyError, TypeError, ValueError) as error:
                    with self.connection() as db:
                        db.execute('UPDATE reports SET state=?,error=? WHERE id=?', ('photos_review' if getattr(error, 'ambiguous', True) else 'photos_pending', getattr(error, 'message', 'Respuesta de evidencias inesperada.'), report['id']))

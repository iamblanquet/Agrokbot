"""Monitoreo de transacciones ERP/Telegram a partir de la tabla de reportes."""
import json
from datetime import datetime, timedelta, timezone

# estado del reporte -> (resultado ERP, resultado Telegram)
STATES = {
    "photos_pending": ("ok", "waiting"),
    "photos_review": ("ok", "waiting"),
    "evidence_review": ("review", "ok"),
    "erp_sending": ("pending", "waiting"),
    "erp_review": ("review", "waiting"),
    "erp_rejected": ("failed", "waiting"),
    "telegram_pending": ("ok", "pending"),
    "telegram_sending": ("ok", "pending"),
    "telegram_review": ("ok", "review"),
    "telegram_failed": ("ok", "failed"),
    "published": ("ok", "ok"),
    "demo_published": ("ok", "ok"),
}
IN_FLIGHT = ("erp_sending", "telegram_sending", "telegram_pending")
STUCK_AFTER = timedelta(minutes=15)


class MonitorService:
    def __init__(self, connection, lock, now, audit, actor, erp=None):
        self.connection = connection
        self.lock = lock
        self.now = now
        self.audit = audit
        self.actor = actor
        self.erp = erp

    @staticmethod
    def _age(created, reference):
        try:
            return reference - datetime.fromisoformat(created)
        except (TypeError, ValueError):
            return timedelta(0)

    def snapshot(self, state="all", hours=24, limit=200):
        reference = datetime.now(timezone.utc)
        since = (reference - timedelta(hours=hours)).isoformat()
        limit = max(1, min(int(limit), 500))
        with self.connection() as db:
            projects = {row[0]: json.loads(row[1]).get("name", row[0]) for row in db.execute("SELECT id,payload FROM catalog WHERE kind='project'")}
            rows = db.execute(
                "SELECT r.id,r.user,r.task_id,r.project_id,r.state,r.created,r.erp_log_id,r.message_id,r.error,"
                "(SELECT COUNT(*) FROM photos p WHERE p.report_id=r.id) AS photos, r.payload, "
                "(SELECT COUNT(*) FROM photos p WHERE p.report_id=r.id AND p.attachment_id IS NOT NULL AND p.upload_state='confirmed') AS confirmed "
                "FROM reports r WHERE r.created>=? ORDER BY r.created DESC", (since,)).fetchall()
        summary = {"total": len(rows), "ok": 0, "pending": 0, "review": 0, "failed": 0, "stuck": 0}
        items = []
        for row in rows:
            erp, telegram = STATES.get(row["state"], ("unknown", "unknown"))
            age = self._age(row["created"], reference)
            stuck = row["state"] in IN_FLIGHT and age > STUCK_AFTER
            inconsistent = row['state']=='published' and (not row['erp_log_id'] or row['confirmed']!=len(json.loads(row['payload']).get('photos',[])))
            if inconsistent:
                bucket='review';erp='review'
            elif row["state"] in ("published", "demo_published"):
                bucket = "ok"
            elif row["state"] in ("erp_rejected", "telegram_failed"):
                bucket = "failed"
            elif row["state"] in ("erp_review", "telegram_review", "photos_review", "evidence_review"):
                bucket = "review"
            else:
                bucket = "pending"
            summary[bucket] += 1
            summary["stuck"] += stuck
            if state in ("all", bucket) or (state == "stuck" and stuck):
                items.append({
                    "id": row["id"], "created": row["created"], "user": row["user"],
                    "project": projects.get(row["project_id"], row["project_id"]), "taskId": row["task_id"],
                    "state": 'evidence_review' if inconsistent else row["state"], "bucket": bucket, "erp": erp, "telegram": telegram, "stuck": stuck,
                    "ageMinutes": max(0, int(age.total_seconds() // 60)),
                    "erpLogId": row["erp_log_id"], "messageId": row["message_id"], "photos": row["photos"], "error": row["error"],
                })
        return {"hours": hours, "summary": summary, "transactions": items[:limit], "generated": self.now()}

    def retry_telegram(self, report_id):
        with self.lock, self.connection() as db:
            changed = db.execute("UPDATE reports SET state='telegram_pending',error=NULL WHERE id=? AND state='telegram_failed'", (str(report_id),)).rowcount
        if changed:
            self.audit.record("monitor_retry_telegram", str(report_id), {})
        return {"ok": bool(changed)}

    def reconcile_evidence(self, report_id, note, log_id=None):
        """Only restore verified receipts. Never upload/delete legacy evidence or resend Telegram."""
        import hashlib
        from backend.reconciliation import verified_log
        if not isinstance(note,str) or not 1<=len(note.strip())<=2000:
            raise ValueError('Escribe una nota de conciliación de hasta 2000 caracteres.')
        with self.lock:
            with self.connection() as db:
                row=db.execute('SELECT * FROM reports WHERE id=?',(report_id,)).fetchone()
                if not row or row['state'] not in ('published','evidence_review'):
                    raise ValueError('Solo se concilian reportes ya publicados.')
                photos={p['id']:p for p in db.execute('SELECT * FROM photos WHERE report_id=?',(report_id,))}
            log=verified_log(self.erp,row,log_id or row['erp_log_id'])
            receipts=[]
            for pid in json.loads(row['payload']).get('photos',[]):
                photo=photos.get(pid)
                if photo is None:
                    raise ValueError('Falta la fotografía local; no se inventará una confirmación.')
                matches=[a for a in log.get('attachments',[]) if a.get('id')==photo['attachment_id'] or a.get('originalFileName')==pid+'.jpg']
                if len(matches)!=1:
                    raise ValueError('La evidencia no aparece de forma única en ERP. Se conservan los bytes locales.')
                attachment=matches[0]['id']
                if hashlib.sha256(self.erp.attachment_file(attachment)).hexdigest()!=photo['digest']:
                    raise ValueError('El contenido remoto no coincide con la fotografía original.')
                receipts.append((attachment,pid))
            with self.connection() as db:
                for attachment,pid in receipts:
                    db.execute("UPDATE photos SET attachment_id=?,upload_state='confirmed' WHERE id=?",(attachment,pid))
                db.execute("UPDATE reports SET state='published',erp_log_id=?,error=NULL WHERE id=?",(log['id'],report_id))
            self.audit.record('evidence_reconciled',report_id,{'note':note,'attachments':len(receipts)})
            return {'ok':True,'confirmed':len(receipts)}

    def resolve(self, report_id, decision, note, log_id=None):
        report_id = str(report_id or "")
        note = str(note or "").strip()
        if decision not in ("confirm", "reject") or not note or len(note) > 2000:
            raise ValueError("Indica una decisión y una nota de resolución de hasta 2000 caracteres.")
        with self.lock, self.connection() as db:
            row = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            if not row or row["state"] not in ("erp_review", "telegram_review"):
                return {"ok": False}
            previous = row["state"]
            if decision == "confirm":
                if previous == 'erp_review':
                    from backend.reconciliation import verified_log
                    if not self.erp:
                        raise ValueError('La conciliación ERP no está configurada.')
                    verified_log(self.erp,row,log_id)
                    db.execute('UPDATE reports SET erp_log_id=? WHERE id=?',(log_id,report_id))
                    target='photos_pending' if json.loads(row['payload']).get('photos') else 'telegram_pending'
                else:
                    target='published'
            else:
                target = "erp_rejected" if previous == "erp_review" else "telegram_failed"
            db.execute("UPDATE reports SET state=?,error=? WHERE id=?", (target, note, report_id))
        self.audit.record("monitor_resolve", report_id, {"user": row["user"], "from": previous, "to": target, "decision": decision, "note": note})
        return {"ok": True, "state": target}

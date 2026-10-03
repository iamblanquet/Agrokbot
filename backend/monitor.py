"""Monitoreo de transacciones ERP/Telegram a partir de la tabla de reportes."""
import json
from datetime import datetime, timedelta, timezone

# estado del reporte -> (resultado ERP, resultado Telegram)
STATES = {
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
    def __init__(self, connection, lock, now, audit, actor):
        self.connection = connection
        self.lock = lock
        self.now = now
        self.audit = audit
        self.actor = actor

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
                "(SELECT COUNT(*) FROM photos p WHERE p.report_id=r.id) AS photos "
                "FROM reports r WHERE r.created>=? ORDER BY r.created DESC", (since,)).fetchall()
        summary = {"total": len(rows), "ok": 0, "pending": 0, "review": 0, "failed": 0, "stuck": 0}
        items = []
        for row in rows:
            erp, telegram = STATES.get(row["state"], ("unknown", "unknown"))
            age = self._age(row["created"], reference)
            stuck = row["state"] in IN_FLIGHT and age > STUCK_AFTER
            if row["state"] in ("published", "demo_published"):
                bucket = "ok"
            elif row["state"] in ("erp_rejected", "telegram_failed"):
                bucket = "failed"
            elif row["state"] in ("erp_review", "telegram_review"):
                bucket = "review"
            else:
                bucket = "pending"
            summary[bucket] += 1
            summary["stuck"] += stuck
            if state in ("all", bucket) or (state == "stuck" and stuck):
                items.append({
                    "id": row["id"], "created": row["created"], "user": row["user"],
                    "project": projects.get(row["project_id"], row["project_id"]), "taskId": row["task_id"],
                    "state": row["state"], "bucket": bucket, "erp": erp, "telegram": telegram, "stuck": stuck,
                    "erpLogId": row["erp_log_id"], "messageId": row["message_id"], "photos": row["photos"], "error": row["error"],
                })
        return {"hours": hours, "summary": summary, "transactions": items[:limit], "generated": self.now()}

    def retry_telegram(self, report_id):
        with self.lock, self.connection() as db:
            changed = db.execute("UPDATE reports SET state='telegram_pending',error=NULL WHERE id=? AND state='telegram_failed'", (str(report_id),)).rowcount
        if changed:
            self.audit.record("monitor_retry_telegram", str(report_id), {})
        return {"ok": bool(changed)}

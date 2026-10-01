"""Diagnóstico de disponibilidad sin exponer credenciales."""


class HealthService:
    def __init__(self, connection, config):
        self.connection = connection
        self.config = config

    def check(self):
        settings = self.config()
        checks = {}
        try:
            with self.connection() as db:
                db.execute("SELECT 1").fetchone()
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"

        erp_ready = settings["erp_mode"] == "demo" or bool(settings["erp_url"] and settings["erp_key"])
        telegram_ready = settings["telegram_mode"] == "demo" or bool(settings["bot_token"] and settings["chat_id"])
        checks["erp"] = "ok" if erp_ready else "not_configured"
        checks["telegram"] = "ok" if telegram_ready else "not_configured"
        ready = all(value == "ok" for value in checks.values())
        return (200 if ready else 503), {"ok": ready, "checks": checks}

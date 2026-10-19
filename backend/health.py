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
        checks["erp"] = "demo" if settings['erp_mode']=='demo' else "configured_not_verified" if erp_ready else "not_configured"
        checks["telegram"] = "demo" if settings['telegram_mode']=='demo' else "configured_not_verified" if telegram_ready else "not_configured"
        ready = checks['database']=='ok' and erp_ready and telegram_ready
        return (200 if ready else 503), {"ok": ready, "scope":"local_readiness", "deliveryVerified":False, "checks": checks}

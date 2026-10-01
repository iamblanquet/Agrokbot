"""Bitácora persistente de acciones administrativas y operativas."""
import json
import secrets


class AuditService:
    def __init__(self, connection, now, actor):
        self.connection = connection
        self.now = now
        self.actor = actor

    def entries(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT actor,action,target,details,created FROM audit_log ORDER BY created DESC LIMIT 500")]

    def record(self, action, target, details):
        actor = self.actor() if callable(self.actor) else self.actor
        with self.connection() as db:
            db.execute("INSERT INTO audit_log VALUES (?,?,?,?,?,?)", (secrets.token_hex(16), actor, action, target, json.dumps(details, sort_keys=True), self.now()))

"""Bitácora persistente de acciones administrativas y operativas."""
import json
import secrets
from contextvars import ContextVar

current_actor = ContextVar('audit_actor', default='system')


class AuditService:
    def __init__(self, connection, now, actor):
        self.connection = connection
        self.now = now
        self.actor = actor

    def entries(self, offset=0, limit=500):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT actor,action,target,details,created FROM audit_log ORDER BY created DESC,id DESC LIMIT ? OFFSET ?", (min(500,max(1,limit)),max(0,offset)))]

    def record(self, action, target, details):
        actor = self.actor() if callable(self.actor) else self.actor
        with self.connection() as db:
            db.execute("INSERT INTO audit_log VALUES (?,?,?,?,?,?)", (secrets.token_hex(16), actor, action, target, json.dumps(details, sort_keys=True), self.now()))

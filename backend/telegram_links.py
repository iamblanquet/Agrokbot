"""Explicit account linking; tokens are hashed, short-lived and single-use."""
import hashlib
import secrets
import time


class TelegramLinks:
    def __init__(self, connection, admin, problem):
        self.connection, self.admin, self.problem = connection, admin, problem

    def active(self, db, user):
        row = db.execute("SELECT active FROM app_users WHERE username=?", (user,)).fetchone()
        return bool(row["active"]) if row else user == self.admin()

    def status(self, user):
        with self.connection() as db:
            row = db.execute("SELECT telegram_id,username FROM telegram_links WHERE user=?", (user,)).fetchone()
        return {"linked": bool(row), "telegram": dict(row) if row else None}

    def issue(self, user):
        token = secrets.token_urlsafe(24)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not self.active(db, user):
                raise self.problem(403, "Cuenta inactiva.")
            if db.execute("SELECT 1 FROM telegram_links WHERE user=?", (user,)).fetchone():
                raise self.problem(409, "Desvincula primero la cuenta actual.")
            db.execute("DELETE FROM telegram_link_tokens WHERE user=? OR expires<=?", (user, time.time()))
            db.execute("INSERT INTO telegram_link_tokens VALUES (?,?,?)", (self.digest(token), user, time.time()+600))
        return token

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def confirm(self, token, telegram_id, username):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT user FROM telegram_link_tokens WHERE token=? AND expires>?", (self.digest(token), time.time())).fetchone()
            if not row or not self.active(db, row["user"]):
                raise self.problem(400, "Enlace vencido o inválido. Genera otro desde Campo.")
            if db.execute("SELECT 1 FROM telegram_links WHERE user=? OR telegram_id=?", (row["user"], str(telegram_id))).fetchone():
                raise self.problem(409, "Una de las cuentas ya está vinculada. Desvincúlala primero desde Campo.")
            db.execute("INSERT INTO telegram_links VALUES (?,?,?)", (row["user"], str(telegram_id), username or ""))
            db.execute("DELETE FROM telegram_link_tokens WHERE user=?", (row["user"],))

    def unlink(self, user):
        with self.connection() as db:
            db.execute("DELETE FROM telegram_links WHERE user=?", (user,))
            db.execute("DELETE FROM telegram_link_tokens WHERE user=?", (user,))
        return {"linked": False}

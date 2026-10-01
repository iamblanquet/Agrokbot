"""Administrative user and ERP assignment service."""
import re

from backend.audit import AuditService


class AdminError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


class AdminService:
    """Persistence and validation for the administrator's user CRUD."""

    def __init__(self, connection, catalog, task_responsible, pin_hash, pin_in_use, now, actor, audit=None):
        self.connection = connection
        self.catalog = catalog
        self.task_responsible = task_responsible
        self.pin_hash = pin_hash
        self.pin_in_use = pin_in_use
        self.now = now
        self.actor = actor
        self.audit = audit or AuditService(connection, now, actor)

    def users(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT username,responsible_name,employee_number,assignment_id,active,created FROM app_users ORDER BY username")]

    def audit_entries(self):
        return self.audit.entries()

    def responsibles(self):
        data = self.catalog()
        found = {}
        for task in data.get("tasks", []):
            person = self.task_responsible(task)
            if person["assignmentId"] and person["employeeNumber"]:
                found[person["assignmentId"]] = {
                    "assignmentId": person["assignmentId"],
                    "employeeNumber": person["employeeNumber"],
                    "name": person["name"],
                }
        return sorted(found.values(), key=lambda item: item["name"].casefold())

    def save(self, body):
        pin = str(body.get("pin", ""))
        assignment = body.get("assignmentId", "")
        previous_username = body.get("username", "")
        if previous_username is None:
            previous_username = ""
        if not isinstance(previous_username, str) or (previous_username and not re.fullmatch(r"[a-z0-9]+", previous_username)):
            raise AdminError(400, "El usuario a actualizar no es válido.")
        if not re.fullmatch(r"\d{4,8}", pin):
            raise AdminError(400, "El PIN debe tener entre 4 y 8 dígitos.")
        selected = next((item for item in self.responsibles() if item["assignmentId"] == assignment), None)
        if not selected:
            raise AdminError(400, "Selecciona un empleado válido de la API.")
        name, employee = selected["name"], selected["employeeNumber"]
        username = re.sub(r"[^a-z0-9]+", "", employee.casefold())
        with self.connection() as db:
            if self.pin_in_use(db, pin, excluding=previous_username or username):
                raise AdminError(409, "Ese PIN ya está asignado a otro usuario.")
            if previous_username and previous_username != username:
                if not db.execute("SELECT 1 FROM app_users WHERE username=?", (previous_username,)).fetchone():
                    raise AdminError(404, "Usuario a actualizar no encontrado.")
                if db.execute("SELECT 1 FROM app_users WHERE username=?", (username,)).fetchone():
                    raise AdminError(409, "El empleado seleccionado ya tiene otro usuario.")
                db.execute("UPDATE app_users SET username=? WHERE username=?", (username, previous_username))
                db.execute("UPDATE sessions SET user=? WHERE user=?", (username, previous_username))
                db.execute("UPDATE user_profiles SET user=? WHERE user=?", (username, previous_username))
            db.execute("INSERT INTO app_users(username,pin_hash,responsible_name,employee_number,assignment_id,created) VALUES (?,?,?,?,?,?) ON CONFLICT(username) DO UPDATE SET pin_hash=excluded.pin_hash,responsible_name=excluded.responsible_name,employee_number=excluded.employee_number,assignment_id=excluded.assignment_id,active=1", (username, self.pin_hash(pin), name.strip(), employee.strip(), assignment.strip(), self.now()))
            db.execute("INSERT INTO user_profiles(user,responsible_name,employee_number,assignment_id,updated) VALUES (?,?,?,?,?) ON CONFLICT(user) DO UPDATE SET responsible_name=excluded.responsible_name,employee_number=excluded.employee_number,assignment_id=excluded.assignment_id,updated=excluded.updated", (username, name.strip(), employee.strip(), assignment.strip(), self.now()))
        self._audit("user_update" if previous_username else "user_upsert", username, {"previousUsername": previous_username, "employeeNumber": employee.strip(), "assignmentId": assignment.strip()})
        return {"username": username, "responsibleName": name.strip(), "employeeNumber": employee.strip(), "assignmentId": assignment.strip(), "active": 1}

    def delete(self, body):
        username = body.get("username")
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM app_users WHERE username=?", (username,)).fetchone():
                raise AdminError(404, "Usuario no encontrado.")
            db.execute("UPDATE app_users SET active=0 WHERE username=?", (username,))
        self._audit("user_delete", username, {})
        return {"ok": True}

    def toggle(self, body):
        username = body.get("username")
        with self.connection() as db:
            row = db.execute("SELECT active FROM app_users WHERE username=?", (username,)).fetchone()
            if not row:
                raise AdminError(404, "Usuario no encontrado.")
            db.execute("UPDATE app_users SET active=? WHERE username=?", (0 if row["active"] else 1, username))
        self._audit("user_toggle", username, {"active": not bool(row["active"])})
        return {"ok": True}

    def _audit(self, action, target, details):
        self.audit.record(action, target, details)

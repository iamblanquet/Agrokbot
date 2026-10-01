"""Field employees, role versions and crew validation."""
import json
import re
import secrets


ROLES = {"operator": "Operadores", "technician": "Técnicos", "assistant": "Auxiliares"}


class EmployeeService:
    def __init__(self, connection, lock, problem):
        self.connection=connection;self.lock=lock;self.problem=problem

    def list(self):
        with self.connection() as db:
            return [{"id": row["id"], "name": row["name"], "roles": json.loads(row["roles"]), "version": row["version"]} for row in db.execute("SELECT * FROM employees WHERE deleted=0 ORDER BY name COLLATE NOCASE")]

    def save(self, body, delete=False):
        employee_id = body.get("id")
        if employee_id is not None and (not isinstance(employee_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", employee_id)):
            raise self.problem(400, "Empleado inválido.")
        if delete and not employee_id:
            raise self.problem(400, "Selecciona un empleado.")
        name, roles = body.get("name"), body.get("roles")
        if not delete:
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                raise self.problem(400, "Escribe un nombre de entre 1 y 80 caracteres.")
            if not isinstance(roles, list) or not roles or any(not isinstance(role, str) or role not in ROLES for role in roles):
                raise self.problem(400, "Selecciona al menos un rol válido.")
            name, roles = name.strip(), sorted(set(roles))
        with self.lock, self.connection() as db:
            prior = db.execute("SELECT * FROM employees WHERE id=? AND deleted=0", (employee_id,)).fetchone() if employee_id else None
            if employee_id and not prior:
                raise self.problem(404, "El empleado ya no está disponible. Actualiza el catálogo.")
            if prior and body.get("version") != prior["version"]:
                raise self.problem(409, "Otro usuario modificó al empleado. Actualiza el catálogo antes de editar.")
            if delete:
                db.execute("UPDATE employees SET deleted=1 WHERE id=?", (employee_id,))
                return {"ok": True}
            employee_id = employee_id or secrets.token_hex(16)
            version = prior["version"] + 1 if prior else 1
            encoded = json.dumps(roles)
            db.execute("INSERT INTO employees(id,name,roles,version) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,roles=excluded.roles,version=excluded.version", (employee_id, name, encoded, version))
            db.execute("INSERT INTO employee_versions VALUES (?,?,?,?)", (employee_id, version, name, encoded))
            return {"id": employee_id, "name": name, "roles": roles, "version": version}

    def validate_crew(self, value):
        if not isinstance(value, list) or len(value) > 30:
            raise self.problem(400, "Selecciona hasta 30 personas por reporte.")
        result, seen = [], set()
        with self.connection() as db:
            for item in value:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or type(item.get("version")) is not int or not isinstance(item.get("role"), str):
                    raise self.problem(400, "Personal del reporte inválido.")
                row = db.execute("SELECT * FROM employee_versions WHERE id=? AND version=?", (item["id"], item["version"])).fetchone()
                if not row or item["role"] not in json.loads(row["roles"]) or item["id"] in seen:
                    raise self.problem(400, "Revisa la cuadrilla: empleado o rol inválido, o persona repetida.")
                seen.add(item["id"])
                result.append({"id": item["id"], "version": item["version"], "name": row["name"], "role": item["role"]})
        return sorted(result, key=lambda item: item["id"])

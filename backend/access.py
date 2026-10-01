"""Resolución de identidad ERP y filtrado de catálogo por usuario."""
import urllib.parse

from backend.http_client import RemoteFailure


class AccessService:
    """Centraliza la relación usuario-aplicación con responsable ERP."""

    def __init__(self, connection, erp, task_responsible, problem, admin_user, erp_mode):
        self.connection = connection
        self.erp = erp
        self.task_responsible = task_responsible
        self.problem = problem
        self.admin_user = admin_user
        self.erp_mode = erp_mode

    def profile_for(self, user):
        with self.connection() as db:
            row = db.execute("SELECT user,responsible_name,employee_number,assignment_id FROM user_profiles WHERE user=?", (user,)).fetchone()
        return dict(row) if row else {"user": user, "responsible_name": "", "employee_number": "", "assignment_id": ""}

    def catalog_for_user(self, data, user):
        """Devuelve únicamente las tareas ERP relacionadas con la sesión."""
        if user == self.admin_user():
            return data
        profile = self.profile_for(user)
        assignment_id, employee_number = profile.get("assignment_id", ""), profile.get("employee_number", "")
        if not assignment_id and not employee_number:
            return {"projects": [], "tasks": [], "employees": [], "fetchedAt": data.get("fetchedAt")}
        if self.erp_mode() == "live" and assignment_id:
            try:
                filtered = self.erp("/external/project-tasks?" + urllib.parse.urlencode({"responsibleAssignmentId": assignment_id})).get("tasks", [])
                if filtered:
                    data = {**data, "tasks": filtered}
            except (RemoteFailure, KeyError, TypeError) as error:
                raise self.problem(502, getattr(error, "message", "No se pudo consultar las tareas del empleado en el ERP.")) from None
        tasks = [task for task in data.get("tasks", []) if ((self.task_responsible(task)["assignmentId"] == assignment_id) or (self.task_responsible(task)["employeeNumber"] == employee_number))]
        project_ids = {task.get("projectId") for task in tasks}
        return {**data, "tasks": tasks, "projects": [project for project in data.get("projects", []) if project.get("id") in project_ids]}

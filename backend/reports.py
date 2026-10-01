"""Validation and persistence workflow for field reports."""
import json
import os
import re
import urllib.parse
from datetime import date, datetime, timezone

from backend.http_client import RemoteFailure


class ReportService:
    def __init__(self, connection, lock, problem, now, profile_for, catalog, catalog_for_user, task_responsible, validate_crew, validate_details, field_message, public_report, erp, settings, roles):
        self.connection=connection;self.lock=lock;self.problem=problem;self.now=now;self.profile_for=profile_for;self.catalog=catalog;self.catalog_for_user=catalog_for_user;self.task_responsible=task_responsible;self.validate_crew=validate_crew;self.validate_details=validate_details;self.field_message=field_message;self.public_report=public_report;self.erp=erp;self.settings=settings;self.roles=roles

    def create(self, payload, user, reporter_name=None, origin="campo-pwa"):
        if not isinstance(payload, dict):
            raise self.problem(400, "Reporte inválido.")
        profile = self.profile_for(user)
        linked_name = profile.get("responsible_name") or reporter_name or user
        rid = payload.get("id", "")
        if not isinstance(rid, str) or not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", rid):
            raise self.problem(400, "Identificador de reporte inválido.")
        try:
            frozen = json.dumps(payload, sort_keys=True, allow_nan=False)
        except (ValueError, TypeError):
            raise self.problem(400, "Datos de reporte inválidos.") from None
        with self.lock, self.connection() as db:
            prior_submission = db.execute("SELECT * FROM submissions WHERE id=?", (rid,)).fetchone()
            if prior_submission and (prior_submission["user"] != user or prior_submission["payload"] != frozen):
                raise self.problem(409, "El reporte está confirmado y no admite modificaciones. Registra una aclaración separada.", "immutable")
            if not prior_submission and not db.execute("SELECT 1 FROM reports WHERE id=?", (rid,)).fetchone():
                db.execute("INSERT INTO submissions VALUES (?,?,?,?)", (rid, user, frozen, self.now()))
        for field in ("progressBps", "baseProgressBps"):
            value = payload.get(field)
            if type(value) is not int or not 0 <= value <= 10000:
                raise self.problem(400, "El avance debe estar entre 0 y 100 %.")
        notes = payload.get("notes", "")
        if not isinstance(payload.get("taskId"), str) or not payload["taskId"]:
            raise self.problem(400, "Selecciona una tarea válida.")
        if not isinstance(notes, str) or not notes.strip() or len(notes) > 2000:
            raise self.problem(400, "Escribe observaciones de entre 1 y 2000 caracteres.")
        try:
            operation_date = date.fromisoformat(payload.get("operationDate", ""))
            if operation_date > datetime.now(timezone.utc).date():
                raise ValueError()
        except (ValueError, TypeError):
            raise self.problem(400, "La fecha de operación es inválida o futura.") from None
        clean = {key: payload.get(key) for key in ("id", "taskId", "progressBps", "baseProgressBps", "notes", "operationDate")}
        if "crew" in payload:
            clean["crew"] = self.validate_crew(payload["crew"])
        clean.update(self.validate_details(payload, user, rid))
        serialized = json.dumps(clean, sort_keys=True)
        with self.lock:
            with self.connection() as db:
                prior = db.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
                if prior:
                    if prior["user"] != user or prior["payload"] != serialized:
                        raise self.problem(409, "Ese identificador ya pertenece a otro reporte.")
                    return self.public_report(prior)
                uncertain = db.execute("SELECT 1 FROM reports WHERE task_id=? AND state IN ('erp_review','erp_sending')", (clean["taskId"],)).fetchone()
                if uncertain:
                    raise self.problem(409, "Hay un registro de esta tarea por verificar en ERP antes de enviar otro avance.", "erp_unresolved")
            data = self.catalog_for_user(self.catalog(), user)
            task = next((item for item in data["tasks"] if item["id"] == clean["taskId"]), None)
            if not task:
                raise self.problem(404, "La tarea ya no está disponible para esta integración.")
            linked = self.profile_for(user)
            assignment = self.task_responsible(task)
            settings = self.settings()
            if user != settings["user"] and (linked.get("assignment_id") or linked.get("employee_number")):
                if linked.get("assignment_id") and assignment["assignmentId"] and linked["assignment_id"] != assignment["assignmentId"]:
                    raise self.problem(403, "Esta tarea está asignada a otro empleado.", "responsible_forbidden")
                if linked.get("employee_number") and assignment["employeeNumber"] and linked["employee_number"] != assignment["employeeNumber"]:
                    raise self.problem(403, "Esta tarea está asignada a otro empleado.", "responsible_forbidden")
            current = task.get("progressBps", 0)
            if current != clean["baseProgressBps"] or clean["progressBps"] < current:
                raise self.problem(409, "La tarea cambió o el reporte reduciría su avance. Revisa el valor actual.", "conflict", {"currentProgressBps": current})
            project = next(item for item in data["projects"] if item["id"] == task["projectId"])
            erp_name = (task.get("responsibleName") or "").strip()
            if settings["enforce_responsible_access"] and erp_name and linked_name.casefold() != erp_name.casefold():
                raise self.problem(403, "Esta tarea está asignada a otro responsable.", "responsible_forbidden")
            serialized = json.dumps(clean, sort_keys=True)
            author = f"{reporter_name or erp_name or linked_name} ({user})"
            message = f"AVANCE REGISTRADO · {task['code']}\n\nProyecto: {project['name']}\nTarea: {task['name']}\nAvance: {clean['progressBps']/100:g} %\nEstado: {'Finalizada' if clean['progressBps'] == 10000 else 'En progreso' if clean['progressBps'] else 'Sin iniciar'}\nReportó: {author}\nFecha: {clean['operationDate']}\n\n{notes}\n\nRef: {rid}"
            crew = clean.get("crew", [])
            if crew:
                details = "\n".join(f"{label}: " + ", ".join(entry["name"] for entry in crew if entry["role"] == role) for role, label in self.roles.items() if any(entry["role"] == role for entry in crew))
                message += f"\n\nPERSONAL EN CAMPO · {len(crew)} personas\n{details}"
            if "details" in clean:
                message = self.field_message(clean, project, task, user)
            if len(message.encode("utf-16-le")) // 2 > 4096:
                raise self.problem(400, "El reporte con la cuadrilla es demasiado largo. Reduce las observaciones.")
            with self.connection() as db:
                db.execute("INSERT INTO reports(id,user,task_id,project_id,payload,state,created,message) VALUES (?,?,?,?,?,'erp_sending',?,?)", (rid, user, task["id"], project["id"], serialized, self.now(), message))
            state, error = "telegram_pending", None
            log_id = "demo-" + rid
            if settings["erp_mode"] == "live":
                try:
                    crew_summary_text = ""
                    if clean.get("crew"):
                        crew_parts = [f"{label}: " + ", ".join(entry["name"] for entry in clean["crew"] if entry.get("role") == role) for role, label in (("operator", "Operadores"), ("technician", "Técnicos"), ("assistant", "Auxiliares")) if any(entry.get("role") == role for entry in clean["crew"])]
                        if crew_parts:
                            crew_summary_text = f"\n\nPersonal en campo ({len(clean['crew'])}):\n" + "\n".join(f"- {part}" for part in crew_parts)
                    erp_notes = message if "details" in clean else notes + crew_summary_text
                    erp_display_user = (clean.get("details") or {}).get("author") or linked_name or user
                    result = self.erp(f"/external/project-tasks/{urllib.parse.quote(task['id'], safe='')}/operation-log", {"source": "WEBAPP", "externalUserId": erp_display_user, "operationDate": clean["operationDate"], "progressBps": clean["progressBps"], "notes": erp_notes, "assetIds": [], "metadataJson": {"clientApp": origin, "clientReportId": rid, "submittedAt": self.now(), "authenticatedUserId": user, "crew": clean.get("crew", []), "personnelCount": len(clean.get("crew", [])), "fieldReport": clean.get("details"), "photoCount": len(clean.get("photos", []))}})
                    log_id = result["operationLog"]["id"]
                except (RemoteFailure, KeyError, TypeError) as failure:
                    state = "erp_review" if getattr(failure, "ambiguous", True) else "erp_rejected"
                    error = getattr(failure, "message", "Respuesta ERP inesperada; verificar registro antes de repetir.")
                    log_id = None
            with self.connection() as db:
                db.execute("UPDATE reports SET state=?,error=?,erp_log_id=? WHERE id=?", (state, error, log_id, rid))
                if state == "telegram_pending":
                    task["progressBps"] = clean["progressBps"]
                    task["status"] = "FINISHED" if clean["progressBps"] == 10000 else "IN_PROGRESS" if clean["progressBps"] else "CREATED"
                    db.execute("UPDATE catalog SET payload=? WHERE kind='task' AND id=?", (json.dumps(task), task["id"]))
                return self.public_report(db.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone())

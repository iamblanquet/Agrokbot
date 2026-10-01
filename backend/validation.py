"""Validación y formato de datos de captura de campo."""
import math
from datetime import datetime, timezone, timedelta

from backend.media import valid_id


class ValidationService:
    """Aplica las reglas de captura sin depender del servidor HTTP."""

    def __init__(self, connection, problem):
        self.connection = connection
        self.problem = problem

    def validate_details(self, payload, user, report_id):
        result = {}
        details = payload.get("details")
        if details is not None:
            if not isinstance(details, dict):
                raise self.problem(400, "Datos de campo inválidos.")

            def text(key, limit):
                value = details.get(key)
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit or any(ord(c) < 32 for c in value):
                    raise self.problem(400, f"Revisa el campo {key}.")
                return value.strip()

            def number(value, maximum):
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
                    raise self.problem(400, "Cantidad, horas o combustible inválidos.")
                return value

            author = text("author", 80)
            raw_title = details.get("title")
            title = raw_title.strip() if isinstance(raw_title, str) else ""
            if title and (len(title) > 80 or any(ord(c) < 32 for c in title)):
                raise self.problem(400, "Revisa el campo title.")
            captured = text("capturedAt", 40)
            try:
                stamp = datetime.fromisoformat(captured.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError()
            except ValueError:
                raise self.problem(400, "Hora de captura inválida.") from None
            offset, offline = details.get("timezoneOffset"), details.get("offline")
            if type(offset) is not int or not -840 <= offset <= 840 or type(offline) is not bool:
                raise self.problem(400, "Zona horaria o conexión de captura inválida.")
            unit = details.get("unit")
            if unit not in ("ha", "m", "m²", "m³", "km", "unidades"):
                raise self.problem(400, "Selecciona una unidad válida.")
            machines = details.get("machinery", [])
            if not isinstance(machines, list) or len(machines) > 5:
                raise self.problem(400, "Registra hasta cinco máquinas.")
            machinery = []
            for machine in machines:
                if not isinstance(machine, dict) or not isinstance(machine.get("name"), str) or not 1 <= len(machine["name"].strip()) <= 80 or any(ord(c) < 32 for c in machine["name"]):
                    raise self.problem(400, "Escribe el nombre de cada máquina.")
                machinery.append({"name": machine["name"].strip(), "hours": number(machine.get("hours"), 24), "liters": number(machine.get("liters"), 100000)})
            result["details"] = {"author": author, "title": title, "capturedAt": captured, "timezoneOffset": offset, "offline": offline,
                                  "quantity": number(details.get("quantity"), 100000000), "unit": unit, "machinery": machinery}
            if "stoppage" in details:
                stop = details["stoppage"]
                if not isinstance(stop, dict) or stop.get("reason") not in ("Lluvia", "Sin Material", "Sin Cuadrilla", "Sin Máquina", "Descanso", "Otro"):
                    raise self.problem(400, "Selecciona un motivo de paro válido.")
                description = stop.get("description", "")
                if not isinstance(description, str) or len(description) > 200 or any(ord(c) < 32 for c in description) or (stop["reason"] == "Otro" and not description.strip()):
                    raise self.problem(400, "Describe el motivo del paro (hasta 200 caracteres).")
                if result["details"]["quantity"] != 0 or payload["progressBps"] != payload["baseProgressBps"]:
                    raise self.problem(400, "Un día sin actividad debe tener avance de jornada cero y conservar el porcentaje acumulado.")
                result["details"]["stoppage"] = {"reason": stop["reason"], "description": description.strip() if stop["reason"] == "Otro" else ""}
        if "photos" in payload:
            ids = payload["photos"]
            if not isinstance(ids, list) or len(ids) > 6 or any(not valid_id(pid) for pid in ids) or len(set(ids)) != len(ids):
                raise self.problem(400, "Adjunta hasta seis fotografías distintas.")
            with self.connection() as db:
                for photo_id in ids:
                    if not db.execute("SELECT 1 FROM photos WHERE id=? AND report_id=? AND user=?", (photo_id, report_id, user)).fetchone():
                        raise self.problem(400, "Falta cargar una fotografía. Conserva el pendiente y vuelve a sincronizar.")
            result["photos"] = ids
        return result

    def field_message(self, clean, project, task, user):
        details = clean["details"]
        captured = datetime.fromisoformat(details["capturedAt"].replace("Z", "+00:00")).astimezone(timezone(timedelta(minutes=-details["timezoneOffset"])))
        crew = clean.get("crew", [])
        if crew:
            crew_parts = []
            for role, label in (("operator", "Operadores"), ("technician", "Técnicos"), ("assistant", "Auxiliares")):
                names = [employee["name"] for employee in crew if employee.get("role") == role]
                if names:
                    crew_parts.append(f"{label}: {', '.join(names)}")
            crew_line = f"\n👥 Cuadrilla ({len(crew)} personas):\n" + "\n".join(f"  • {part}" for part in crew_parts)
        else:
            crew_line = "\n👥 Cuadrilla: Sin personal asignado"
        machines = " · ".join(f"{machine['name']}: {machine['hours']:g} hrs ({machine['liters']:g} L)" for machine in details["machinery"]) or "Sin maquinaria"
        stoppage = details.get("stoppage")
        status = f"\n☂ Estatus: Día sin actividad (Paro)\nMotivo: {stoppage['reason']}" + (f" — {stoppage['description']}" if stoppage["description"] else "") if stoppage else ""
        return (f"📅 Fecha Operativa: {clean['operationDate']}"
                f"\n⏰ Hora Captura ({'Sin Internet' if details['offline'] else 'Con Internet'}): {captured:%H:%M:%S} hrs"
                f"{status}\n👤 " + (f"Autor: {details['author']} - {details['title']}" if details.get("title") else f"Responsable: {details['author']}") + f"\n📊 Avance: {details['quantity']:g} {details['unit']}"
                f"{crew_line}\n🚜 Maquinaria: {machines}"
                f"\n\nTarea: {task['name']}\nAvance acumulado: {clean['progressBps']/100:g} %"
                f"\nCapturado: {captured:%Y-%m-%d %H:%M:%S %z}"
                f"\n\n{clean['notes']}\n\nRef: {clean['id']}")

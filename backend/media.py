"""Private evidence photo validation and persistence."""
import base64
import binascii
import hashlib
import re
import json


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9-]{16,80}", value)


class MediaService:
    def __init__(self, connection, lock, problem, audit=None):
        self.connection=connection;self.lock=lock;self.problem=problem;self.audit=audit

    def purge_delivered(self):
        # Preserve metadata and pending bytes. Empty BLOB is compatible with
        # existing NOT NULL schemas and does not recreate data on upload retries.
        with self.lock, self.connection() as db:
            db.execute("PRAGMA secure_delete=ON")
            return db.execute("""UPDATE photos SET data=X''
                WHERE length(data)>0 AND upload_state='confirmed'
                AND attachment_id IS NOT NULL AND attachment_id NOT LIKE 'demo-%'
                AND report_id IN (SELECT id FROM reports WHERE state='published')""").rowcount

    def save_photo(self, body, user):
        pid, rid, encoded = body.get("id"), body.get("reportId"), body.get("data")
        if not valid_id(pid) or not valid_id(rid) or not isinstance(encoded, str) or len(encoded) > 2000000:
            raise self.problem(400, "Fotografía inválida o demasiado grande.")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise self.problem(400, "Fotografía inválida.") from None
        if not 4 <= len(data) <= 1500000 or not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
            raise self.problem(400, "Se requiere una fotografía JPEG de hasta 1.5 MB.")
        digest = hashlib.sha256(data).hexdigest()
        with self.lock, self.connection() as db:
            prior = db.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
            if prior:
                if prior["user"] != user or prior["report_id"] != rid or prior["digest"] != digest:
                    raise self.problem(409, "La fotografía ya pertenece a otra captura.")
                return {"id": pid}
            report = db.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
            if report and (report['user'] != user or pid not in json.loads(report['payload']).get('photos', [])):
                raise self.problem(403, "La fotografía no pertenece a este reporte.")
            if report and report["state"] != "photos_pending":
                raise self.problem(409, "No se pueden añadir fotos a un reporte ya registrado.")
            if not report and db.execute("SELECT 1 FROM submissions WHERE id=?", (rid,)).fetchone():
                raise self.problem(409, "No se pueden añadir fotos a un reporte ya registrado.")
            if db.execute("SELECT count(*) FROM photos WHERE report_id=?", (rid,)).fetchone()[0] >= 30:
                raise self.problem(400, "Demasiadas fotografías cargadas para esta captura.")
            db.execute("INSERT INTO photos(id,report_id,user,data,digest) VALUES (?,?,?,?,?)", (pid, rid, user, data, digest))
        if self.audit:self.audit("photo_uploaded", pid, {"report_id": rid, "user": user})
        return {"id": pid}

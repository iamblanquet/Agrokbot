"""Persistent Telegram outbox delivery."""
import hashlib
import json

from backend.http_client import RemoteFailure


class DeliveryService:
    def __init__(self, connection, lock, settings, telegram, telegram_photo, telegram_media_group):
        self.connection = connection
        self.lock = lock
        self.settings = settings
        self.telegram = telegram
        self.telegram_photo = telegram_photo
        self.telegram_media_group = telegram_media_group

    def deliver(self):
        settings = self.settings()
        with self.lock:
            with self.connection() as db:
                rows = db.execute("SELECT * FROM reports WHERE state='telegram_pending' ORDER BY created LIMIT 15").fetchall()
            for report in rows:
                with self.connection() as db:
                    topic = db.execute("SELECT * FROM topics WHERE project_id=?", (report["project_id"],)).fetchone()
                    project = db.execute("SELECT payload FROM catalog WHERE kind='project' AND id=?", (report["project_id"],)).fetchone()
                    title = json.loads(project[0])["name"] if project else report["project_id"]
                    db.execute("UPDATE reports SET state='telegram_sending',error=NULL WHERE id=?", (report["id"],))
                try:
                    if not topic:
                        if settings["mode"] == "demo":
                            thread_id = str(int(hashlib.sha256(report["project_id"].encode()).hexdigest()[:6], 16))
                        else:
                            chat = self.telegram("getChat", {"chat_id": settings["chat_id"]})
                            if chat.get("type") != "supergroup" or not chat.get("is_forum"):
                                raise RemoteFailure("El grupo configurado debe ser un supergrupo con temas activados.")
                            thread_id = str(self.telegram("createForumTopic", {"chat_id": settings["chat_id"], "name": title[:128]})["message_thread_id"])
                        with self.connection() as db:
                            db.execute("INSERT INTO topics VALUES (?,?,?)", (report["project_id"], thread_id, title))
                    else:
                        thread_id = topic["thread_id"]
                    photo_ids = json.loads(report["payload"]).get("photos", [])
                    message_id = report["message_id"]
                    if not message_id:
                        if not photo_ids:
                            if settings["mode"] == "demo":
                                message_id = "demo-" + report["id"][:8]
                            else:
                                data = {"chat_id": settings["chat_id"], "message_thread_id": int(thread_id), "text": report["message"]}
                                if settings["public_url"].startswith("https://"):
                                    data["reply_markup"] = {"inline_keyboard": [[{"text": "Abrir Campo", "url": settings["public_url"]}]]}
                                message_id = str(self.telegram("sendMessage", data)["message_id"])
                            with self.connection() as db:
                                db.execute("UPDATE reports SET message_id=?,thread_id=? WHERE id=?", (message_id, thread_id, report["id"]))
                        elif len(photo_ids) == 1:
                            with self.connection() as db:
                                photo = db.execute("SELECT * FROM photos WHERE id=? AND report_id=?", (photo_ids[0], report["id"])).fetchone()
                            if not photo:
                                raise RemoteFailure("No se encuentra una fotografía del reporte.")
                            reply_markup = {"inline_keyboard": [[{"text": "Abrir Campo", "url": settings["public_url"]}]]} if settings["public_url"].startswith("https://") else None
                            if settings["mode"] == "demo":
                                message_id = "demo-" + photo_ids[0][:8]
                            else:
                                message_id = self.telegram_photo(photo, thread_id, caption=report["message"], reply_markup=reply_markup)
                            with self.connection() as db:
                                db.execute("UPDATE reports SET message_id=?,thread_id=? WHERE id=?", (message_id, thread_id, report["id"]))
                                db.execute("UPDATE photos SET message_id=? WHERE id=?", (message_id, photo_ids[0]))
                        else:
                            photos = []
                            with self.connection() as db:
                                for pid in photo_ids:
                                    photo = db.execute("SELECT * FROM photos WHERE id=? AND report_id=?", (pid, report["id"])).fetchone()
                                    if not photo:
                                        raise RemoteFailure("No se encuentra una fotografía del reporte.")
                                    photos.append(photo)
                            caption = report["message"]
                            if settings["public_url"].startswith("https://") and (len(caption.encode("utf-16-le")) // 2 + len(settings["public_url"]) + 20 <= 1024):
                                caption += f"\n\n🔗 Abrir Campo: {settings['public_url']}"
                            if settings["mode"] == "demo":
                                message_ids = ["demo-" + pid[:8] for pid in photo_ids]
                            else:
                                message_ids = self.telegram_media_group(photos, thread_id, caption=caption)
                            message_id = message_ids[0]
                            with self.connection() as db:
                                db.execute("UPDATE reports SET message_id=?,thread_id=? WHERE id=?", (message_id, thread_id, report["id"]))
                                for index, pid in enumerate(photo_ids):
                                    db.execute("UPDATE photos SET message_id=? WHERE id=?", (message_ids[index] if index < len(message_ids) else message_id, pid))
                    else:
                        for index, pid in enumerate(photo_ids, 1):
                            with self.connection() as db:
                                photo = db.execute("SELECT * FROM photos WHERE id=? AND report_id=?", (pid, report["id"])).fetchone()
                            if not photo:
                                raise RemoteFailure("No se encuentra una fotografía del reporte.")
                            if photo["message_id"]:
                                continue
                            photo_message = "demo-" + pid if settings["mode"] == "demo" else self.telegram_photo(photo, thread_id, message_id=message_id, caption=f"Evidencia {index}/{len(photo_ids)} · Ref: {report['id']}")
                            with self.connection() as db:
                                db.execute("UPDATE photos SET message_id=? WHERE id=?", (photo_message, pid))
                    with self.connection() as db:
                        db.execute("UPDATE reports SET state=?,error=NULL WHERE id=?", ("demo_published" if settings["mode"] == "demo" else "published", report["id"]))
                except (RemoteFailure, KeyError, ValueError, TypeError) as failure:
                    state = "telegram_review" if getattr(failure, "ambiguous", True) else "telegram_failed"
                    with self.connection() as db:
                        db.execute("UPDATE reports SET state=?,error=? WHERE id=?", (state, getattr(failure, "message", "Respuesta inesperada de Telegram."), report["id"]))

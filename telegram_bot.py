"""Telegram report wizard. Uses durable drafts and the same idempotent report service as PWA."""
import hashlib
import json
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal


class ReportBot:
    def __init__(self, backend):
        self.b = backend
        self.username = ""
        self.scope = hashlib.sha256(backend.BOT_TOKEN.encode()).hexdigest()[:16]
        self.offset_key = "telegram_offset:" + self.scope
        with self.b.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bot_drafts (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def key(self, chat, uid, thread=None):
        return f"{self.scope}:{chat}:{uid}:{thread or 0}"

    def save(self, draft):
        draft["updated"] = time.time()
        with self.b.connection() as db:
            db.execute("INSERT OR REPLACE INTO bot_drafts VALUES (?,?)", (draft["key"], json.dumps(draft)))

    def load(self, key):
        with self.b.connection() as db:
            row = db.execute("SELECT payload FROM bot_drafts WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def authorized(self, user):
        if user.get("is_bot") or not user.get("id"):
            return False
        if self.b.ALLOWED and str(user["id"]) not in self.b.ALLOWED:
            return False
        member = self.b.telegram("getChatMember", {"chat_id": self.b.CHAT_ID, "user_id": user["id"]})
        return member.get("status") in ("creator", "administrator", "member") or (member.get("status") == "restricted" and member.get("is_member", False))

    def send(self, draft, text, markup=None, force=False):
        data = {"chat_id": draft["chat"], "text": text}
        if draft.get("thread"):
            data["message_thread_id"] = draft["thread"]
        if markup:
            data["reply_markup"] = {"inline_keyboard": markup}
        elif force:
            data["reply_markup"] = {"force_reply": True, "selective": True}
            if draft.get("input_message"):
                data["reply_parameters"] = {"message_id": draft["input_message"], "allow_sending_without_reply": True}
        result = self.b.telegram("sendMessage", data)
        draft["prompt_id"] = result["message_id"]
        self.save(draft)

    def buttons(self, draft, choices):
        return [[{"text": label[:80], "callback_data": f"r:{draft['nonce']}:{action}"}] for label, action in choices]

    def catalog_for_user(self, user_id):
        """Apply the same ERP responsibility boundary used by the Mini App."""
        return self.b.catalog_for_user(self.b.catalog(), f"telegram:{user_id}")

    def prompt(self, draft):
        step = draft["step"]
        if step in ("project", "task"):
            items = draft["choices"]
            page = draft.get("page", 0)
            start = page * 8
            rows = self.buttons(draft, [(x["label"], f"pick{start+i}") for i, x in enumerate(items[start:start+8])])
            pages = []
            if page:
                pages.append(("← Anterior", "prev"))
            if start + 8 < len(items):
                pages.append(("Siguiente →", "next"))
            rows += self.buttons(draft, pages + [("Cancelar", "cancel")])
            mode = "ERP de prueba · los mensajes se publican en el grupo real.\n\n" if self.b.ERP_MODE == "demo" else ""
            text = mode + ("1/5 · Elige el proyecto." if step == "project" else f"2/5 · {draft['project_name']}\nElige la tarea.")
            if not items:
                text = "No hay proyectos o tareas disponibles. Usa /reportar cuando el catálogo esté actualizado."
            self.send(draft, text, rows)
        elif step == "date":
            self.send(draft, "3/5 · Fecha del trabajo\nResponde a este mensaje con la fecha AAAA-MM-DD (por ejemplo, 2026-09-26) o pulsa Hoy.", self.buttons(draft, [("Hoy (hora de Ciudad de México)", "today"), ("Cancelar", "cancel")]))
        elif step == "progress":
            self.send(draft, f"4/5 · {draft['task_name']}\nAvance actual: {draft['baseProgressBps']/100:g} %\nEscribe el avance acumulado entre {draft['baseProgressBps']/100:g} y 100 (ejemplo: 65.5).\nResponde a este mensaje. /cancelar para salir.", force=True)
        elif step == "notes":
            self.send(draft, "5/5 · Describe el trabajo realizado y las observaciones (máximo 2000 caracteres).\nResponde a este mensaje. /cancelar para salir.", force=True)
        elif step == "confirm":
            self.send(draft, f"Revisa antes de registrar:\n\nProyecto: {draft['project_name']}\nTarea: {draft['task_name']}\nFecha: {draft['operationDate']}\nAvance: {draft['progressBps']/100:g} %\n\n{draft['notes']}\n\nAl confirmar se registrará el avance y se publicará en el tema del proyecto.", self.buttons(draft, [("✓ Confirmar reporte", "confirm"), ("Cambiar avance", "edit"), ("Cancelar", "cancel")]))
        elif step == "done":
            self.receipt(draft)
        else:
            self.send(draft, "Captura cancelada. Para empezar otra usa /reportar.")

    def receipt(self, draft):
        with self.b.connection() as db:
            row = db.execute("SELECT state,error FROM reports WHERE id=?", (draft["id"],)).fetchone()
        if not row:
            self.send(draft, "No hay registro confirmado. Usa /reportar para comenzar.")
            return
        labels = {"published": "Publicado en el tema del proyecto.", "demo_published": "Publicado en la simulación.", "telegram_pending": "Avance registrado. Publicación en el tema del proyecto pendiente.", "telegram_sending": "Avance registrado. Enviando al tema del proyecto.", "telegram_failed": "Avance registrado. Falló el envío al grupo; requiere revisión.", "telegram_review": "Avance registrado. Debe verificarse el envío en Telegram antes de repetir.", "erp_review": "Debe verificarse el registro en ERP antes de repetir.", "erp_rejected": "El ERP rechazó el registro."}
        self.send(draft, f"{labels.get(row['state'], 'Registro en proceso.')}\nReferencia: {draft['id']}\n\n/estado para consultar este reporte.\n/reportar para registrar otro.")

    def handle(self, update):
        callback = update.get("callback_query")
        message = callback.get("message", {}) if callback else update.get("message", {})
        user = callback.get("from", {}) if callback else message.get("from", {})
        chat = message.get("chat", {})
        if not chat.get("id") or user.get("is_bot"):
            return
        if chat.get("type") != "private" and str(chat["id"]) != str(self.b.CHAT_ID):
            return
        key = self.key(chat["id"], user.get("id"), message.get("message_thread_id"))
        draft = self.load(key)
        text = message.get("text", "").strip()
        command = text.split()[0].lower() if text.startswith("/") else ""
        if "@" in command:
            command, target = command.split("@", 1)
            if target != self.username.lower():
                return
        if callback and not str(callback.get("data", "")).startswith("r:"):
            return
        if not callback and not command:
            if not draft or draft["step"] not in ("date", "progress", "notes"):
                return
            # Never interpret unrelated group conversation as operational input.
            if chat.get("type") != "private" and message.get("reply_to_message", {}).get("message_id") != draft.get("prompt_id"):
                return
        if not self.authorized(user):
            if callback:
                self.b.telegram("answerCallbackQuery", {"callback_query_id": callback["id"], "text": "Acceso solo para miembros autorizados del grupo.", "show_alert": True})
            elif command:
                self.b.telegram("sendMessage", {"chat_id": chat["id"], "text": "Debes pertenecer al supergrupo configurado para usar este bot."})
            return
        if callback:
            self.b.telegram("answerCallbackQuery", {"callback_query_id": callback["id"]})
        uid = update["update_id"]
        if draft and uid <= draft.get("last_update", -1):
            return
        if command in ("/start", "/reportar") and getattr(self.b, "PUBLIC_URL", "").startswith("https://"):
            button = {"text": "Abrir Campo · Reportar"}
            if chat.get("type") == "private":
                button["web_app"] = {"url": self.b.PUBLIC_URL}
            else:
                button["url"] = f"https://t.me/{self.username}?start=reportar"
            data = {"chat_id": chat["id"], "text": "Abre la Mini App para elegir proyecto y tarea, capturar el avance y guardar tu reporte. Se publicará en el tema del proyecto.", "reply_markup": {"inline_keyboard": [[button]]}}
            if message.get("message_thread_id"):
                data["message_thread_id"] = message["message_thread_id"]
            self.b.telegram("sendMessage", data)
            return
        if command in ("/start", "/reportar"):
            data = self.catalog_for_user(user["id"])
            draft = {"key": key, "id": str(uuid.uuid4()), "nonce": uuid.uuid4().hex[:12], "chat": chat["id"], "thread": message.get("message_thread_id"), "user": user["id"], "name": " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))[:120], "step": "project", "last_update": uid, "page": 0, "choices": [{"id": p["id"], "label": p["name"]} for p in data["projects"]]}
            self.save(draft)
            self.prompt(draft)
            return
        if not draft:
            self.b.telegram("sendMessage", {"chat_id": chat["id"], "text": "Escribe /reportar para comenzar tu reporte."})
            return
        if time.time() - draft.get("updated", 0) > 86400:
            self.send(draft, "Tu captura venció después de 24 horas. Usa /reportar para comenzar de nuevo.")
            draft["step"] = "cancelled"
            self.save(draft)
            return
        if command in ("/continuar", "/estado", "/ayuda"):
            draft["last_update"] = uid
            self.save(draft)
            self.prompt(draft)
            return
        if command == "/cancelar":
            draft["step"] = "cancelled"
        elif callback:
            parts = callback["data"].split(":", 2)
            if len(parts) != 3 or parts[1] != draft["nonce"] or message.get("message_id") != draft.get("prompt_id"):
                return  # Old button, another user's wizard, or an already-used confirmation.
            action = parts[2]
            if action == "cancel":
                draft["step"] = "cancelled"
            elif action in ("prev", "next") and draft["step"] in ("project", "task"):
                draft["page"] = max(0, min((len(draft["choices"])-1)//8, draft.get("page", 0) + (1 if action == "next" else -1)))
            elif action.startswith("pick") and draft["step"] in ("project", "task"):
                if not action[4:].isdigit() or int(action[4:]) >= len(draft["choices"]):
                    return
                selected = draft["choices"][int(action[4:])]
                data = self.catalog_for_user(user["id"])
                if draft["step"] == "project":
                    draft.update(project_id=selected["id"], project_name=selected["label"], step="task", page=0, choices=[{"id": t["id"], "label": f"{t['code']} · {t['name']}"} for t in data["tasks"] if t["projectId"] == selected["id"]])
                else:
                    task = next((t for t in data["tasks"] if t["id"] == selected["id"] and t["projectId"] == draft["project_id"]), None)
                    if not task:
                        self.send(draft, "La tarea ya no está disponible. Usa /reportar para actualizar.")
                        return
                    draft.update(taskId=task["id"], task_name=selected["label"], baseProgressBps=task["progressBps"], step="date")
            elif action == "today" and draft["step"] == "date":
                # Mexico City is UTC-6 year round. Keep this fixed choice explicit in the UI.
                draft.update(operationDate=datetime.now(timezone(timedelta(hours=-6))).date().isoformat(), step="progress")
            elif action == "edit" and draft["step"] == "confirm":
                draft["step"] = "progress"
            elif action == "confirm" and draft["step"] == "confirm":
                try:
                    payload = {k: draft[k] for k in ("id", "taskId", "baseProgressBps", "progressBps", "notes", "operationDate")}
                    self.b.create_report(payload, f"telegram:{draft['user']}", reporter_name=draft["name"], origin="campo-telegram")
                    draft["step"] = "done"
                except self.b.Problem as error:
                    draft.update(step="done", last_update=uid)
                    self.save(draft)
                    self.send(draft, error.message + "\nEl reporte confirmado se conserva sin modificaciones. Registra una aclaración separada desde Campo.")
                    return
            else:
                return
        elif command:
            self.send(draft, "Comandos: /reportar, /continuar, /estado y /cancelar.")
            return
        elif draft["step"] == "date":
            try:
                value = date.fromisoformat(text)
                if value > datetime.now(timezone.utc).date():
                    raise ValueError()
            except ValueError:
                self.send(draft, "Fecha inválida. Usa AAAA-MM-DD y no una fecha futura.", force=True)
                return
            draft.update(operationDate=value.isoformat(), step="progress")
        elif draft["step"] == "progress":
            number = text.rstrip("%").strip().replace(",", ".")
            if not re.fullmatch(r"\d{1,3}(\.\d{1,2})?", number):
                self.send(draft, "Escribe solo el porcentaje, por ejemplo 65 o 65.50.", force=True)
                return
            value = int(Decimal(number) * 100)
            if not draft["baseProgressBps"] <= value <= 10000:
                self.send(draft, f"El avance debe estar entre {draft['baseProgressBps']/100:g} y 100 %.", force=True)
                return
            draft.update(progressBps=value, step="confirm" if draft.get("notes") else "notes")
        elif draft["step"] == "notes":
            if not text or len(text) > 2000:
                self.send(draft, "Envía observaciones en texto de entre 1 y 2000 caracteres.", force=True)
                return
            draft.update(notes=text, step="confirm")
        else:
            return
        draft.update(last_update=uid, input_message=message.get("message_id"))
        self.save(draft)
        self.prompt(draft)

    def run(self):
        delay = 2
        while True:
            try:
                info = self.b.telegram("getWebhookInfo", {})
                if info.get("url"):
                    print("Telegram: hay un webhook activo; no se modificó. Desactívalo antes de usar polling.", flush=True)
                    time.sleep(30)
                    continue
                self.username = self.b.telegram("getMe", {})["username"]
                if getattr(self.b, "PUBLIC_URL", "").startswith("https://"):
                    self.b.telegram("setChatMenuButton", {"menu_button": {"type": "web_app", "text": "Reportar", "web_app": {"url": self.b.PUBLIC_URL}}})
                self.b.telegram("setMyCommands", {"commands": [
                    {"command": "reportar", "description": "Abrir la Mini App de reportes"},
                    {"command": "continuar", "description": "Retomar la captura pendiente"},
                    {"command": "estado", "description": "Consultar el último reporte"},
                    {"command": "cancelar", "description": "Cancelar la captura actual"},
                ]})
                print(f"Telegram: captura activa en @{self.username}", flush=True)
                break
            except Exception as error:
                print(f"Telegram startup: {type(error).__name__}", flush=True)
                time.sleep(min(delay, 30))
                delay *= 2
        while True:
            try:
                with self.b.connection() as db:
                    row = db.execute("SELECT value FROM settings WHERE key=?", (self.offset_key,)).fetchone()
                offset = int(row[0]) if row else 0
                updates = self.b.telegram("getUpdates", {"offset": offset, "timeout": 10, "allowed_updates": ["message", "callback_query"]})
                for update in updates:
                    try:
                        self.handle(update)
                    except Exception as error:
                        # Draft/report writes are durable. /continuar recovers a lost conversational prompt.
                        print(f"Telegram update {update.get('update_id')}: {type(error).__name__}; usa /continuar", flush=True)
                    with self.b.connection() as db:
                        db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (self.offset_key, str(update["update_id"] + 1)))
                delay = 2
            except Exception as error:
                print(f"Telegram polling: {type(error).__name__}", flush=True)
                time.sleep(min(delay, 30))
                delay = min(delay * 2, 30)

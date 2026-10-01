"""Campo: prototype server, persistent outbox and ERP/Telegram adapters (stdlib only)."""
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
from contextlib import contextmanager
from datetime import date, datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from backend.admin import AdminError, AdminService
from backend.access import AccessService
from backend.auth import AuthError, AuthService
from backend.audit import AuditService
from backend.database import DatabaseService
from backend.delivery import DeliveryService
from backend.employees import EmployeeService, ROLES
from backend.erp import ErpClient, task_responsible as normalize_task_responsible
from backend.health import HealthService
from backend.http_client import RemoteFailure, request_json
from backend.media import MediaService, valid_id as media_valid_id
from backend.reports import ReportService
from backend.security import pin_hash, pin_in_use, verify_pin
from backend.telegram import TelegramClient, safe_caption as telegram_safe_caption
from backend.validation import ValidationService
from backend.config import load_config

ROOT = Path(__file__).parent
CONFIG = load_config(ROOT, os.environ)
DATA = CONFIG.data_dir
DB = DATA / "campo.sqlite3"
LOCK = threading.RLock()
ERP_MODE = CONFIG.erp_mode
TG_MODE = CONFIG.telegram_mode
ERP_URL = CONFIG.erp_url
ERP_KEY = CONFIG.erp_key
BOT_TOKEN = CONFIG.bot_token
CHAT_ID = CONFIG.chat_id
USER = CONFIG.user
APP_RESPONSIBLE_NAME = CONFIG.responsible_name
USER_RESPONSIBLE_MAP = CONFIG.responsible_map
PASSWORD = CONFIG.password
PUBLIC_URL = CONFIG.public_url
ALLOWED = set(CONFIG.allowed_users)
ATTEMPTS = {}


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


class Problem(Exception):
    def __init__(self, status, message, code="error", extra=None):
        self.status, self.message, self.code, self.extra = status, message, code, extra or {}


remote = request_json


TELEGRAM = TelegramClient(
    lambda url, payload=None, headers=None: remote(url, payload, headers),
    lambda: {"token": BOT_TOKEN, "chat_id": CHAT_ID},
)


def telegram(method, payload):
    return TELEGRAM.request(method, payload)


def safe_caption(text, limit=1024):
    return telegram_safe_caption(text, limit)


def telegram_photo(photo, thread_id, message_id=None, caption="", reply_markup=None):
    return TELEGRAM.photo(photo, thread_id, message_id, caption, reply_markup)


def telegram_media_group(photos, thread_id, caption=""):
    return TELEGRAM.media_group(photos, thread_id, caption)


valid_id = media_valid_id
MEDIA = MediaService(connection, LOCK, Problem)
HEALTH = HealthService(connection, lambda: {"erp_mode": ERP_MODE, "erp_url": ERP_URL, "erp_key": ERP_KEY, "telegram_mode": TG_MODE, "bot_token": BOT_TOKEN, "chat_id": CHAT_ID})


def save_photo(body, user):
    return MEDIA.save_photo(body, user)


def health():
    return HEALTH.check()


VALIDATION = ValidationService(connection, Problem)


def validate_details(payload, user, rid):
    return VALIDATION.validate_details(payload, user, rid)


def field_message(clean, project, task, user):
    return VALIDATION.field_message(clean, project, task, user)


DATABASE = DatabaseService(DATA, connection, now)


def initialize():
    return DATABASE.initialize(ERP_MODE, TG_MODE, ERP_URL, CHAT_ID)


EMPLOYEES = EmployeeService(connection, LOCK, Problem)


def employees():
    return EMPLOYEES.list()


def save_employee(body, delete=False):
    return EMPLOYEES.save(body, delete)


def validate_crew(value):
    return EMPLOYEES.validate_crew(value)


ERP = ErpClient(
    lambda url, payload=None, headers=None: remote(url, payload, headers),
    connection,
    LOCK,
    employees,
    now,
    lambda: {"mode": ERP_MODE, "url": ERP_URL, "key": ERP_KEY, "allow_http": os.getenv("ERP_ALLOW_HTTP") == "true"},
)


def erp(path, payload=None):
    return ERP.request(path, payload)


def catalog(refresh=True):
    try:
        return ERP.catalog(refresh)
    except RemoteFailure as error:
        raise Problem(502, getattr(error, "message", "Formato inesperado de la API ERP.")) from None


def public_report(row):
    result = dict(row)
    result["payload"] = json.loads(result["payload"])
    return result


def configured_profile(user):
    """Resolve the stable ERP employee relation for an application user."""
    try:
        mapping = json.loads(USER_RESPONSIBLE_MAP) if USER_RESPONSIBLE_MAP else {}
    except (ValueError, TypeError):
        mapping = {}
    value = mapping.get(user, {}) if isinstance(mapping, dict) else {}
    return value if isinstance(value, dict) else {}


AUTH = AuthService(
    connection,
    LOCK,
    lambda: ATTEMPTS,
    lambda: {
        "bot_token": BOT_TOKEN,
        "chat_id": CHAT_ID,
        "allowed": ALLOWED,
        "password_login_enabled": os.getenv("PASSWORD_LOGIN_ENABLED", "true") == "true",
        "password": PASSWORD,
        "user": USER,
        "app_responsible_name": APP_RESPONSIBLE_NAME,
        "cookie_secure": os.getenv("COOKIE_SECURE") == "true",
    },
    pin_hash,
    verify_pin,
    lambda method, payload: telegram(method, payload),
    configured_profile,
    now,
)


task_responsible = normalize_task_responsible


ACCESS = AccessService(connection, erp, task_responsible, Problem, lambda: USER, lambda: ERP_MODE)


def profile_for(user):
    return ACCESS.profile_for(user)


def is_admin(user):
    if user != USER:
        return False
    with connection() as db:
        return not db.execute("SELECT 1 FROM app_users WHERE username=?", (user,)).fetchone()


def catalog_for_user(data, user):
    return ACCESS.catalog_for_user(data, user)


AUDIT = AuditService(connection, now, lambda: USER)
ADMIN = AdminService(connection, catalog, task_responsible, pin_hash, pin_in_use, now, USER, AUDIT)


def _admin_result(operation, *args):
    try:
        return operation(*args)
    except AdminError as error:
        raise Problem(error.status, error.message) from None


def admin_users():
    return _admin_result(ADMIN.users)


def admin_audit():
    return _admin_result(ADMIN.audit_entries)


def admin_responsibles():
    return _admin_result(ADMIN.responsibles)


def save_admin_user(body):
    return _admin_result(ADMIN.save, body)


def delete_admin_user(body):
    return _admin_result(ADMIN.delete, body)


def toggle_admin_user(body):
    return _admin_result(ADMIN.toggle, body)


REPORTS = ReportService(
    connection,
    LOCK,
    Problem,
    now,
    profile_for,
    lambda: catalog(),
    lambda data, user: catalog_for_user(data, user),
    task_responsible,
    validate_crew,
    validate_details,
    field_message,
    public_report,
    lambda path, payload=None: erp(path, payload),
    lambda: {"user": USER, "erp_mode": ERP_MODE, "enforce_responsible_access": os.getenv("ENFORCE_RESPONSIBLE_ACCESS", "false").lower() == "true"},
    ROLES,
)


def create_report(payload, user, reporter_name=None, origin="campo-pwa"):
    return REPORTS.create(payload, user, reporter_name, origin)


DELIVERY = DeliveryService(
    connection,
    LOCK,
    lambda: {"mode": TG_MODE, "chat_id": CHAT_ID, "public_url": PUBLIC_URL},
    lambda method, payload: telegram(method, payload),
    lambda photo, thread_id, message_id=None, caption="", reply_markup=None: telegram_photo(photo, thread_id, message_id, caption, reply_markup),
    lambda photos, thread_id, caption="": telegram_media_group(photos, thread_id, caption),
)


def deliver():
    return DELIVERY.deliver()


def worker():
    while True:
        try:
            deliver()
        except Exception as error:
            print(f"Worker error: {type(error).__name__}", flush=True)
        time.sleep(4)


class Handler(BaseHTTPRequestHandler):
    server_version = "Campo"

    def log_message(self, fmt, *args):
        # Paths/status only. Do not log tokens, cookies, request bodies or query parameters.
        print(f"{self.command} {urllib.parse.urlsplit(self.path).path}", flush=True)

    def json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            limit = 2100000 if urllib.parse.urlsplit(self.path).path == "/api/photos" else 32000
            if not 0 < length <= limit:
                raise ValueError()
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, TypeError):
            raise Problem(400, "Solicitud inválida.") from None

    def session(self):
        try:
            return AUTH.session(self.headers.get("Cookie", ""))
        except AuthError as error:
            raise Problem(error.status, error.message) from None

    def login(self, body):
        try:
            payload, cookie = AUTH.login(body, self.client_address[0])
        except AuthError as error:
            raise Problem(error.status, error.message) from None
        return self.json(200, payload, cookie)

    def do_GET(self):
        try:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                status, payload = health()
                return self.json(status, payload)
            if path.startswith("/api/"):
                user = self.session()
                if path.startswith("/api/admin/") and not is_admin(user):
                    raise Problem(403, "Solo el administrador puede gestionar usuarios.")
                if path == "/api/admin/users":
                    return self.json(200, {"users": admin_users()})
                if path == "/api/admin/audit":
                    return self.json(200, {"entries": admin_audit()})
                if path == "/api/admin/responsibles":
                    return self.json(200, {"responsibles": admin_responsibles()})
                if path.startswith("/api/photos/"):
                    pid = path.rsplit("/", 1)[-1]
                    with connection() as db:
                        photo = db.execute("SELECT data FROM photos WHERE id=? AND user=?", (pid, user)).fetchone()
                    if not photo:
                        raise Problem(404, "Fotografía no disponible.")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(photo["data"])))
                    self.send_header("Cache-Control", "private, no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(photo["data"])
                    return
                if path == "/api/me":
                    profile = profile_for(user)
                    return self.json(200, {"user": user, "responsibleName": profile.get("responsible_name", ""), "isAdmin": is_admin(user)})
                if path == "/api/config":
                    scope = "Todos los proyectos de la integración" if is_admin(user) else "Tareas asignadas al empleado ERP"
                    return self.json(200, {"erpMode": ERP_MODE, "telegramMode": TG_MODE, "telegramConfigured": bool(BOT_TOKEN and CHAT_ID), "publicUrl": PUBLIC_URL, "authScope": scope})
                if path == "/api/employees":
                    return self.json(200, {"employees": employees()})
                if path == "/api/catalog":
                    return self.json(200, catalog_for_user(catalog(), user))
                if path == "/api/reports":
                    with LOCK, connection() as db:
                        reports = [public_report(row) for row in db.execute("SELECT * FROM reports WHERE user=? ORDER BY created DESC LIMIT 500", (user,))]
                        topics = [dict(row) for row in db.execute("SELECT * FROM topics ORDER BY title")]
                    with connection() as db:
                        clarifications = [dict(r) for r in db.execute("SELECT * FROM clarifications WHERE user=? ORDER BY created", (user,))]
                    return self.json(200, {"reports": reports, "topics": topics, "clarifications": clarifications})
                raise Problem(404, "Ruta no encontrada.")
            files = {"/actualizar": "refresh.html", "/refresh.js": "refresh.js", "/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/storage.js": "../frontend/storage.js", "/sync.js": "../frontend/sync.js", "/auth.js": "../frontend/auth.js", "/admin.js": "../frontend/admin.js", "/style.css": "style.css", "/sw.js": "sw.js", "/manifest.webmanifest": "manifest.webmanifest", "/icon.svg": "icon.svg", "/icon-192.png": "icon-192.png", "/icon-512.png": "icon-512.png", "/api-client.js": "../frontend/api.js"}
            if path not in files:
                raise Problem(404, "Archivo no encontrado.")
            file = ROOT / "public" / files[path]
            body = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", {".js": "text/javascript", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml"}.get(file.suffix, mimetypes.guess_type(str(file))[0] or "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' https://telegram.org; connect-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)
        except Problem as error:
            self.json(error.status, {"error": error.message, "code": error.code, **error.extra})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.json(500, {"error": "Error interno del servidor."})

    def do_POST(self):
        try:
            # Same-origin JSON requests only; no CORS or cross-origin state changes.
            origin = self.headers.get("Origin")
            allowed = {"http://" + self.headers.get("Host", ""), "https://" + self.headers.get("Host", "")}
            if PUBLIC_URL:
                allowed.add(PUBLIC_URL)
            if origin and origin not in allowed:
                raise Problem(403, "Origen no autorizado.")
            if "application/json" not in self.headers.get("Content-Type", ""):
                raise Problem(415, "Se requiere JSON.")
            body = self.body()
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/login":
                return self.login(body)
            user = self.session()
            if path.startswith("/api/admin/") and not is_admin(user):
                raise Problem(403, "Solo el administrador puede gestionar usuarios.")
            if path == "/api/admin/users":
                return self.json(200, save_admin_user(body))
            if path == "/api/admin/users/delete":
                return self.json(200, delete_admin_user(body))
            if path == "/api/admin/users/toggle":
                return self.json(200, toggle_admin_user(body))
            if path == "/api/logout":
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                token_hash = hashlib.sha256(cookie["campo_session"].value.encode()).hexdigest()
                with connection() as db:
                    db.execute("DELETE FROM sessions WHERE token=?", (token_hash,))
                return self.json(200, {"ok": True}, "campo_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
            if path == "/api/clarifications":
                cid, rid, note = body.get("id"), body.get("reportId"), body.get("note")
                if not valid_id(cid) or not valid_id(rid) or not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000:
                    raise Problem(400, "Escribe una aclaración de hasta 2000 caracteres.")
                with LOCK, connection() as db:
                    if not (db.execute("SELECT 1 FROM reports WHERE id=? AND user=?", (rid,user)).fetchone() or db.execute("SELECT 1 FROM submissions WHERE id=? AND user=?", (rid,user)).fetchone()):
                        raise Problem(404, "Sincroniza primero el reporte original.")
                    prior = db.execute("SELECT * FROM clarifications WHERE id=?", (cid,)).fetchone()
                    if prior and (prior["user"] != user or prior["report_id"] != rid or prior["note"] != note.strip()):
                        raise Problem(409, "La aclaración confirmada no se puede modificar.")
                    db.execute("INSERT OR IGNORE INTO clarifications VALUES (?,?,?,?,?)", (cid,rid,user,note.strip(),now()))
                return self.json(200, {"ok": True})
            if path == "/api/photos":
                return self.json(200, save_photo(body, user))
            if path in ("/api/employees/save", "/api/employees/delete"):
                return self.json(200, save_employee(body, delete=path.endswith("/delete")))
            if path == "/api/reports":
                return self.json(200, create_report(body, user))
            if path == "/api/retry-telegram":
                with LOCK, connection() as db:
                    db.execute("UPDATE reports SET state='telegram_pending',error=NULL WHERE id=? AND user=? AND state='telegram_failed'", (body.get("id"), user))
                return self.json(200, {"ok": True})
            raise Problem(404, "Ruta no encontrada.")
        except Problem as error:
            self.json(error.status, {"error": error.message, "code": error.code, **error.extra})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            print(f"Request error: {type(error).__name__}", flush=True)
            self.json(500, {"error": "Error interno. El pendiente se conserva; reintenta con el mismo identificador."})


if __name__ == "__main__":
    initialize()
    threading.Thread(target=worker, daemon=True).start()
    if TG_MODE == "live" and os.getenv("TELEGRAM_POLLING", "true").lower() == "true":
        from telegram_bot import ReportBot
        bot = ReportBot(sys.modules[__name__])
        threading.Thread(target=bot.run, daemon=True).start()
    print(f"Campo en puerto {os.getenv('PORT', '8080')} | ERP {ERP_MODE} | Telegram {TG_MODE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()

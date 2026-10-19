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
from backend.reminders import Reminders
from backend.push import Push, validate_subscription
from backend.delivery import DeliveryService
from backend.monitor import MonitorService
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
from backend.journal import JournalService
from backend.evidence import EvidenceService

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
HEALTH = HealthService(connection, lambda: {"erp_mode": ERP_MODE, "erp_url": ERP_URL, "erp_key": current_erp_key(), "telegram_mode": TG_MODE, "bot_token": BOT_TOKEN, "chat_id": CHAT_ID})


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
    DATABASE.initialize(ERP_MODE, TG_MODE, ERP_URL, CHAT_ID)
    REMINDERS.initialize()


EMPLOYEES = EmployeeService(connection, LOCK, Problem)


def employees():
    return EMPLOYEES.list()


def save_employee(body, delete=False):
    result = EMPLOYEES.save(body, delete)
    audit_event("employee_deleted" if delete else "employee_saved", str(result.get("id") or body.get("id") or ""), {"name": result.get("name") or body.get("name", ""), "roles": result.get("roles") or body.get("roles", [])})
    return result


def validate_crew(value):
    return EMPLOYEES.validate_crew(value)


ERP = ErpClient(
    lambda url, payload=None, headers=None: remote(url, payload, headers),
    connection,
    LOCK,
    employees,
    now,
    lambda: {"mode": ERP_MODE, "url": ERP_URL, "key": current_erp_key(), "allow_http": os.getenv("ERP_ALLOW_HTTP") == "true"},
)


def erp(path, payload=None):
    return ERP.request(path, payload)

def current_erp_key():
    with connection() as db:
        row = db.execute("SELECT value FROM settings WHERE key='erp_api_key'").fetchone()
    return row[0] if row and row[0] else ERP_KEY

def save_erp_key(value):
    value = str(value or "").strip()
    if not 20 <= len(value) <= 300 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise Problem(400, "La API key no tiene un formato válido.")
    with LOCK, connection() as db:
        db.execute("INSERT INTO settings(key,value) VALUES('erp_api_key',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (value,))
    audit_event("erp_key_updated", "erp", {"length": len(value)})
    return {"ok": True, "configured": True, "masked": value[:6] + "…" + value[-4:]}

def erp_key_status():
    value = current_erp_key()
    return {"configured": bool(value), "masked": value[:6] + "…" + value[-4:] if value else ""}


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

def audit_event(action, target, details):
    AUDIT.record(action, target, details)

MEDIA = MediaService(connection, LOCK, Problem, audit_event)
ADMIN = AdminService(connection, catalog, task_responsible, pin_hash, pin_in_use, now, USER, AUDIT)

MONITOR = MonitorService(connection, LOCK, now, AUDIT, USER)


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
    audit_event,
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
    audit_event,
)


def deliver():
    EvidenceService(connection, LOCK, ERP, lambda: ERP_MODE).process()
    result = DELIVERY.deliver()
    MEDIA.purge_delivered()
    return result


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
        audit_event("session_login", payload.get("user", ""), {"user": payload.get("user", ""), "ip": self.client_address[0]})
        return self.json(200, payload, cookie)

    def do_GET(self):
        try:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                status, payload = health()
                return self.json(status, payload)
            if path.startswith("/api/"):
                user = self.session()
                if path == '/api/notifications/key':
                    return self.json(200, {'publicKey': PUSH.public_key()})
                if path.startswith("/api/admin/") and not path.startswith("/api/admin/journal/") and not is_admin(user):
                    raise Problem(403, "Solo el administrador puede gestionar usuarios.")
                if path.startswith('/api/admin/journal/'):
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    param = lambda name: (query.get(name) or [''])[0]
                    journal = JournalService(ERP)
                    try:
                        if path == '/api/admin/journal/projects':
                            return self.json(200, journal.projects())
                        if path == '/api/admin/journal/entries':
                            return self.json(200, journal.entries(param('project')))
                        if path in ('/api/admin/journal/preview', '/api/admin/journal/file'):
                            data, mime = journal.attachment(param('project'), param('log'), param('attachment'), path.endswith('/preview'))
                            self.send_response(200)
                            self.send_header('Content-Type', mime)
                            self.send_header('Content-Length', str(len(data)))
                            self.send_header('Cache-Control', 'private, no-store')
                            self.send_header('X-Content-Type-Options', 'nosniff')
                            if path.endswith('/file'):
                                extension = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[mime]
                                self.send_header('Content-Disposition', 'attachment; filename="evidencia.' + extension + '"')
                            self.end_headers()
                            self.wfile.write(data)
                            return
                    except ValueError as error:
                        raise Problem(400, str(error)) from None
                    except LookupError:
                        raise Problem(404, 'Evidencia no encontrada.') from None
                    except (RemoteFailure, TypeError) as error:
                        raise Problem(502, getattr(error, 'message', 'Respuesta ERP inesperada.')) from None
                    raise Problem(404, 'Ruta no encontrada.')
                if path == "/api/admin/users":
                    return self.json(200, {"users": admin_users()})
                if path == "/api/admin/audit":
                    return self.json(200, {"entries": admin_audit()})
                if path == "/api/admin/integration/erp-key":
                    return self.json(200, erp_key_status())
                if path == "/api/admin/monitor":
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    hours = min(max(int((query.get("hours") or ["24"])[0]), 1), 720) if (query.get("hours") or ["24"])[0].isdigit() else 24
                    return self.json(200, MONITOR.snapshot((query.get("state") or ["all"])[0], hours))
                if path == "/api/admin/responsibles":
                    return self.json(200, {"responsibles": admin_responsibles()})
                if path.startswith("/api/photos/"):
                    pid = path.rsplit("/", 1)[-1]
                    with connection() as db:
                        photo = db.execute("SELECT data,attachment_id FROM photos WHERE id=? AND user=?", (pid, user)).fetchone()
                    if not photo:
                        raise Problem(404, "Fotografía no disponible.")
                    data = photo['data']
                    if not data:
                        if not photo['attachment_id'] or photo['attachment_id'].startswith('demo-'):
                            raise Problem(404, "Fotografía no disponible.")
                        try:
                            data = ERP.attachment_file(photo['attachment_id'])
                        except RemoteFailure as error:
                            raise Problem(502, error.message) from None
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "private, no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(data)
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
            files = {"/actualizar": "refresh.html", "/refresh.js": "refresh.js", "/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/storage.js": "../frontend/storage.js", "/sync.js": "../frontend/sync.js", "/auth.js": "../frontend/auth.js", "/admin.js": "../frontend/admin.js", "/monitor.js": "../frontend/monitor.js", "/style.css": "style.css", "/sw.js": "sw.js", "/manifest.webmanifest": "manifest.webmanifest", "/icon.svg": "icon.svg", "/icon-192.png": "icon-192.png", "/icon-512.png": "icon-512.png", "/apple-touch-icon.png": "apple-touch-icon.png", "/agrokool-mark.png": "agrokool-mark.png", "/agrokool-mark-white.png": "agrokool-mark-white.png", "/agrokool-logo.png": "agrokool-logo.png", "/agrokool-logo-white.png": "agrokool-logo-white.png", "/isologo-agk.png": "isologo-agk.png", "/agrokool-verde.png": "agrokool-verde.png", "/agrokool-gold.png": "agrokool-gold.png", "/agrokool-horizontal.png": "agrokool-horizontal.png", "/agrokool-vertical.png": "agrokool-vertical.png", "/agrokool-symbol.png": "agrokool-symbol.png", "/api-client.js": "../frontend/api.js"}
            files.update({'/journal.js': '../frontend/journal.js', '/journal.css': 'journal.css'})
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
            if path == '/api/notifications/status':
                with connection() as db:
                    registered = db.execute('SELECT 1 FROM push_subscriptions WHERE endpoint=? AND user=?', (body.get('endpoint'), user)).fetchone()
                return self.json(200, {'subscribed': bool(registered)})
            if path == '/api/notifications/subscribe':
                try:
                    subscription = validate_subscription(body)
                except ValueError as error:
                    raise Problem(400, str(error)) from None
                with connection() as db:
                    existing = db.execute('SELECT user FROM push_subscriptions WHERE endpoint=?', (subscription['endpoint'],)).fetchone()
                    if existing and existing['user'] != user:
                        raise Problem(409, 'Desactiva los avisos de la cuenta anterior en este dispositivo.')
                    db.execute('INSERT OR REPLACE INTO push_subscriptions VALUES (?,?,?)', (subscription['endpoint'], user, json.dumps(subscription)))
                return self.json(200, {'ok': True})
            if path == '/api/notifications/unsubscribe':
                with connection() as db:
                    db.execute('DELETE FROM push_subscriptions WHERE endpoint=? AND user=?', (body.get('endpoint'), user))
                return self.json(200, {'ok': True})
            if path.startswith("/api/admin/") and not is_admin(user):
                raise Problem(403, "Solo el administrador puede gestionar usuarios.")
            if path == '/api/admin/notifications/test':
                with connection() as db:
                    subscriptions = db.execute('''SELECT s.payload FROM push_subscriptions s
                        LEFT JOIN app_users u ON u.username=s.user
                        WHERE u.active=1 OR s.user=?''', (USER,)).fetchall()
                sent = failed = 0
                for subscription in subscriptions:
                    try:
                        PUSH.send(json.loads(subscription['payload']), {
                            'title': 'Campo · Notificación de prueba',
                            'body': 'Prueba del administrador. No modifica reportes ni publica en Telegram.',
                            'tag': 'campo-prueba-admin',
                        })
                        sent += 1
                    except Exception:
                        failed += 1
                message = (f'Prueba: {sent} aceptadas por el proveedor, {failed} fallidas, de {len(subscriptions)} dispositivos registrados. La aceptación no confirma la recepción en pantalla.'
                           if subscriptions else 'No hay dispositivos registrados de usuarios activos. Activa la campana en los dispositivos que recibirán los avisos.')
                return self.json(200, {'ok': failed == 0, 'sent': sent, 'failed': failed, 'total': len(subscriptions), 'message': message})
            if path == "/api/admin/users":
                return self.json(200, save_admin_user(body))
            if path == "/api/admin/users/delete":
                return self.json(200, delete_admin_user(body))
            if path == "/api/admin/monitor/retry":
                return self.json(200, MONITOR.retry_telegram(body.get("id", "")))
            if path == "/api/admin/monitor/resolve":
                try:
                    return self.json(200, MONITOR.resolve(body.get("id", ""), body.get("decision", ""), body.get("note", "")))
                except ValueError as error:
                    raise Problem(400, str(error)) from None
            if path == "/api/admin/integration/erp-key":
                return self.json(200, save_erp_key(body.get("apiKey", "")))
            if path == "/api/admin/users/toggle":
                return self.json(200, toggle_admin_user(body))
            if path == "/api/logout":
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                token_hash = hashlib.sha256(cookie["campo_session"].value.encode()).hexdigest()
                session_user = self.session()
                with connection() as db:
                    db.execute("DELETE FROM sessions WHERE token=?", (token_hash,))
                audit_event("session_logout", session_user, {"user": session_user})
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
                audit_event("clarification_added", cid, {"user": user, "report_id": rid})
                return self.json(200, {"ok": True})
            if path == "/api/photos":
                return self.json(200, save_photo(body, user))
            if path in ("/api/employees/save", "/api/employees/delete"):
                return self.json(200, save_employee(body, delete=path.endswith("/delete")))
            if path == "/api/reports":
                return self.json(200, create_report(body, user))
            if path == "/api/retry-telegram":
                with LOCK, connection() as db:
                    changed=db.execute("UPDATE reports SET state='telegram_pending',error=NULL WHERE id=? AND user=? AND state='telegram_failed'", (body.get("id"), user)).rowcount
                if changed:audit_event("user_retry_telegram", str(body.get("id", "")), {"user": user})
                return self.json(200, {"ok": bool(changed)})
            raise Problem(404, "Ruta no encontrada.")
        except Problem as error:
            self.json(error.status, {"error": error.message, "code": error.code, **error.extra})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            print(f"Request error: {type(error).__name__}", flush=True)
            self.json(500, {"error": "Error interno. El pendiente se conserva; reintenta con el mismo identificador."})


REMINDERS = Reminders(connection, ERP, telegram, CHAT_ID)
PUSH = Push(DATA, PUBLIC_URL)


def reminder_worker():
    while True:
        try:
            REMINDERS.tick(datetime.now(timezone.utc), PUSH.send)
        except Exception as error:
            print('Reminder worker:', type(error).__name__, flush=True)
        time.sleep(60)


if __name__ == "__main__":
    initialize()
    threading.Thread(target=worker, daemon=True).start()
    if ERP_MODE == 'live' and TG_MODE == 'live' and os.getenv('REMINDERS_ENABLED', 'false') == 'true':
        PUSH.public_key()
        threading.Thread(target=reminder_worker, daemon=True).start()
    if TG_MODE == "live" and os.getenv("TELEGRAM_POLLING", "true").lower() == "true":
        from telegram_bot import ReportBot
        bot = ReportBot(sys.modules[__name__])
        threading.Thread(target=bot.run, daemon=True).start()
    print(f"Campo en puerto {os.getenv('PORT', '8080')} | ERP {ERP_MODE} | Telegram {TG_MODE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()

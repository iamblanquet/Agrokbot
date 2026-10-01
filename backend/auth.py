"""Session, PIN and Telegram authentication services."""
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse
from http.cookies import SimpleCookie


class AuthError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


class AuthService:
    def __init__(self, connection, lock, attempts, config, pin_hash, verify_pin, telegram, configured_profile, now):
        self.connection = connection
        self.lock = lock
        self.attempts = attempts
        self.config = config
        self.pin_hash = pin_hash
        self.verify_pin = verify_pin
        self.telegram = telegram
        self.configured_profile = configured_profile
        self.now = now

    def session(self, cookie_header):
        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header or "")
            token = cookies["campo_session"].value
        except Exception:
            raise AuthError(401, "Inicia sesión para sincronizar.") from None
        with self.connection() as db:
            row = db.execute("SELECT s.user FROM sessions s LEFT JOIN app_users u ON u.username=s.user WHERE s.token=? AND s.expires>? AND (u.username IS NULL OR u.active=1)", (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if not row:
            raise AuthError(401, "Tu sesión venció. Inicia sesión para sincronizar; tus pendientes se conservan.")
        return row["user"]

    def login(self, body, ip):
        self._check_attempt(ip)
        settings = self.config()
        init_data = body.get("initData")
        if init_data:
            raise AuthError(403, "El acceso requiere el PIN de la cuenta. Telegram no sustituye el inicio de sesión.")
        if not settings["password_login_enabled"]:
            raise AuthError(403, "El acceso por PIN está deshabilitado en el servidor.")
        user, responsible_name, employee_number, assignment_id = self._pin_identity(body, settings)

        responsible_name = self.configured_profile(user).get("name") or responsible_name
        configured = self.configured_profile(user)
        employee_number = str(configured.get("employeeNumber") or employee_number)
        assignment_id = str(configured.get("assignmentId") or assignment_id)
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user, time.time() + 7 * 86400))
            if responsible_name or employee_number or assignment_id:
                db.execute("INSERT INTO user_profiles(user,responsible_name,employee_number,assignment_id,updated) VALUES (?,?,?,?,?) ON CONFLICT(user) DO UPDATE SET responsible_name=excluded.responsible_name,employee_number=excluded.employee_number,assignment_id=excluded.assignment_id,updated=excluded.updated", (user, responsible_name, employee_number, assignment_id, self.now()))
            is_admin = user == settings["user"] and not db.execute("SELECT 1 FROM app_users WHERE username=?", (user,)).fetchone()
        secure = "; Secure" if settings["cookie_secure"] else ""
        same_site = "None" if secure else "Strict"
        return {"user": user, "isAdmin": bool(is_admin)}, f"campo_session={token}; HttpOnly; SameSite={same_site}; Path=/; Max-Age=604800{secure}"

    def _check_attempt(self, ip):
        with self.lock:
            attempts = self.attempts()
            recent = [t for t in attempts.get(ip, []) if time.time() - t < 60]
            if len(recent) >= 10:
                raise AuthError(429, "Demasiados intentos. Espera un minuto.")
            attempts[ip] = recent + [time.time()]

    def _telegram_identity(self, init_data, settings):
        if not settings["bot_token"] or not isinstance(init_data, str):
            raise AuthError(401, "Acceso de Telegram no configurado.")
        params = dict(urllib.parse.parse_qsl(init_data))
        received_hash = params.pop("hash", "")
        check = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
        secret = hmac.new(b"WebAppData", settings["bot_token"].encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        try:
            age = time.time() - int(params.get("auth_date", 0))
            tg_user = json.loads(params.get("user", "{}"))
            uid = str(tg_user["id"])
        except (ValueError, KeyError, TypeError):
            raise AuthError(401, "Identidad de Telegram inválida.") from None
        if not hmac.compare_digest(expected, received_hash) or not -30 <= age <= 3600 or (settings["allowed"] and uid not in settings["allowed"]):
            raise AuthError(403, "Usuario de Telegram no autorizado o sesión vencida.")
        if not settings["allowed"]:
            member = self.telegram("getChatMember", {"chat_id": settings["chat_id"], "user_id": int(uid)})
            if member.get("status") not in ("creator", "administrator", "member") and not (member.get("status") == "restricted" and member.get("is_member")):
                raise AuthError(403, "Debes pertenecer al grupo de reportes para entrar.")
        name = " ".join(str(tg_user.get(key, "")).strip() for key in ("first_name", "last_name") if str(tg_user.get(key, "")).strip())
        return "telegram:" + uid, name

    def _pin_identity(self, body, settings):
        login_pin = str(body.get("password", ""))
        with self.connection() as db:
            app_user = next((row for row in db.execute("SELECT * FROM app_users WHERE active=1") if self.verify_pin(login_pin, row["pin_hash"])), None)
        if app_user:
            if not app_user["pin_hash"].startswith("scrypt$"):
                with self.connection() as db:
                    db.execute("UPDATE app_users SET pin_hash=? WHERE username=?", (self.pin_hash(login_pin), app_user["username"]))
            return app_user["username"], app_user["responsible_name"], app_user["employee_number"], app_user["assignment_id"]
        if not hmac.compare_digest(login_pin.encode(), settings["password"].encode()):
            raise AuthError(401, "PIN incorrecto.")
        return settings["user"], settings["app_responsible_name"], "", ""

"""Inicialización, migraciones ligeras y datos demo de la base local."""
import json


class DatabaseService:
    """Prepara el almacenamiento persistente sin mezclarlo con HTTP."""

    def __init__(self, data_path, connection, now):
        self.data_path = data_path
        self.connection = connection
        self.now = now

    def initialize(self, erp_mode, telegram_mode, erp_url, chat_id):
        if erp_mode not in ("demo", "live") or telegram_mode not in ("demo", "live"):
            raise RuntimeError("ERP_MODE y TELEGRAM_MODE deben ser demo o live")
        self.data_path.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, user TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS clarifications (id TEXT PRIMARY KEY, report_id TEXT NOT NULL, user TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS catalog (kind TEXT, id TEXT, payload TEXT, PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS employees (id TEXT PRIMARY KEY, name TEXT NOT NULL, roles TEXT NOT NULL, version INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS employee_versions (id TEXT, version INTEGER, name TEXT NOT NULL, roles TEXT NOT NULL, PRIMARY KEY(id,version));
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user TEXT, expires REAL);
            CREATE TABLE IF NOT EXISTS user_profiles (user TEXT PRIMARY KEY, responsible_name TEXT NOT NULL DEFAULT '', employee_number TEXT NOT NULL DEFAULT '', assignment_id TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS app_users (username TEXT PRIMARY KEY, pin_hash TEXT NOT NULL, responsible_name TEXT NOT NULL, employee_number TEXT NOT NULL, assignment_id TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log (id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, details TEXT NOT NULL, created TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS app_users_assignment ON app_users(assignment_id);
            CREATE INDEX IF NOT EXISTS app_users_employee ON app_users(employee_number);
            CREATE TABLE IF NOT EXISTS reports (
              id TEXT PRIMARY KEY, user TEXT NOT NULL, task_id TEXT NOT NULL, project_id TEXT NOT NULL,
              payload TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL,
              erp_log_id TEXT, message_id TEXT, thread_id TEXT, error TEXT, message TEXT);
            CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, report_id TEXT NOT NULL, user TEXT NOT NULL, data BLOB NOT NULL, digest TEXT NOT NULL, message_id TEXT);
            CREATE INDEX IF NOT EXISTS photos_report ON photos(report_id);
            CREATE TABLE IF NOT EXISTS topics (project_id TEXT PRIMARY KEY, thread_id TEXT, title TEXT);
            """)
            self._migrate_profiles(db)
            self._sync_app_profiles(db)
            self._recover_incomplete_operations(db)
            self._check_identity(db, erp_mode, telegram_mode, erp_url, chat_id)
            self._seed_demo_catalog(db, erp_mode)

    def _migrate_profiles(self, db):
        profile_columns = {row[1] for row in db.execute("PRAGMA table_info(user_profiles)")}
        for column in ("employee_number", "assignment_id"):
            if column not in profile_columns:
                db.execute(f"ALTER TABLE user_profiles ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

    def _sync_app_profiles(self, db):
        for app_profile in db.execute("SELECT username,responsible_name,employee_number,assignment_id FROM app_users"):
            db.execute(
                "INSERT INTO user_profiles(user,responsible_name,employee_number,assignment_id,updated) VALUES (?,?,?,?,?) "
                "ON CONFLICT(user) DO UPDATE SET responsible_name=excluded.responsible_name,employee_number=excluded.employee_number,assignment_id=excluded.assignment_id,updated=excluded.updated",
                (*app_profile, self.now()),
            )

    def _recover_incomplete_operations(self, db):
        db.execute("UPDATE reports SET state='erp_review',error='El proceso se interrumpió durante el registro. Verifica en ERP antes de repetir.' WHERE state='erp_sending'")
        db.execute("UPDATE reports SET state='telegram_review',error='El proceso se interrumpió durante el envío. Verifica en Telegram antes de repetir.' WHERE state='telegram_sending'")

    def _check_identity(self, db, erp_mode, telegram_mode, erp_url, chat_id):
        identity = json.dumps([erp_mode, erp_url if erp_mode == "live" else "", telegram_mode, chat_id if telegram_mode == "live" else ""])
        existing = db.execute("SELECT value FROM settings WHERE key='identity'").fetchone()
        if existing and existing[0] != identity:
            raise RuntimeError("La integración cambió. Usa un volumen nuevo (otro nombre de proyecto Compose) para conservar el anterior y separar datos.")
        db.execute("INSERT OR IGNORE INTO settings VALUES ('identity',?)", (identity,))

    def _seed_demo_catalog(self, db, erp_mode):
        if erp_mode != "demo" or db.execute("SELECT 1 FROM settings WHERE key='demo_catalog_deleted'").fetchone() or db.execute("SELECT 1 FROM catalog LIMIT 1").fetchone():
            return
        projects = [
            {"id": "demo-stere", "folio": "PRJ-2026-0001", "code": "STERE-MECANIZADO", "name": "Santa Teresita · Maíz mecanizado", "company": {"name": "AGROKOOL"}, "status": "IN_PROGRESS", "progressBps": 3800},
            {"id": "demo-riego", "folio": "PRJ-2026-0002", "code": "RIEGO-NORTE", "name": "Sistema de riego · Sector norte", "company": {"name": "AGROKOOL"}, "status": "IN_PROGRESS", "progressBps": 2500},
        ]
        specs = [
            ("demo-t1", "demo-stere", "T-PREP-01", "Reconocimiento y delimitación operativa", 6400, "Preparación de terreno", "Abner Pérez"),
            ("demo-t2", "demo-stere", "T-PREP-02", "Limpieza y preparación del terreno", 4500, "Preparación de terreno", "María López"),
            ("demo-t3", "demo-stere", "T-SIEM-01", "Siembra del lote principal", 0, "Siembra", "Carlos Ruiz"),
            ("demo-t4", "demo-stere", "T-SIEM-02", "Revisión de maquinaria y equipo", 10000, "Siembra", "Abner Pérez"),
            ("demo-t5", "demo-riego", "T-RIEG-01", "Instalación de línea principal", 5000, "Instalación", "María López"),
            ("demo-t6", "demo-riego", "T-RIEG-02", "Prueba de presión y caudal", 0, "Validación", "Carlos Ruiz"),
        ]
        for project in projects:
            db.execute("INSERT INTO catalog VALUES ('project',?,?)", (project["id"], json.dumps(project)))
        responsible_data = {
            "Abner Pérez": {"assignmentId": "demo-assign-abner", "employeeNumber": "AGROKOOL-0003", "fullName": "Abner Pérez"},
            "María López": {"assignmentId": "demo-assign-maria", "employeeNumber": "AGROKOOL-0004", "fullName": "María López"},
            "Carlos Ruiz": {"assignmentId": "demo-assign-carlos", "employeeNumber": "AGROKOOL-0005", "fullName": "Carlos Ruiz"},
        }
        for task_id, project_id, code, name, progress, activity, responsible in specs:
            task = {"id": task_id, "projectId": project_id, "code": code, "name": name, "progressBps": progress, "status": "FINISHED" if progress == 10000 else "IN_PROGRESS" if progress else "CREATED", "responsibleName": responsible, "responsible": responsible_data[responsible], "activity": {"name": activity}, "workPackage": {"name": "Frente principal"}}
            db.execute("INSERT INTO catalog VALUES ('task',?,?)", (task_id, json.dumps(task)))

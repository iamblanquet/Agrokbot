"""Daily missing-report selection. Dates in the ERP are operational calendar dates."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import json
import urllib.parse


def due(now):
    local = now.astimezone(ZoneInfo('America/Mexico_City'))
    return local.weekday() < 6 and local.hour >= 21


def missing_reports(projects, day):
    date.fromisoformat(day)
    missing, unscheduled = [], 0
    for project in projects:
        for activity in project.get('activities', []):
            for task in activity.get('tasks', []):
                if task.get('status') in ('FINISHED', 'COMPLETED', 'CANCELLED', 'CANCELED'):
                    continue
                start = (task.get('plannedStartDate') or '')[:10]
                end = (task.get('plannedEndDate') or '')[:10]
                try:
                    date.fromisoformat(start); date.fromisoformat(end)
                    if start > end:
                        raise ValueError('Inverted schedule')
                except ValueError:
                    unscheduled += 1
                    continue
                if not start <= day <= end:
                    continue
                logs = task.get('operationLogs')
                if not isinstance(logs, list):
                    raise ValueError('ERP omitted operationLogs; cannot conclude missing reports')
                if any((log.get('operationDate') or '')[:10] == day for log in logs):
                    continue
                responsible = task.get('responsible') or {}
                missing.append({'id': task['id'], 'task': task.get('name') or task['id'],
                                'project': project.get('name') or project['id'],
                                'responsible': responsible.get('fullName') or task.get('responsibleName') or 'Sin responsable',
                                'assignmentId': responsible.get('assignmentId'),
                                'employeeNumber': responsible.get('employeeNumber')})
    return missing, unscheduled


def belongs(task, profile):
    return bool((profile.get('assignment_id') and profile['assignment_id'] == task.get('assignmentId')) or
                (profile.get('employee_number') and profile['employee_number'] == task.get('employeeNumber')))


class Reminders:
    def __init__(self, connection, erp, telegram, chat_id):
        self.connection, self.erp, self.telegram, self.chat_id = connection, erp, telegram, chat_id

    def initialize(self):
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS reminder_runs(day TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reminder_deliveries(id TEXT PRIMARY KEY, state TEXT NOT NULL, error TEXT);
                CREATE TABLE IF NOT EXISTS push_subscriptions(endpoint TEXT PRIMARY KEY, user TEXT NOT NULL, payload TEXT NOT NULL);
            ''')

    def snapshot(self, day):
        # Build a complete snapshot before creating notifications. Never use stale catalog.
        projects = self.erp.request('/external/projects')['projects']
        details = [self.erp.request('/external/projects/' + urllib.parse.quote(p['id'], safe=''))['project'] for p in projects]
        tasks, skipped = missing_reports(details, day)
        return {'day': day, 'tasks': tasks, 'unscheduled': skipped}

    def once(self, key, send):
        # A crash/timeout after send is ambiguous: do not auto-send twice.
        with self.connection() as db:
            db.execute("DELETE FROM reminder_deliveries WHERE id=? AND state='retry'", (key,))
            claimed = db.execute("INSERT OR IGNORE INTO reminder_deliveries VALUES (?, 'sending', NULL)", (key,)).rowcount
        if not claimed:
            return
        try:
            send()
        except Exception as error:
            from backend.http_client import RemoteFailure
            retry = isinstance(error, RemoteFailure) and not error.ambiguous
            with self.connection() as db:
                db.execute("UPDATE reminder_deliveries SET state=?,error=? WHERE id=?", ('retry' if retry else 'review', type(error).__name__, key))
            return
        with self.connection() as db:
            db.execute("UPDATE reminder_deliveries SET state='sent' WHERE id=?", (key,))

    def topic(self):
        with self.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key='reminder_topic'").fetchone()
        if row:
            if row[0] == 'creating':
                raise ValueError('Topic creation needs manual review')
            return int(row[0])
        with self.connection() as db:
            claimed = db.execute("INSERT OR IGNORE INTO settings VALUES ('reminder_topic','creating')").rowcount
        if not claimed:
            raise ValueError('Topic creation already in progress')
        result = self.telegram('createForumTopic', {'chat_id': self.chat_id, 'name': 'Tablero'})
        topic_id = result['message_thread_id']
        with self.connection() as db:
            db.execute("UPDATE settings SET value=? WHERE key='reminder_topic'", (str(topic_id),))
        return topic_id

    def tick(self, now, push):
        if not due(now):
            return
        day = now.astimezone(ZoneInfo('America/Mexico_City')).date().isoformat()
        with self.connection() as db:
            saved = db.execute('SELECT payload FROM reminder_runs WHERE day=?', (day,)).fetchone()
        if saved:
            snapshot = json.loads(saved[0])
        else:
            try:
                snapshot = self.snapshot(day)
            except Exception:
                self.once(day + ':erp-error', lambda: self.telegram('sendMessage', {
                    'chat_id': self.chat_id, 'message_thread_id': self.topic(),
                    'text': f'Tablero · {day}: No se pudo verificar el ERP. No se determinaron reportes faltantes.'}))
                return  # Retry the read next tick; no false missing-report alerts.
            with self.connection() as db:
                db.execute('INSERT OR IGNORE INTO reminder_runs VALUES (?,?)', (day, json.dumps(snapshot)))
        tasks = snapshot['tasks']
        lines = [f'Tablero · {day} · corte 21:00 (Ciudad de México)',
                 f'{len(tasks)} tareas programadas sin reporte recibido.',
                 f"Sin fechas válidas (no evaluadas): {snapshot['unscheduled']}."]
        for task in sorted(tasks, key=lambda t: (t['responsible'], t['project'], t['task'])):
            lines.append(f"{task['responsible']} · {task['project']} · {task['task']}")
        # Each chunk has a stable delivery key and stays below Telegram's UTF-16 limit.
        chunks, text = [], ''
        for line in lines:
            line = line[:900]
            if len((text + '\n' + line).encode('utf-16-le')) // 2 > 3500:
                chunks.append(text); text = ''
            text += ('\n' if text else '') + line
        if text:
            chunks.append(text)
        for index, text in enumerate(chunks):
            self.once(f'{day}:telegram:{index}', lambda text=text: self.telegram('sendMessage', {
                'chat_id': self.chat_id, 'message_thread_id': self.topic(), 'text': text}))
        with self.connection() as db:
            subscriptions = [dict(r) for r in db.execute('''SELECT s.*,p.assignment_id,p.employee_number
                FROM push_subscriptions s JOIN user_profiles p ON s.user=p.user
                JOIN app_users u ON u.username=s.user WHERE u.active=1''')]
        for subscription in subscriptions:
            mine = [t for t in tasks if belongs(t, subscription)]
            if mine:
                import hashlib
                key = day + ':push:' + hashlib.sha256(subscription['endpoint'].encode()).hexdigest()
                self.once(key, lambda s=subscription, count=len(mine): push(json.loads(s['payload']), {
                    'title': 'Reportes pendientes', 'body': f'{count} tareas programadas sin reporte recibido hoy. Revisa la bitácora.',
                    'tag': 'campo-reportes-' + day}))

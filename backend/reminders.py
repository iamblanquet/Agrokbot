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


def daily_summary(projects, day):
    missing, skipped = missing_reports(projects, day)
    planned, reported = [], []
    for project in projects:
        for activity in project.get('activities', []):
            for task in activity.get('tasks', []):
                responsible = task.get('responsible') or {}
                item = {'id':task['id'], 'task':task.get('name') or task['id'],
                        'project':project.get('name') or project['id'],
                        'responsible':responsible.get('fullName') or task.get('responsibleName') or 'Sin responsable',
                        'assignmentId':responsible.get('assignmentId'), 'employeeNumber':responsible.get('employeeNumber'),
                        'status':task.get('status')}
                start, end = (task.get('plannedStartDate') or '')[:10], (task.get('plannedEndDate') or '')[:10]
                try:
                    date.fromisoformat(start); date.fromisoformat(end)
                    if start <= day <= end and task.get('status') not in ('CANCELLED','CANCELED'):
                        planned.append(item)
                except ValueError:
                    pass
                logs = task.get('operationLogs')
                if not isinstance(logs, list):
                    raise ValueError('ERP omitted operationLogs; cannot build daily summary')
                today = [log for log in logs if (log.get('operationDate') or '')[:10] == day]
                if today:
                    latest = max(today, key=lambda log:(log.get('createdAt') or '', log.get('id') or ''))
                    reported.append({**item, 'reports':len(today), 'progressBps':latest.get('progressBps')})
    return {'day':day, 'planned':planned, 'reported':reported, 'tasks':missing, 'unscheduled':skipped}


class Reminders:
    def __init__(self, connection, erp, telegram, chat_id, topic_key='reminder_topic', topic_name='Tablero'):
        self.connection, self.erp, self.telegram, self.chat_id = connection, erp, telegram, chat_id
        self.topic_key, self.topic_name = topic_key, topic_name

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

    def daily_snapshot(self, day):
        projects = self.erp.request('/external/projects')['projects']
        details = [self.erp.request('/external/projects/' + urllib.parse.quote(p['id'], safe=''))['project'] for p in projects]
        return daily_summary(details, day)

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
            row = db.execute("SELECT value FROM settings WHERE key=?", (self.topic_key,)).fetchone()
        if row:
            if row[0] == 'creating':
                raise ValueError('Topic creation needs manual review')
            return int(row[0])
        with self.connection() as db:
            claimed = db.execute("INSERT OR IGNORE INTO settings VALUES (?,'creating')", (self.topic_key,)).rowcount
        if not claimed:
            raise ValueError('Topic creation already in progress')
        result = self.telegram('createForumTopic', {'chat_id': self.chat_id, 'name': self.topic_name})
        topic_id = result['message_thread_id']
        with self.connection() as db:
            db.execute("UPDATE settings SET value=? WHERE key=?", (str(topic_id),self.topic_key))
        return topic_id

    def tick(self, now, push):
        local = now.astimezone(ZoneInfo('America/Mexico_City'))
        if local.weekday() == 6:
            return
        minutes = local.hour * 60 + local.minute
        day = local.date().isoformat()
        # Recover a missed morning run only while it is still useful for the day.
        if 450 <= minutes < 1260:
            self.run_slot(day, 'morning', push)
        if minutes >= 1260:
            self.run_slot(day, 'missing', push)
        if minutes >= 1290:
            self.run_slot(day, 'evening', push)

    def run_slot(self, day, slot, push):
        run_key = day if slot == 'missing' else f'{day}:{slot}'
        with self.connection() as db:
            saved = db.execute('SELECT payload FROM reminder_runs WHERE day=?', (run_key,)).fetchone()
        if saved:
            snapshot = json.loads(saved[0])
        else:
            try:
                snapshot = self.snapshot(day) if slot == 'missing' else self.daily_snapshot(day)
            except Exception:
                self.once(f'{day}:{slot}:erp-error', lambda: self.telegram('sendMessage', {
                    'chat_id': self.chat_id, 'message_thread_id': self.topic(),
                    'text': f'Tablero · {day} · {slot}: No se pudo verificar el ERP. No se determinaron tareas ni reportes faltantes.'}))
                return  # Retry the read next tick; no false missing-report alerts.
            with self.connection() as db:
                db.execute('INSERT OR IGNORE INTO reminder_runs VALUES (?,?)', (run_key, json.dumps(snapshot)))
        tasks = snapshot['planned'] if slot == 'morning' else snapshot['tasks']
        lines = []
        def task_line(task):
            return f"{task['responsible']} · {task['project']} · {task['task']}"
        if slot == 'morning':
            lines = [f'Tablero · {day} · planificación 07:30 (Ciudad de México)',
                     f'{len(tasks)} tareas planificadas para hoy.']
            lines.extend(task_line(t) for t in sorted(tasks, key=lambda t:(t['responsible'],t['project'],t['task'])))
        elif slot == 'evening':
            reported = snapshot['reported']
            lines = [f'Tablero · {day} · resumen 21:30 (Ciudad de México)',
                     f"{len(reported)} tareas con reporte; {sum(t['reports'] for t in reported)} reportes recibidos para hoy.",
                     'El avance es acumulado según el último reporte del día; reportar no significa finalizar.']
            for task in sorted(reported, key=lambda t:(t['responsible'],t['project'],t['task'])):
                value = task.get('progressBps')
                progress = f'{value / 100:g} %' if isinstance(value,(int,float)) else 'no informado'
                finished = task.get('status') in ('FINISHED','COMPLETED')
                lines.append(f"{task_line(task)} · {task['reports']} reportes · avance {progress} · {'Finalizada en ERP' if finished else 'No finalizada en ERP'}")
            lines.append(f'{len(tasks)} tareas programadas sin reporte recibido:')
            lines.extend(task_line(t) for t in tasks)
        if lines:
            lines.append(f"Sin fechas válidas (no evaluadas para pendientes): {snapshot['unscheduled']}.")
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
            self.once(f'{day}:{slot}:telegram:{index}', lambda text=text: self.telegram('sendMessage', {
                'chat_id': self.chat_id, 'message_thread_id': self.topic(), 'text': text}))
        if slot == 'evening':
            return
        with self.connection() as db:
            subscriptions = [dict(r) for r in db.execute('''SELECT s.*,p.assignment_id,p.employee_number
                FROM push_subscriptions s JOIN user_profiles p ON s.user=p.user
                JOIN app_users u ON u.username=s.user WHERE u.active=1''')]
        for subscription in subscriptions:
            mine = [t for t in tasks if belongs(t, subscription)]
            if mine:
                import hashlib
                key = day + (':morning:push:' if slot == 'morning' else ':push:') + hashlib.sha256(subscription['endpoint'].encode()).hexdigest()
                names = '; '.join(t['task'] for t in mine)
                data = ({'title':'Tus tareas de hoy', 'body':f'{len(mine)} tareas: {names[:600]}. Abre Campo con internet para actualizar tus datos.',
                         'tag':'campo-tareas-' + day, 'refreshCatalog':True}
                        if slot == 'morning' else {'title':'Reportes pendientes', 'body':f'{len(mine)} tareas programadas sin reporte recibido hoy. Revisa la bitácora.', 'tag':'campo-reportes-' + day})
                self.once(key, lambda s=subscription, data=data: push(json.loads(s['payload']), data))

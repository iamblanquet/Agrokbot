import unittest
from datetime import datetime, timezone
from backend.reminders import due, missing_reports, belongs, Reminders
from backend.push import validate_subscription


class ReminderTests(unittest.TestCase):
    def test_full_evening_cycle_targets_only_missing_responsible_and_never_duplicates(self):
        import sqlite3
        import tempfile
        import json
        from pathlib import Path
        from unittest.mock import Mock
        from contextlib import contextmanager
        with tempfile.TemporaryDirectory() as folder:
            @contextmanager
            def connection():
                db = sqlite3.connect(Path(folder) / 'cycle.sqlite')
                db.row_factory = sqlite3.Row
                try:
                    with db:
                        yield db
                finally:
                    db.close()
            erp, telegram, push = Mock(), Mock(), Mock()
            service = Reminders(connection, erp, telegram, 'test-group')
            service.initialize()
            with connection() as db:
                db.executescript('''CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);
                    INSERT INTO settings VALUES ('reminder_topic','22');
                    CREATE TABLE app_users(username TEXT PRIMARY KEY,active INTEGER);
                    CREATE TABLE user_profiles(user TEXT,assignment_id TEXT,employee_number TEXT);''')
                for user, assignment, active in [('missing','a1',1),('reported','a2',1),('disabled','a1',0),('unrelated','a3',1)]:
                    db.execute('INSERT INTO app_users VALUES (?,?)',(user,active))
                    db.execute('INSERT INTO user_profiles VALUES (?,?,?)',(user,assignment,''))
                    db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)',(user,user,json.dumps({'endpoint':user})))
            project = self.project(responsible={'assignmentId':'a1','fullName':'Responsable pendiente'})[0]
            tasks = project['activities'][0]['tasks']
            tasks.append({**tasks[0], 'id':'reported', 'responsible':{'assignmentId':'a2'}, 'operationLogs':[{'operationDate':'2026-10-19'}]})
            tasks.append({**tasks[0], 'id':'tomorrow', 'plannedStartDate':'2026-10-20','plannedEndDate':'2026-10-20'})
            tasks.append({**tasks[0], 'id':'finished', 'status':'FINISHED'})
            erp.request.side_effect = lambda path: {'projects':[{'id':'p1'}]} if path=='/external/projects' else {'project':project}
            service.tick(datetime(2026,10,19,13,29,tzinfo=timezone.utc),push)
            erp.request.assert_not_called()
            service.tick(datetime(2026,10,20,3,0,tzinfo=timezone.utc),push)
            push.assert_called_once()
            self.assertEqual(push.call_args.args[0]['endpoint'],'missing')
            self.assertIn('1 tareas',push.call_args.args[1]['body'])
            telegram.assert_not_called()
            service.tick(datetime(2026,10,20,3,1,tzinfo=timezone.utc),push)
            push.assert_called_once()
            telegram.assert_not_called()
            with connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM reminder_runs').fetchone()[0],1)
                self.assertEqual(db.execute("SELECT count(*) FROM reminder_deliveries WHERE state='sent'").fetchone()[0],1)
            # A report arriving between the PWA reminder and Telegram summary is included.
            tasks[0]['operationLogs']=[{'id':'late','operationDate':'2026-10-19','progressBps':1500}]
            service.tick(datetime(2026,10,20,3,29,tzinfo=timezone.utc),push)
            telegram.assert_not_called()
            service.tick(datetime(2026,10,20,3,30,tzinfo=timezone.utc),push)
            telegram.assert_called_once()
            text=telegram.call_args.args[1]['text']
            self.assertIn('2 tareas con reporte',text)
            self.assertIn('15 %',text)
            self.assertIn('0 tareas programadas sin reporte',text)
            self.assertEqual(telegram.call_args.args[1]['message_thread_id'],22)
            service.tick(datetime(2026,10,20,3,31,tzinfo=timezone.utc),push)
            telegram.assert_called_once()
            push.assert_called_once()
            # Separate morning cut includes already reported tasks and per-user assignment.
            push.reset_mock();telegram.reset_mock()
            service.tick(datetime(2026,10,19,13,30,tzinfo=timezone.utc),push)
            self.assertEqual(push.call_count,2)
            self.assertEqual({c.args[0]['endpoint'] for c in push.call_args_list},{'missing','reported'})
            self.assertTrue(all(c.args[1]['refreshCatalog'] for c in push.call_args_list))
            telegram.assert_called_once()
            self.assertIn('3 tareas planificadas',telegram.call_args.args[1]['text'])
            service.tick(datetime(2026,10,19,13,31,tzinfo=timezone.utc),push)
            self.assertEqual(push.call_count,2)
            telegram.assert_called_once()

    def test_slots_weekdays_and_no_late_morning_after_nine(self):
        from unittest.mock import Mock
        service=Reminders(None,None,None,None)
        service.run_slot=Mock()
        service.tick(datetime(2026,10,18,13,30,tzinfo=timezone.utc),None)
        service.run_slot.assert_not_called()
        service.tick(datetime(2026,10,17,13,30,tzinfo=timezone.utc),None)
        service.run_slot.assert_called_once_with('2026-10-17','morning',None)
        service.run_slot.reset_mock()
        service.tick(datetime(2026,10,20,4,0,tzinfo=timezone.utc),None)
        self.assertEqual([c.args[1] for c in service.run_slot.call_args_list],['missing','evening'])

    def test_success_and_ambiguous_delivery_are_not_duplicated(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        from contextlib import contextmanager
        with tempfile.TemporaryDirectory() as folder:
            @contextmanager
            def connection():
                db=sqlite3.connect(Path(folder)/'test.sqlite')
                try:
                    with db: yield db
                finally: db.close()
            service=Reminders(connection,None,None,None)
            service.initialize()
            send=Mock()
            service.once('ok',send);service.once('ok',send)
            self.assertEqual(send.call_count,1)
            uncertain=Mock(side_effect=TimeoutError())
            service.once('uncertain',uncertain);service.once('uncertain',uncertain)
            self.assertEqual(uncertain.call_count,1)

    def test_schedule_mexico_monday_saturday(self):
        self.assertFalse(due(datetime(2026,10,20,2,59,tzinfo=timezone.utc)))
        self.assertTrue(due(datetime(2026,10,20,3,0,tzinfo=timezone.utc)))
        self.assertTrue(due(datetime(2026,10,18,3,0,tzinfo=timezone.utc)))
        self.assertFalse(due(datetime(2026,10,19,3,0,tzinfo=timezone.utc)))

    def project(self, **overrides):
        task={'id':'t1','name':'Tarea','plannedStartDate':'2026-10-19T00:00:00Z',
              'plannedEndDate':'2026-10-19T00:00:00Z','operationLogs':[], **overrides}
        return [{'id':'p1','activities':[{'tasks':[task]}]}]

    def test_missing_and_any_source_report(self):
        self.assertEqual(len(missing_reports(self.project(), '2026-10-19')[0]),1)
        self.assertEqual(missing_reports(self.project(operationLogs=[{'operationDate':'2026-10-19','source':'IMPORT'}]),'2026-10-19')[0],[])
        self.assertEqual(missing_reports(self.project(), '2026-10-20')[0],[])

    def test_unknown_schedule_not_assumed(self):
        self.assertEqual(missing_reports(self.project(plannedStartDate=None),'2026-10-19'),([],1))
        self.assertEqual(missing_reports(self.project(status='FINISHED'),'2026-10-19')[0],[])
        with self.assertRaises(ValueError):missing_reports(self.project(operationLogs=None),'2026-10-19')

    def test_identity_requires_real_identifier(self):
        self.assertFalse(belongs({},{}))
        self.assertTrue(belongs({'assignmentId':'a'}, {'assignment_id':'a'}))
        self.assertFalse(belongs({'assignmentId':'a'}, {'assignment_id':'b'}))

    def test_push_rejects_arbitrary_network_targets(self):
        for endpoint in ['http://localhost/','https://127.0.0.1/','https://fcm.googleapis.com.evil.test/','https://fcm.googleapis.com:444/']:
            with self.assertRaises(ValueError):validate_subscription({'endpoint':endpoint})

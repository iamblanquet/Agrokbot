import unittest
from datetime import datetime, timezone
from backend.reminders import due, missing_reports, belongs, Reminders
from backend.push import validate_subscription


class ReminderTests(unittest.TestCase):
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

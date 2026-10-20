import unittest
import tempfile
import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import Mock
from backend.reminders import Reminders
from backend.http_client import RemoteFailure


class PrivateReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        @contextmanager
        def connection():
            db = sqlite3.connect(Path(self.tmp.name)/'test.sqlite')
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()
        self.connection = connection
        self.telegram = Mock()
        self.service = Reminders(connection, Mock(), self.telegram, 'group')
        self.service.initialize()
        with connection() as db:
            db.executescript("""
                CREATE TABLE app_users(username TEXT PRIMARY KEY,active INTEGER);
                CREATE TABLE user_profiles(user TEXT,assignment_id TEXT,employee_number TEXT);
                CREATE TABLE telegram_links(user TEXT PRIMARY KEY,telegram_id TEXT UNIQUE);
                INSERT INTO app_users VALUES ('ana',1),('disabled',0),('other',1);
                INSERT INTO user_profiles VALUES ('ana','a1',''),('disabled','a1',''),('other','a2','');
                INSERT INTO telegram_links VALUES ('ana','123'),('disabled','456'),('other','789');
            """)
        self.tasks = [{'id':'t1','assignmentId':'a1','project':'Proyecto','task':'Tarea de Ana'}]

    def tearDown(self):
        self.tmp.cleanup()

    def run_notice(self, slot='missing'):
        self.service.private_reminders('2026-10-20',slot,self.tasks)

    def test_targets_only_linked_active_responsible_without_push_subscription(self):
        self.run_notice()
        self.run_notice()
        self.telegram.assert_called_once()
        payload = self.telegram.call_args.args[1]
        self.assertEqual(payload['chat_id'],'123')
        self.assertNotIn('message_thread_id',payload)
        self.assertIn('Tarea de Ana',payload['text'])
        self.assertIn('hora de Campeche',payload['text'])
        self.run_notice('morning')
        self.assertEqual(self.telegram.call_count,2)
        self.assertIn('actualizar',self.telegram.call_args.args[1]['text'])

    def test_daily_slot_delivers_both_channels_once(self):
        with self.connection() as db:
            db.execute("INSERT INTO reminder_runs VALUES (?,?)",
                       ('2026-10-20',json.dumps({'tasks':self.tasks,'unscheduled':0})))
            db.execute("INSERT INTO push_subscriptions VALUES ('endpoint','ana',?)",
                       (json.dumps({'endpoint':'endpoint'}),))
        push = Mock()
        self.service.run_slot('2026-10-20','missing',push)
        self.service.run_slot('2026-10-20','missing',push)
        self.telegram.assert_called_once()
        push.assert_called_once()

    def test_definite_failure_retries_but_ambiguous_does_not(self):
        self.telegram.side_effect = RemoteFailure('Unavailable',False)
        self.run_notice()
        self.telegram.side_effect = None
        self.run_notice()
        self.assertEqual(self.telegram.call_count,2)
        self.telegram.side_effect = RemoteFailure('Timeout',True)
        self.run_notice('morning')
        self.run_notice('morning')
        self.assertEqual(self.telegram.call_count,3)

    def test_retry_does_not_deliver_after_unlink(self):
        self.telegram.side_effect = RemoteFailure('Unavailable',False)
        self.run_notice()
        with self.connection() as db:
            key = db.execute("SELECT id FROM reminder_deliveries").fetchone()[0]
            db.execute("DELETE FROM telegram_links WHERE user='ana'")
        self.service.retry_job(key,Mock())
        self.telegram.assert_called_once()
        with self.connection() as db:
            self.assertEqual(db.execute("SELECT state FROM reminder_deliveries").fetchone()[0],'expired')

    def test_long_unicode_messages_are_chunked_and_not_duplicated(self):
        self.tasks = [dict(self.tasks[0],id=str(i),task='🌱'*600) for i in range(12)]
        self.run_notice()
        count = self.telegram.call_count
        self.assertGreater(count,1)
        self.assertTrue(all(len(call.args[1]['text'].encode('utf-16-le'))//2<=4096 for call in self.telegram.call_args_list))
        self.run_notice()
        self.assertEqual(self.telegram.call_count,count)

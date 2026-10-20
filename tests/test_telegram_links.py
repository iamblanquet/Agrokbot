import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace
from telegram_bot import ReportBot
import server


class TelegramLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(server, "DB", Path(self.tmp.name)/"test.sqlite3")
        self.patch.start()
        with server.connection() as db:
            db.executescript("""
            CREATE TABLE app_users(username TEXT PRIMARY KEY, active INTEGER);
            INSERT INTO app_users VALUES ('alice',1),('bob',1);
            CREATE TABLE telegram_links(user TEXT PRIMARY KEY, telegram_id TEXT UNIQUE, username TEXT);
            CREATE TABLE telegram_link_tokens(token TEXT PRIMARY KEY,user TEXT UNIQUE,expires REAL);
            """)
        self.links = server.TELEGRAM_LINKS

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_link_single_use_and_unlink(self):
        token = self.links.issue("alice")
        self.links.confirm(token, 123, "alice_tg")
        self.assertEqual(self.links.status("alice")["telegram"]["telegram_id"], "123")
        with self.assertRaises(server.Problem):
            self.links.confirm(token, 456, "")
        self.links.unlink("alice")
        self.assertFalse(self.links.status("alice")["linked"])

    def test_unique_telegram_and_user(self):
        self.links.confirm(self.links.issue("alice"), 123, "")
        with self.assertRaises(server.Problem):
            self.links.confirm(self.links.issue("bob"), 123, "")
        with self.assertRaises(server.Problem):
            self.links.issue("alice")

    def test_bot_requires_private_confirmation(self):
        token = self.links.issue("alice")
        backend = SimpleNamespace(BOT_TOKEN="test", connection=server.connection,
                                  TELEGRAM_LINKS=self.links, Problem=server.Problem, telegram=Mock())
        bot = ReportBot(backend)
        message = {"chat":{"id":123,"type":"private"}, "from":{"id":123},
                   "text":"/start link_"+token}
        bot.handle({"message":message})
        self.assertFalse(self.links.status("alice")["linked"])
        callback = {"id":"callback", "from":{"id":123}, "data":"link:"+token,
                    "message":{"chat":{"id":-1,"type":"supergroup"}}}
        bot.handle({"callback_query":callback})
        self.assertFalse(self.links.status("alice")["linked"])
        callback["message"]["chat"] = {"id":123,"type":"private"}
        bot.handle({"callback_query":callback})
        self.assertTrue(self.links.status("alice")["linked"])

    def test_expired_revoked_rotated_and_inactive(self):
        token = self.links.issue("alice")
        self.links.issue("alice")
        with self.assertRaises(server.Problem):
            self.links.confirm(token, 123, "")
        token = self.links.issue("alice")
        with server.connection() as db:
            db.execute("UPDATE telegram_link_tokens SET expires=0")
        with self.assertRaises(server.Problem):
            self.links.confirm(token, 123, "")
        token = self.links.issue("alice")
        self.links.unlink("alice")
        with self.assertRaises(server.Problem):
            self.links.confirm(token, 123, "")
        token = self.links.issue("alice")
        with server.connection() as db:
            db.execute("UPDATE app_users SET active=0 WHERE username='alice'")
        with self.assertRaises(server.Problem):
            self.links.confirm(token, 123, "")
        with self.assertRaises(server.Problem):
            self.links.issue("alice")

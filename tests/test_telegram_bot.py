import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
from telegram_bot import ReportBot


class BotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, 'DATA', Path(self.temp.name)), patch.object(server, 'DB', Path(self.temp.name)/'bot.sqlite3'), patch.object(server, 'ERP_MODE', 'demo'), patch.object(server, 'TG_MODE', 'demo'), patch.object(server, 'CHAT_ID', '-100123'), patch.object(server, 'BOT_TOKEN', 'fake'), patch.object(server, 'ALLOWED', set())]
        for p in self.patches:
            p.start()
        server.initialize()
        self.sent = []
        self.membership = 'member'
        self.mock = patch.object(server, 'telegram', side_effect=self.telegram)
        self.mock.start()
        self.bot = ReportBot(server)
        self.bot.username = 'testbot'
        self.number = 0
        self.chat = {'id': 123, 'type': 'private'}
        self.user = {'id': 123, 'first_name': 'Operador', 'is_bot': False}
        with server.connection() as db:
            db.execute(
                "INSERT INTO user_profiles VALUES (?,?,?,?,?)",
                ('telegram:123', 'Operador', 'AGROKOOL-0003', 'demo-assign-abner', server.now()),
            )

    def tearDown(self):
        self.mock.stop()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def telegram(self, method, data):
        if method == 'getChatMember':
            return {'status': self.membership}
        if method == 'sendMessage':
            self.sent.append(data)
            return {'message_id': 1000+len(self.sent)}
        return True

    def draft(self):
        return self.bot.load(self.bot.key(self.chat['id'], self.user['id']))

    def message(self, text, reply=None):
        self.number += 1
        msg = {'chat': self.chat, 'from': self.user, 'message_id': self.number, 'text': text}
        if reply:
            msg['reply_to_message'] = {'message_id': reply}
        self.bot.handle({'update_id': self.number, 'message': msg})

    def click(self, action, draft=None):
        self.number += 1
        d = draft or self.draft()
        update = {'update_id': self.number, 'callback_query': {'id': str(self.number), 'from': self.user, 'data': f"r:{d['nonce']}:{action}", 'message': {'chat': self.chat, 'message_id': d['prompt_id']}}}
        self.bot.handle(update)
        return update

    def to_progress(self):
        self.message('/reportar')
        self.click('pick0')
        self.click('pick0')
        self.click('today')

    def test_miniapp_private_button_and_group_deep_link(self):
        with patch.object(server, 'PUBLIC_URL', 'https://campo.example'):
            self.message('/reportar')
            self.assertEqual(self.sent[-1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url'], 'https://campo.example')
            self.assertIsNone(self.draft())
            self.chat = {'id': -100123, 'type': 'supergroup'}
            self.message('/reportar')
            button = self.sent[-1]['reply_markup']['inline_keyboard'][0][0]
            self.assertEqual(button['url'], 'https://t.me/testbot?start=reportar')
            self.assertNotIn('web_app', button)

    def test_complete_flow_and_duplicate_confirm(self):
        self.to_progress()
        self.message('65,5')
        self.message('Trabajo completado en el sector norte.')
        confirm = self.click('confirm')
        self.bot.handle(confirm)
        self.assertEqual(self.draft()['step'], 'done')
        with server.connection() as db:
            rows = db.execute('SELECT * FROM reports').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['user'], 'telegram:123')
            self.assertIn('Operador (telegram:123)', rows[0]['message'])
            self.assertEqual(rows[0]['state'], 'telegram_pending')

    def test_nonmember_cannot_access_catalog(self):
        self.membership = 'left'
        self.message('/reportar')
        self.assertIsNone(self.draft())
        self.assertIn('Debes pertenecer', self.sent[-1]['text'])

    def test_other_member_cannot_use_someone_elses_buttons(self):
        self.message('/reportar')
        first = self.draft()
        self.user = {'id': 456, 'first_name': 'Otro', 'is_bot': False}
        self.click('pick0', first)
        self.assertIsNone(self.draft())
        self.assertEqual(self.bot.load(first['key'])['step'], 'project')

    def test_group_requires_reply_and_ignores_other_groups(self):
        self.chat = {'id': -100999, 'type':'supergroup'}
        self.message('/reportar')
        self.assertIsNone(self.draft())
        self.chat = {'id': -100123, 'type':'supergroup'}
        self.to_progress()
        self.message('65')
        self.assertEqual(self.draft()['step'], 'progress')
        self.message('65', self.draft()['prompt_id'])
        self.assertEqual(self.draft()['step'], 'notes')

    def test_invalid_progress_and_stale_buttons(self):
        self.message('/reportar')
        stale = self.draft()
        self.click('pick0')
        self.click('pick0', stale)
        self.assertEqual(self.draft()['step'], 'task')
        self.click('pick0')
        self.click('today')
        for value in ('-1','101','nan','64.555','50'):
            self.message(value)
            self.assertEqual(self.draft()['step'], 'progress')

    def test_conflict_seals_capture_without_reopening_edit(self):
        self.to_progress()
        self.message('65')
        self.message('Nota que no debe perderse')
        error = server.Problem(409, 'Conflicto', 'conflict', {'currentProgressBps':8000})
        with patch.object(server, 'create_report', side_effect=error):
            self.click('confirm')
        self.assertEqual(self.draft()['step'], 'done')
        self.assertNotEqual(self.draft()['baseProgressBps'], 8000)
        self.assertEqual(self.draft()['notes'], 'Nota que no debe perderse')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0], 0)

    def test_restart_resume_and_cancel(self):
        self.to_progress()
        saved = self.draft()['id']
        self.bot = ReportBot(server)
        self.message('/continuar')
        self.assertEqual(self.draft()['id'], saved)
        self.assertEqual(self.draft()['step'], 'progress')
        self.message('/cancelar')
        self.assertEqual(self.draft()['step'], 'cancelled')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0], 0)

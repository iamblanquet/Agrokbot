"""Offline-to-ERP evidence workflow against a local HTTP ERP simulator."""
import base64
import json
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import server


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, 'DB', Path(self.temp.name) / 'test.sqlite3'), patch.object(server, 'ERP_MODE', 'demo'), patch.object(server, 'TG_MODE', 'demo')]
        for p in self.patches: p.start()
        server.initialize()
        self.catalog = server.catalog()
        self.events = []
        self.attachments = []
        self.failure = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def reply(self, code, data):
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.assertEqual(self.headers['Authorization'], 'Bearer test-key')
                if self.path.endswith('/operation-log'):
                    owner.events.append('log')
                    self.reply(201, {'operationLog': {'id': 'log-123'}})
                else:
                    owner.assertEqual(self.path, '/api/external/project-operation-logs/log-123/attachments')
                    owner.assertIn(b'name="file"', body)
                    owner.assertIn(b'\xff\xd8\xffimage\xff\xd9', body)
                    owner.assertIn('multipart/form-data', self.headers['Content-Type'])
                    filename = body.split(b'filename="')[1].split(b'"')[0].decode()
                    owner.events.append(filename)
                    if owner.failure == 'reject':
                        owner.failure = None
                        return self.reply(403, {})
                    item = {'id': 'attachment-' + filename, 'operationLogId': 'log-123', 'originalFileName': filename, 'mimeType': 'image/jpeg', 'sizeBytes': str(len(b'\xff\xd8\xffimage\xff\xd9'))}
                    owner.attachments.append(item)
                    if owner.failure == 'ambiguous':
                        owner.failure = None
                        return self.reply(500, {})
                    self.reply(201, {'attachments': [item]})

            def do_GET(self):
                owner.events.append('verify')
                self.reply(200, {'project': {'activities': [{'tasks': [{'operationLogs': [{'id': 'log-123', 'attachments': owner.attachments}]}]}]}})

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        more = [patch.object(server, 'ERP_MODE', 'live'), patch.object(server, 'ERP_URL', f'http://127.0.0.1:{self.http.server_port}/api'), patch.object(server, 'ERP_KEY', 'test-key'), patch.dict('os.environ', {'ERP_ALLOW_HTTP': 'true'}), patch.object(server, 'catalog', return_value=self.catalog)]
        for p in more: p.start()
        self.patches.extend(more)
        self.rid = str(uuid.uuid4())
        self.photos = [{'id': str(uuid.uuid4()), 'reportId': self.rid, 'data': base64.b64encode(b'\xff\xd8\xffimage\xff\xd9').decode()} for _ in range(2)]
        self.payload = {'id': self.rid, 'taskId': 'demo-t1', 'baseProgressBps': 6400, 'progressBps': 6500, 'operationDate': '2026-01-01', 'notes': 'Avance', 'photos': [p['id'] for p in self.photos]}

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def state(self):
        with server.connection() as db:
            return db.execute('SELECT state FROM reports WHERE id=?', (self.rid,)).fetchone()[0]

    def prepare(self):
        server.create_report(self.payload, 'dev')
        for p in self.photos: server.save_photo(p, 'dev')

    def test_real_http_multipart_order_and_idempotence(self):
        receipt = server.create_report(self.payload, 'dev')
        self.assertEqual(receipt['state'], 'photos_pending')
        server.deliver()
        self.assertEqual(self.state(), 'photos_pending')
        server.save_photo(self.photos[0], 'dev')
        server.deliver()
        self.assertEqual(self.state(), 'photos_pending')
        server.save_photo(self.photos[1], 'dev')
        server.deliver()
        self.assertEqual(self.state(), 'demo_published')
        self.assertEqual(len(self.attachments), 2)
        self.assertEqual(self.events[0], 'log')
        self.assertEqual(self.events[-1], 'verify')
        server.create_report(self.payload, 'dev')
        for p in self.photos: server.save_photo(p, 'dev')
        server.deliver()
        self.assertEqual(self.events.count('log'), 1)
        self.assertEqual(len(self.attachments), 2)

    def test_rejected_photo_retries_without_recreating_log(self):
        self.prepare()
        self.failure = 'reject'
        server.deliver()
        self.assertEqual(self.state(), 'photos_pending')
        server.deliver()
        self.assertEqual(self.state(), 'demo_published')
        self.assertEqual(self.events.count('log'), 1)
        self.assertEqual(len(self.attachments), 2)

    def test_ambiguous_upload_reconciles_without_duplicate(self):
        self.prepare()
        self.failure = 'ambiguous'
        server.deliver()
        self.assertEqual(self.state(), 'photos_review')
        server.deliver()
        self.assertEqual(self.state(), 'demo_published')
        self.assertEqual(len(self.attachments), 2)
        self.assertEqual(self.events.count(self.photos[0]['id'] + '.jpg'), 1)

    def test_missing_remote_confirmation_blocks_telegram(self):
        self.prepare()
        with patch.object(server.ERP, 'attachments', return_value=[]):
            server.deliver()
        self.assertEqual(self.state(), 'photos_pending')
        server.deliver()
        self.assertEqual(len(self.attachments), 2)
        self.assertEqual(self.state(), 'demo_published')

    def test_foreign_or_undeclared_photos_rejected(self):
        server.create_report(self.payload, 'dev')
        for photo, user in [(self.photos[0], 'other'), ({**self.photos[0], 'id': str(uuid.uuid4())}, 'dev')]:
            with self.assertRaises(server.Problem): server.save_photo(photo, user)
        self.assertEqual(len(self.attachments), 0)

    def test_interrupted_upload_is_not_reposted(self):
        self.prepare()
        with server.connection() as db:
            db.execute("UPDATE photos SET upload_state='sending' WHERE id=?", (self.photos[0]['id'],))
        server.deliver()
        server.deliver()
        self.assertEqual(self.state(), 'photos_review')
        self.assertEqual(len(self.attachments), 0)

    def test_telegram_runs_only_after_project_confirmation(self):
        self.prepare()
        with server.connection() as db:
            db.execute("INSERT INTO topics VALUES ('demo-stere','123','Proyecto')")
        def telegram_group(*args, **kwargs):
            self.assertEqual(self.events[-1], 'verify')
            self.assertEqual(len(self.attachments), 2)
            return ['501', '502']
        with patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'telegram_media_group', side_effect=telegram_group) as telegram:
            server.deliver()
            server.deliver()
        self.assertEqual(telegram.call_count, 1)
        self.assertEqual(self.state(), 'published')
        with server.connection() as db:
            rows = db.execute('SELECT data,attachment_id,digest FROM photos').fetchall()
        self.assertTrue(all(r['data'] == b'' and r['attachment_id'] and r['digest'] for r in rows))
        for photo in self.photos:
            server.save_photo(photo, 'dev')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT sum(length(data)) FROM photos').fetchone()[0], 0)

    def test_failed_delivery_keeps_pending_bytes(self):
        self.prepare()
        with server.connection() as db:
            db.execute("INSERT INTO topics VALUES ('demo-stere','123','Proyecto')")
        with patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'telegram_media_group', side_effect=server.RemoteFailure('rechazado')):
            server.deliver()
        self.assertEqual(self.state(), 'telegram_failed')
        with server.connection() as db:
            self.assertGreater(db.execute('SELECT sum(length(data)) FROM photos').fetchone()[0], 0)

    def test_legacy_pending_cannot_bypass_evidence_confirmation(self):
        self.prepare()
        with server.connection() as db:
            db.execute("UPDATE reports SET state='telegram_pending' WHERE id=?", (self.rid,))
        server.deliver()
        self.assertEqual(self.state(), 'photos_pending')
        self.assertEqual(len(self.attachments), 0)
        server.deliver()
        self.assertEqual(self.state(), 'demo_published')

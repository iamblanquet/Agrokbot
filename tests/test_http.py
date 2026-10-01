import base64
import uuid
import hashlib
import hmac
import http.cookiejar
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch
import server


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, 'DATA', Path(self.temp.name)), patch.object(server, 'DB', Path(self.temp.name) / 'http.sqlite3'), patch.object(server, 'ERP_MODE', 'demo'), patch.object(server, 'TG_MODE', 'demo'), patch.object(server, 'ATTEMPTS', {}), patch.object(server, 'USER', 'tester'), patch.object(server, 'PASSWORD', 'prueba-ñ'), patch.object(server, 'BOT_TOKEN', 'fake-test-token'), patch.object(server, 'ALLOWED', {'123'})]
        for p in self.patches:
            p.start()
        server.initialize()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.http.server_port}'
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        req = urllib.request.Request(self.url + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with self.client.open(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_cookie_login_logout_and_unauthenticated_read(self):
        health_status, health_payload = self.request('/api/health')
        self.assertEqual(health_status, 200)
        self.assertTrue(health_payload['ok'])
        self.assertEqual(health_payload['checks']['database'], 'ok')
        self.assertEqual(self.request('/api/catalog')[0], 401)
        self.assertEqual(self.request('/api/login', {'user':'tester', 'password':'incorrect'})[0], 401)
        self.assertEqual(self.request('/api/login', {'user':'tester', 'password':'prueba-ñ'})[0], 200)
        self.assertEqual(len(self.request('/api/catalog')[1]['projects']), 2)
        self.assertEqual(self.request('/api/logout', {})[0], 200)
        self.assertEqual(self.request('/api/catalog')[0], 401)

    def test_health_reports_missing_live_configuration_without_secrets(self):
        with patch.object(server, 'ERP_MODE', 'live'), patch.object(server, 'ERP_URL', ''), patch.object(server, 'ERP_KEY', ''), patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'BOT_TOKEN', ''), patch.object(server, 'CHAT_ID', ''):
            status, payload = server.health()
        self.assertEqual(status, 503)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['checks']['database'], 'ok')
        self.assertEqual(payload['checks']['erp'], 'not_configured')
        self.assertEqual(payload['checks']['telegram'], 'not_configured')
        self.assertNotIn('key', payload)

    def test_employees_require_session_and_crud(self):
        self.assertEqual(self.request('/api/employees')[0], 401)
        self.assertEqual(self.request('/api/employees/save', {'name': 'Ana', 'roles': ['operator']})[0], 401)
        self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})
        status, employee = self.request('/api/employees/save', {'name': 'Ana', 'roles': ['operator']})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.request('/api/employees')[1]['employees']), 1)
        status, edited = self.request('/api/employees/save', {**employee, 'roles': ['technician', 'assistant']})
        self.assertEqual(status, 200)
        self.assertEqual(edited['version'], 2)
        self.assertEqual(self.request('/api/employees/delete', employee)[0], 409)
        self.assertEqual(self.request('/api/employees/delete', edited)[0], 200)
        self.assertEqual(self.request('/api/employees')[1]['employees'], [])

    def test_private_photo_upload_and_read(self):
        pid, rid = str(uuid.uuid4()), str(uuid.uuid4())
        image = b'\xff\xd8\xffphoto\xff\xd9'
        body = {'id': pid, 'reportId': rid, 'data': base64.b64encode(image).decode()}
        self.assertEqual(self.request('/api/photos', body)[0], 401)
        self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})
        self.assertEqual(self.request('/api/photos', body)[0], 200)
        with self.client.open(self.url+'/api/photos/'+pid) as response:
            self.assertEqual(response.read(), image)
            self.assertEqual(response.headers['Content-Type'], 'image/jpeg')
            self.assertIn('no-store', response.headers['Cache-Control'])
        self.request('/api/logout', {})
        self.assertEqual(self.request('/api/photos/'+pid)[0], 401)
        self.assertEqual(self.request('/api/login', {'initData': self.signed()})[0], 403)
        self.assertEqual(self.request('/api/photos/'+pid)[0], 401)

    def test_clarification_is_append_only(self):
        self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})
        self.assertEqual(self.request('/api/config')[1]['authScope'], 'Todos los proyectos de la integración')
        rid = str(uuid.uuid4())
        report = {'id': rid, 'taskId': 'demo-t1', 'baseProgressBps': 6400, 'progressBps': 6400, 'notes': 'Original', 'operationDate': '2026-01-01'}
        self.assertEqual(self.request('/api/reports', report)[0], 200)
        note = {'id': str(uuid.uuid4()), 'reportId': rid, 'note': 'Aclaración separada'}
        self.assertEqual(self.request('/api/clarifications', note)[0], 200)
        self.assertEqual(self.request('/api/clarifications', note)[0], 200)
        self.assertEqual(self.request('/api/clarifications', {**note, 'note': 'Modificada'})[0], 409)
        data = self.request('/api/reports')[1]
        self.assertEqual(len(data['clarifications']), 1)
        self.assertEqual(data['reports'][0]['payload']['notes'], 'Original')
        self.request('/api/logout', {})
        self.assertEqual(self.request('/api/login', {'initData': self.signed()})[0], 403)
        self.assertEqual(self.request('/api/clarifications', {**note, 'id': str(uuid.uuid4())})[0], 401)

    def test_cross_origin_mutation_rejected(self):
        status, _ = self.request('/api/login', {'user':'tester','password':'prueba-ñ'}, {'Origin':'https://other.example'})
        self.assertEqual(status, 403)

    def signed(self, uid=123, timestamp=None):
        fields = {'auth_date':str(int(timestamp or time.time())), 'user':json.dumps({'id':uid}), 'query_id':'test'}
        check = '\n'.join(f'{k}={v}' for k,v in sorted(fields.items()))
        secret = hmac.new(b'WebAppData', b'fake-test-token', hashlib.sha256).digest()
        fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        return urllib.parse.urlencode(fields)

    def test_miniapp_does_not_bypass_pin_and_disabled_password(self):
        with patch.object(server, 'ALLOWED', set()), patch.object(server, 'telegram', return_value={'status':'member'}) as call:
            self.assertEqual(self.request('/api/login', {'initData': self.signed()})[0], 403)
            call.assert_not_called()
        with patch.dict('os.environ', {'PASSWORD_LOGIN_ENABLED':'false'}):
            self.assertEqual(self.request('/api/login', {'user':'tester','password':'prueba-ñ'})[0], 403)

    def test_telegram_signature_allowlist_and_expiry(self):
        self.assertEqual(self.request('/api/login', {'initData': self.signed()})[0], 403)
        self.assertEqual(self.request('/api/me')[0], 401)
        self.assertEqual(self.request('/api/login', {'initData': self.signed(456)})[0], 403)
        self.assertEqual(self.request('/api/login', {'initData': self.signed(timestamp=time.time()-7200)})[0], 403)
        self.assertEqual(self.request('/api/login', {'initData': self.signed().replace('test','tampered')})[0], 403)

    def test_admin_user_crud_and_pin_login(self):
        people = [{"assignmentId": "assign-ana", "employeeNumber": "EMP-001", "name": "Ana Pérez"}, {"assignmentId": "assign-beto", "employeeNumber": "EMP-002", "name": "Beto López"}]
        self.assertEqual(self.request('/api/admin/users')[0], 401)
        self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})
        with patch.object(server.ADMIN, 'responsibles', return_value=people):
            self.assertEqual(self.request('/api/admin/responsibles')[1]['responsibles'], people)
            self.assertEqual(self.request('/api/admin/users', {'assignmentId': 'assign-ana', 'pin': '1234'})[0], 200)
            users = self.request('/api/admin/users')[1]['users']
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]['username'], 'emp001')
            self.assertEqual(users[0]['employee_number'], 'EMP-001')
            self.assertEqual(users[0]['active'], 1)
            audit = self.request('/api/admin/audit')[1]['entries']
            self.assertTrue(any(entry['action'] == 'user_upsert' and entry['target'] == 'emp001' for entry in audit))
            self.assertEqual(self.request('/api/admin/users', {'assignmentId': 'assign-ana', 'pin': '5678'})[0], 200)
            self.assertEqual(len(self.request('/api/admin/users')[1]['users']), 1)
            self.assertEqual(self.request('/api/admin/users', {'username': 'emp001', 'assignmentId': 'assign-beto', 'pin': '5678'})[0], 200)
            users = self.request('/api/admin/users')[1]['users']
            self.assertEqual([user['username'] for user in users], ['emp002'])
            with server.connection() as db:
                self.assertEqual(db.execute("SELECT assignment_id FROM user_profiles WHERE user='emp002'").fetchone()[0], 'assign-beto')
            audit = self.request('/api/admin/audit')[1]['entries']
            self.assertTrue(any(entry['action'] == 'user_update' and entry['target'] == 'emp002' for entry in audit))
            self.assertEqual(self.request('/api/admin/users/toggle', {'username': 'emp002'})[0], 200)
            self.assertEqual(self.request('/api/admin/users')[1]['users'][0]['active'], 0)
            self.assertEqual(self.request('/api/admin/users/toggle', {'username': 'emp002'})[0], 200)
        self.assertEqual(self.request('/api/logout', {})[0], 200)
        self.assertEqual(self.request('/api/login', {'user': '', 'password': '1234'})[0], 401)
        self.assertEqual(self.request('/api/login', {'user': '', 'password': '5678'})[0], 200)
        self.assertEqual(self.request('/api/logout', {})[0], 200)
        self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})
        self.assertEqual(self.request('/api/admin/users/delete', {'username': 'emp002'})[0], 200)
        self.assertEqual(self.request('/api/logout', {})[0], 200)
        self.assertEqual(self.request('/api/login', {'user': '', 'password': '5678'})[0], 401)

    def test_telegram_cannot_open_an_authenticated_session(self):
        self.assertEqual(self.request('/api/login', {'initData': self.signed()})[0], 403)
        self.assertEqual(self.request('/api/admin/users')[0], 401)
        self.assertEqual(self.request('/api/admin/users', {'assignmentId': 'x', 'pin': '1234'})[0], 401)


if __name__ == '__main__':
    unittest.main()

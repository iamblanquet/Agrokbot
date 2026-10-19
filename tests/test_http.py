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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import server


class AuthTests(unittest.TestCase):
    def test_recovery_routes_require_admin_and_audit_real_actor(self):
        for path in ['/api/admin/health','/api/admin/notifications/pending']:
            self.assertEqual(self.request(path)[0],401)
        for path in ['/api/admin/notifications/resolve','/api/admin/monitor/evidence']:
            self.assertEqual(self.request(path,{})[0],401)
        self.request('/api/login',{'password':'prueba-ñ'})
        with patch.object(server,'is_admin',return_value=False):
            for path in ['/api/admin/health','/api/admin/notifications/pending']:
                self.assertEqual(self.request(path)[0],403)
            for path in ['/api/admin/notifications/resolve','/api/admin/monitor/evidence']:
                self.assertEqual(self.request(path,{})[0],403)
        with server.connection() as db:
            db.execute("INSERT INTO reminder_deliveries VALUES ('job','review','Timeout')")
        status,_=self.request('/api/admin/notifications/resolve',{'id':'job','decision':'sent','note':'Verificado','verified':True})
        self.assertEqual(status,200)
        with server.connection() as db:
            row=db.execute("SELECT actor FROM audit_log WHERE action='notification_resolved'").fetchone()
            self.assertEqual(row[0],'tester')

    def test_health_probe_is_read_only_and_does_not_claim_delivery(self):
        self.request('/api/login',{'password':'prueba-ñ'})
        with patch.object(server,'ERP_MODE','live'),patch.object(server,'TG_MODE','live'),patch.object(server.ERP,'request',return_value={'projects':[]}) as erp,patch.object(server,'telegram',return_value={'id':'group'}) as telegram:
            status,data=self.request('/api/admin/health')
        self.assertEqual(status,200)
        self.assertEqual(data['checks'],{'erp':'reachable','telegram':'reachable'})
        self.assertFalse(data['deliveryVerified'])
        erp.assert_called_once_with('/external/projects')
        telegram.assert_called_once_with('getChat',{'chat_id':server.CHAT_ID})

    def test_incident_permission_is_enforced_and_revocable(self):
        self.assertEqual(self.request('/api/incidents')[0],401)
        self.request('/api/login',{'user':'tester','password':'prueba-ñ'})
        with server.connection() as db:
            db.execute('INSERT INTO app_users VALUES (?,?,?,?,?,?,?)',('tester','hash','Test','1','a',1,'now'))
        with patch.object(server,'is_admin',return_value=False):
            self.assertEqual(self.request('/api/incidents')[0],403)
            self.assertEqual(self.request('/api/incidents/update',{})[0],403)
            self.assertEqual(self.request('/api/admin/incidents/permission',{'user':'tester','enabled':True})[0],403)
        with patch.object(server,'is_admin',return_value=True):
            self.assertEqual(self.request('/api/admin/incidents/permission',{'user':'tester','enabled':True})[0],200)
        with patch.object(server,'is_admin',return_value=False):
            self.assertEqual(self.request('/api/incidents')[0],200)
            self.assertTrue(self.request('/api/me')[1]['canManageIncidents'])
            self.assertEqual(self.request('/api/incidents/update',{})[0],400)
        with patch.object(server,'is_admin',return_value=True):
            self.request('/api/admin/incidents/permission',{'user':'tester','enabled':False})
        with patch.object(server,'is_admin',return_value=False):
            self.assertEqual(self.request('/api/incidents')[0],403)

    def test_push_transfer_requires_subscription_keys_and_detaches_on_request(self):
        self.request('/api/login', {'user':'tester','password':'prueba-ñ'})
        subscription={'endpoint':'https://fcm.googleapis.com/test', 'keys':{
            'p256dh':base64.urlsafe_b64encode(b'x'*65).decode(), 'auth':base64.urlsafe_b64encode(b'y'*16).decode()}}
        with server.connection() as db:
            db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)',(subscription['endpoint'],'previous',json.dumps(subscription)))
        wrong={**subscription,'keys':{**subscription['keys'],'auth':base64.urlsafe_b64encode(b'z'*16).decode()}}
        self.assertEqual(self.request('/api/notifications/subscribe',wrong)[0],409)
        self.assertEqual(self.request('/api/notifications/subscribe',subscription)[0],200)
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT user FROM push_subscriptions').fetchone()[0],'tester')
        self.assertEqual(self.request('/api/notifications/unsubscribe',{'endpoint':subscription['endpoint']})[0],200)
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM push_subscriptions').fetchone()[0],0)

    def test_reminder_preview_and_test_do_not_change_daily_cut(self):
        self.request('/api/login', {'user':'tester','password':'prueba-ñ'})
        snapshot={'day':'2026-10-19','tasks':[{'id':'t','task':'Tarea','project':'Proyecto','responsible':'Ana','assignmentId':'a'}],'unscheduled':0}
        with server.connection() as db:
            db.execute('INSERT INTO app_users VALUES (?,?,?,?,?,?,?)',('worker','hash','Ana','1','a',1,'now'))
            db.execute('INSERT INTO user_profiles VALUES (?,?,?,?,?)',('worker','Ana','1','a','now'))
            db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)',('device','worker','{}'))
        with patch.object(server.REMINDERS,'snapshot',return_value=snapshot), patch.object(server.PUSH,'send') as send:
            with patch.object(server,'is_admin',return_value=False):
                self.assertEqual(self.request('/api/admin/reminders/preview',{})[0],403)
                self.assertEqual(self.request('/api/admin/reminders/test',{})[0],403)
            with patch.object(server,'is_admin',return_value=True):
                status, result=self.request('/api/admin/reminders/preview',{})
                self.assertEqual((status,result['devices']),(200,1))
                self.assertNotIn('payload',json.dumps(result))
                send.assert_not_called()
                self.assertEqual(self.request('/api/admin/reminders/test',{})[1]['sent'],1)
                self.assertIn('PRUEBA',send.call_args.args[1]['title'])
            with server.connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM reminder_runs').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM reminder_deliveries').fetchone()[0],0)

    def test_admin_push_broadcast_active_users_and_partial_failures(self):
        path = '/api/admin/notifications/test'
        with patch.object(server.PUSH, 'send') as send:
            self.assertEqual(self.request(path, {'endpoint':'own'})[0], 401)
            self.request('/api/login', {'user':'tester','password':'prueba-ñ'})
            with server.connection() as db:
                for name, active in [('another',1),('disabled',0)]:
                    db.execute('INSERT INTO app_users VALUES (?,?,?,?,?,?,?)', (name,'hash',name,name,name,active,'now'))
                db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)', ('own','tester',json.dumps({'endpoint':'own'})))
                db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)', ('other','another',json.dumps({'endpoint':'other'})))
                db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)', ('disabled','disabled','{}'))
                db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)', ('orphan','missing','{}'))
            with patch.object(server, 'is_admin', return_value=False):
                self.assertEqual(self.request(path, {'endpoint':'own'})[0], 403)
            with patch.object(server, 'is_admin', return_value=True):
                send.assert_not_called()
                status, body = self.request(path, {})
                self.assertEqual(status, 200)
                self.assertEqual((body['total'],body['sent'],body['failed']), (2,2,0))
                self.assertEqual({c.args[0]['endpoint'] for c in send.call_args_list}, {'own','other'})
                self.assertEqual(send.call_args.args[1]['tag'], 'campo-prueba-admin')
                send.side_effect = [RuntimeError('sensitive provider response'), None]
                status, body = self.request(path, {})
                self.assertEqual((status,body['sent'],body['failed']), (200,1,1))
                self.assertNotIn('sensitive', json.dumps(body))
                with server.connection() as db:
                    db.execute('DELETE FROM push_subscriptions')
                self.assertEqual(self.request(path, {})[1]['total'], 0)

    def test_notification_status_is_authenticated_and_account_scoped(self):
        path = '/api/notifications/status'
        self.assertEqual(self.request(path, {'endpoint':'test'})[0], 401)
        self.request('/api/login', {'user':'tester','password':'prueba-ñ'})
        with server.connection() as db:
            db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)', ('own','tester','{}'))
            db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)', ('other','another','{}'))
        for endpoint, expected in [('own',True),('other',False),('missing',False)]:
            self.assertEqual(self.request(path, {'endpoint':endpoint}), (200, {'subscribed':expected}))

    def test_journal_is_authenticated_and_read_only(self):
        with patch.object(server.ERP, 'request', return_value={'projects':[]}) as erp:
            self.assertEqual(self.request('/api/admin/journal/projects')[0],401)
            erp.assert_not_called()
            self.request('/api/login', {'user':'tester','password':'prueba-ñ'})
            with patch.object(server,'is_admin',return_value=False):
                self.assertEqual(self.request('/api/admin/journal/projects'),(200,{'projects':[]}))
            erp.assert_called_once_with('/external/projects')
            self.assertEqual(self.request('/api/admin/journal/projects',{})[0],404)

    def test_journal_image_no_store_membership_and_errors(self):
        from test_journal import project_fixture
        self.request('/api/login', {'user':'tester','password':'prueba-ñ'})
        with patch.object(server.ERP,'request',return_value=project_fixture()), patch.object(server.ERP,'reference_image',return_value=(b'png','image/png')) as image:
            self.assertEqual(self.request('/api/admin/journal/preview?project=p1&log=log2&attachment=a1')[0],404)
            image.assert_not_called()
            with self.client.open(self.url+'/api/admin/journal/preview?project=p1&log=log1&attachment=a1') as response:
                self.assertEqual(response.read(),b'png')
                self.assertIn('no-store',response.headers['Cache-Control'])
                self.assertEqual(response.headers['Content-Type'],'image/png')
        with patch.object(server.ERP,'request',side_effect=server.RemoteFailure('ERP no disponible')):
            self.assertEqual(self.request('/api/admin/journal/projects')[0],502)
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

    def test_purged_photo_is_proxied_without_persisting(self):
        pid, rid = str(uuid.uuid4()), str(uuid.uuid4())
        self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})
        with server.connection() as db:
            db.execute("INSERT INTO photos(id,report_id,user,data,digest,attachment_id) VALUES (?,?,?,X'','digest','remote-id')", (pid, rid, 'tester'))
        image = b'\xff\xd8\xffremote\xff\xd9'
        with patch.object(server.ERP, 'attachment_file', return_value=image) as fetch:
            with self.client.open(self.url+'/api/photos/'+pid) as response:
                self.assertEqual(response.read(), image)
                self.assertIn('no-store', response.headers['Cache-Control'])
            fetch.assert_called_once_with('remote-id')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT length(data) FROM photos WHERE id=?', (pid,)).fetchone()[0], 0)
        self.request('/api/logout', {})
        with patch.object(server.ERP, 'attachment_file') as fetch:
            self.assertEqual(self.request('/api/photos/'+pid)[0], 401)
            fetch.assert_not_called()
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

    def test_monitor_is_admin_only_and_classifies_transactions(self):
        self.assertEqual(self.request('/api/admin/monitor')[0], 401)
        self.assertEqual(self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})[0], 200)
        old = '2020-01-01T00:00:00+00:00'
        recent = server.now()
        stuck_at = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        with server.connection() as db:
            for rid, state, created in (('r-ok', 'demo_published', recent), ('r-fail', 'telegram_failed', recent), ('r-stuck', 'telegram_sending', stuck_at), ('r-old', 'published', old)):
                db.execute("INSERT INTO reports(id,user,task_id,project_id,payload,state,created,message,error) VALUES (?,?,?,?,?,?,?,?,?)", (rid, 'u', 't', 'demo-stere', '{}', state, created, 'm', 'boom' if state == 'telegram_failed' else None))
        status, data = self.request('/api/admin/monitor')
        self.assertEqual(status, 200)
        self.assertEqual(data['summary'], {'total': 3, 'ok': 1, 'pending': 1, 'review': 0, 'failed': 1, 'stuck': 1})
        self.assertNotIn('payload', data['transactions'][0])
        self.assertEqual([t['id'] for t in self.request('/api/admin/monitor?state=failed')[1]['transactions']], ['r-fail'])
        self.assertEqual([t['id'] for t in self.request('/api/admin/monitor?state=stuck')[1]['transactions']], ['r-stuck'])
        self.assertEqual(self.request('/api/admin/monitor/retry', {'id': 'r-fail'})[1], {'ok': True})
        self.assertEqual(self.request('/api/admin/monitor/retry', {'id': 'r-ok'})[1], {'ok': False})
        with server.connection() as db:
            self.assertEqual(db.execute("SELECT state FROM reports WHERE id='r-fail'").fetchone()[0], 'telegram_pending')

    def test_telegram_cannot_open_an_authenticated_session(self):
        self.assertEqual(self.request('/api/login', {'initData': self.signed()})[0], 403)
        self.assertEqual(self.request('/api/admin/users')[0], 401)
        self.assertEqual(self.request('/api/admin/users', {'assignmentId': 'x', 'pin': '1234'})[0], 401)

    def test_admin_can_resolve_ambiguous_report_and_audit_it(self):
        self.assertEqual(self.request('/api/login', {'user': 'tester', 'password': 'prueba-ñ'})[0], 200)
        with server.connection() as db:
            db.execute("INSERT INTO reports(id,user,task_id,project_id,payload,state,created,message,error) VALUES (?,?,?,?,?,?,?,?,?)", ('r-review', 'campo', 't', 'demo-stere', '{}', 'telegram_review', server.now(), 'm', 'timeout'))
        status, data = self.request('/api/admin/monitor/resolve', {'id': 'r-review', 'decision': 'confirm', 'note': 'Verificado en el grupo.'})
        self.assertEqual(status, 200)
        self.assertEqual(data, {'ok': True, 'state': 'published'})
        with server.connection() as db:
            row = db.execute("SELECT state,error FROM reports WHERE id='r-review'").fetchone()
            self.assertEqual((row['state'], row['error']), ('published', 'Verificado en el grupo.'))
            self.assertTrue(db.execute("SELECT 1 FROM audit_log WHERE action='monitor_resolve' AND target='r-review'").fetchone())


if __name__ == '__main__':
    unittest.main()

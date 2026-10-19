import base64
import hashlib
import json
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import server
from backend.audit import current_actor
from backend.evidence import EvidenceService
from backend.http_client import RemoteFailure
from backend.reminders import Reminders


class AuditFixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(server,'DB',Path(self.temp.name)/'test.sqlite3'),
                      patch.object(server,'ERP_MODE','demo'),patch.object(server,'TG_MODE','demo')]
        for p in self.patches:p.start()
        server.initialize()
        self.token=current_actor.set('system')

    def tearDown(self):
        current_actor.reset(self.token)
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def report(self, rid=None, photos=None, state='erp_review'):
        rid=rid or str(uuid.uuid4())
        payload={'id':rid,'operationDate':'2026-01-01','progressBps':6500,'photos':photos or []}
        with server.connection() as db:
            db.execute('INSERT INTO reports(id,user,task_id,project_id,payload,state,created,message,erp_log_id,message_id) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (rid,'worker','t','p',json.dumps(payload),state,server.now(),'Texto','log','123' if state=='published' else None))
        return rid

    def log(self, rid, attachments=None):
        return {'id':'log','operationDate':'2026-01-01','progressBps':6500,'metadataJson':{'clientReportId':rid},'attachments':attachments or []}

    def project(self, log):
        return {'project':{'activities':[{'tasks':[{'id':'t','operationLogs':[log]}]}]}}

    def test_pin_reset_and_toggle_revoke_existing_sessions(self):
        person={'assignmentId':'a','employeeNumber':'EMP001','name':'Empleado'}
        with patch.object(server.ADMIN,'responsibles',return_value=[person]):
            server.ADMIN.save({'pin':'56781234','assignmentId':'a'})
            for action in ('save','toggle','delete'):
                with server.connection() as db:
                    db.execute('INSERT INTO sessions VALUES (?,?,?)',('session','emp001',time.time()+86400))
                if action=='save':server.ADMIN.save({'username':'emp001','pin':'56781235','assignmentId':'a'})
                else:getattr(server.ADMIN,action)({'username':'emp001'})
                with server.connection() as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
            server.ADMIN.toggle({'username':'emp001'})
            with server.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)

    def test_audit_actor_is_request_context_not_configured_admin(self):
        def record(user):
            token=current_actor.set(user)
            try:server.AUDIT.record('test',user,{})
            finally:current_actor.reset(token)
        threads=[threading.Thread(target=record,args=(u,)) for u in ('alice','bob')]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual({(r['actor'],r['target']) for r in server.AUDIT.entries()},{('alice','alice'),('bob','bob')})

    def test_audit_and_incident_pagination_beyond_500(self):
        with server.connection() as db:
            for i in range(503):
                db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?,?)',(str(i),'worker','test',str(i),'{}','2026-01-01'))
                db.execute('INSERT INTO incidents(id,user,erp_log_id,project_id,task_id,payload,created,updated) VALUES (?,?,?,?,?,?,?,?)',(str(i),'worker','log','p','t','{}','now','now'))
        first=server.INCIDENTS.listing()
        second=server.INCIDENTS.listing(first['nextOffset'])
        self.assertEqual(len({r['id'] for r in first['incidents']+second['incidents']}),503)
        self.assertIsNone(second['nextOffset'])
        self.assertEqual(len({r['target'] for r in server.AUDIT.entries()+server.AUDIT.entries(500)}),503)

    def test_evidence_queue_rotates_past_15_blocked_reports(self):
        for i in range(15):self.report(f'{i:016d}',['missing'],'photos_pending')
        last=self.report('z'*16,[],'photos_pending')
        service=EvidenceService(server.connection,server.LOCK,Mock(),lambda:'demo')
        service.process()
        service.process()
        with server.connection() as db:self.assertEqual(db.execute('SELECT state FROM reports WHERE id=?',(last,)).fetchone()[0],'telegram_pending')

    def test_erp_resolution_validates_reference_and_restores_photo_queue(self):
        rid=self.report(photos=['photo'])
        with patch.object(server.ERP,'request',return_value=self.project(self.log(rid))):
            result=server.MONITOR.resolve(rid,'confirm','Verificado','log')
        self.assertEqual(result['state'],'photos_pending')
        with server.connection() as db:self.assertEqual(db.execute('SELECT erp_log_id FROM reports WHERE id=?',(rid,)).fetchone()[0],'log')

    def test_erp_resolution_rejects_other_report_or_missing_id(self):
        rid=self.report()
        with patch.object(server.ERP,'request',return_value=self.project(self.log('different'))):
            with self.assertRaises(ValueError):server.MONITOR.resolve(rid,'confirm','Verificado','log')
        with self.assertRaises(ValueError):server.MONITOR.resolve(rid,'confirm','Verificado')
        with server.connection() as db:self.assertEqual(db.execute('SELECT state FROM reports WHERE id=?',(rid,)).fetchone()[0],'erp_review')

    def test_erp_resolution_without_photos_still_requires_verified_reference(self):
        rid=self.report()
        with patch.object(server.ERP,'request',return_value=self.project(self.log(rid))):
            self.assertEqual(server.MONITOR.resolve(rid,'confirm','Verificado','log')['state'],'telegram_pending')

    def legacy_photo(self):
        rid=self.report(photos=['photo'],state='published')
        data=b'\xff\xd8\xfftest\xff\xd9'
        with server.connection() as db:
            db.execute('INSERT INTO photos(id,report_id,user,data,digest) VALUES (?,?,?,?,?)',('photo',rid,'worker',data,hashlib.sha256(data).hexdigest()))
        return rid,data

    def test_legacy_inconsistency_is_review_not_success_and_bytes_survive(self):
        rid,data=self.legacy_photo()
        self.assertEqual(server.MONITOR.snapshot()['summary']['review'],1)
        server.initialize()
        server.MEDIA.purge_delivered()
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT state FROM reports WHERE id=?',(rid,)).fetchone()[0],'evidence_review')
            self.assertEqual(db.execute('SELECT data FROM photos').fetchone()[0],data)

    def test_reconcile_matches_remote_digest_without_upload_or_replay(self):
        rid,data=self.legacy_photo()
        log=self.log(rid,[{'id':'attachment','originalFileName':'photo.jpg'}])
        with patch.object(server.ERP,'request',return_value=self.project(log)),patch.object(server.ERP,'attachment_file',return_value=data),patch.object(server.ERP,'upload_attachment') as upload:
            result=server.MONITOR.reconcile_evidence(rid,'Conciliado')
        self.assertEqual(result,{'ok':True,'confirmed':1});upload.assert_not_called()
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT message_id FROM reports').fetchone()[0],'123')
            self.assertEqual(tuple(db.execute('SELECT attachment_id,upload_state,data FROM photos').fetchone()),('attachment','confirmed',data))

    def test_missing_or_different_remote_photo_preserves_local_data(self):
        rid,data=self.legacy_photo()
        for attachments,remote in [([],data),([{'id':'attachment','originalFileName':'photo.jpg'}],b'wrong')]:
            with patch.object(server.ERP,'request',return_value=self.project(self.log(rid,attachments))),patch.object(server.ERP,'attachment_file',return_value=remote):
                with self.assertRaises(ValueError):server.MONITOR.reconcile_evidence(rid,'Verificado')
        with server.connection() as db:self.assertEqual(tuple(db.execute('SELECT data,attachment_id FROM photos').fetchone()),(data,None))

    def test_full_telegram_text_is_persisted_before_photos_and_not_repeated(self):
        rid=self.report(photos=['photo'],state='telegram_pending')
        text='Texto largo '+('x'*1500)+' FINAL IMPORTANTE'
        with server.connection() as db:
            db.execute('UPDATE reports SET message=? WHERE id=?',(text,rid))
            db.execute("INSERT INTO photos(id,report_id,user,data,digest,attachment_id,upload_state) VALUES (?,?,?,?,'digest','attachment','confirmed')",('photo',rid,'worker',b'bytes'))
            db.execute("INSERT INTO topics VALUES ('p','22','Proyecto')")
        with patch.object(server,'TG_MODE','live'),patch.object(server,'telegram',return_value={'message_id':100}) as send,patch.object(server,'telegram_photo',side_effect=[RemoteFailure('rejected'), '101']) as photo:
            server.DELIVERY.deliver()
            server.MONITOR.retry_telegram(rid)
            server.DELIVERY.deliver()
        send.assert_called_once();self.assertEqual(send.call_args.args[1]['text'],text)
        self.assertEqual(photo.call_count,2)
        with server.connection() as db:self.assertEqual(db.execute('SELECT state FROM reports').fetchone()[0],'published')

    def test_topic_definite_failure_recovers_but_ambiguous_stays_for_review(self):
        send=Mock(side_effect=[RemoteFailure('rejected'),{'message_thread_id':22}])
        service=Reminders(server.connection,None,send,'group')
        with self.assertRaises(RemoteFailure):service.topic()
        self.assertEqual(service.topic(),22)
        service.topic_key='incident_topic';send.side_effect=RemoteFailure('timeout',True)
        with self.assertRaises(RemoteFailure):service.topic()
        with self.assertRaises(ValueError):service.topic()
        service.resolve({'topic':'incident_topic','topicId':33,'verified':True,'note':'Encontrado en el grupo'})
        self.assertEqual(service.topic(),33)

    def test_uncertain_notification_retries_only_after_verified_resolution(self):
        send=Mock(side_effect=[RemoteFailure('timeout',True),{'message_id':1}])
        service=Reminders(server.connection,None,send,'group')
        payload={'chat_id':'group','message_thread_id':22,'text':'Original'}
        service.send_notice('old:notice',payload)
        service.send_notice('old:notice',payload)
        self.assertEqual(send.call_count,1)
        with self.assertRaises(ValueError):service.resolve({'id':'old:notice','decision':'retry','note':'No verificado'})
        self.assertTrue(service.resolve({'id':'old:notice','decision':'retry','note':'Proveedor confirma no enviado','verified':True})['ok'])
        service.retry_job('old:notice',Mock())
        service.retry_job('old:notice',Mock())
        self.assertEqual(send.call_count,2)
        self.assertEqual(send.call_args.args[1],payload)

    def test_health_does_not_claim_live_integrations_verified(self):
        with patch.object(server,'ERP_MODE','live'),patch.object(server,'ERP_URL','http://example.invalid'),patch.object(server,'ERP_KEY','test'):
            status,health=server.health()
        self.assertEqual(status,200)
        self.assertEqual(health['checks']['erp'],'configured_not_verified')
        self.assertFalse(health['deliveryVerified'])

    def test_expired_push_removes_subscription_without_retry_loop(self):
        from backend.push import Push
        from pywebpush import WebPushException
        subscription={'endpoint':'https://fcm.googleapis.com/test','keys':{
            'p256dh':base64.urlsafe_b64encode(b'x'*65).decode(),'auth':base64.urlsafe_b64encode(b'y'*16).decode()}}
        with server.connection() as db:
            db.execute('INSERT INTO push_subscriptions VALUES (?,?,?)',(subscription['endpoint'],'worker',json.dumps(subscription)))
        response=Mock(status_code=410)
        push=Push(Path(self.temp.name),'https://campo.test',server.connection)
        service=Reminders(server.connection,None,Mock(),'group')
        with patch('pywebpush.webpush',side_effect=WebPushException('gone',response=response)):
            service.once('push-expired',lambda:push.send(subscription,{'title':'Test'}))
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM push_subscriptions').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT state FROM reminder_deliveries WHERE id='push-expired'").fetchone()[0],'expired')


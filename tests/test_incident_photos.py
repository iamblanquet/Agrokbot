import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import server
from backend.incidents import IncidentService
from backend.http_client import RemoteFailure


class IncidentPhotoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(server,'DB',Path(self.temp.name)/'db.sqlite3'),patch.object(server,'ERP_MODE','demo'),patch.object(server,'TG_MODE','demo')]
        for p in self.patches:p.start()
        server.initialize()
        self.telegram=Mock(return_value={'message_id':12})
        self.photo=Mock(return_value='13')
        self.read=Mock(return_value=b'jpeg-from-erp')
        self.service=IncidentService(server.connection,server.now,self.telegram,'group',server.Problem,self.photo,self.read)
        self.ids=['photo-a','photo-b']
        self.payload={'operationDate':'2026-01-01','photos':self.ids,'details':{'incident':{'description':'Fuga','priority':'high','stopsWork':True}}}
        with server.connection() as db:
            db.execute("INSERT INTO settings VALUES ('incident_topic','33')")
            db.execute('INSERT INTO reports(id,user,task_id,project_id,payload,state,created,erp_log_id,message) VALUES (?,?,?,?,?,?,?,?,?)',
                       ('incident-report','worker','t','p',json.dumps(self.payload),'photos_pending',server.now(),'log','Report'))
            for pid in self.ids:
                db.execute("INSERT INTO photos(id,report_id,user,data,digest,attachment_id,upload_state) VALUES (?,?,?,?,?,?,'confirmed')",
                           (pid,'incident-report','worker',b'jpeg',hashlib.sha256(b'jpeg').hexdigest(),'attachment-'+pid))

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_all_photos_go_to_incidents_once_without_touching_project_receipts(self):
        self.service.tick(True);self.service.tick(True)
        self.telegram.assert_called_once()
        self.assertEqual(self.photo.call_count,2)
        self.assertEqual([c.args[0]['id'] for c in self.photo.call_args_list],self.ids)
        self.assertTrue(all(c.args[1]==33 for c in self.photo.call_args_list))
        self.assertIn('incident-report',self.photo.call_args_list[0].kwargs['caption'])
        self.read.assert_not_called()
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM photos WHERE message_id IS NOT NULL').fetchone()[0],0)
        row=self.service.listing()['incidents'][0]
        self.assertEqual(row['telegramPhotos'],{'total':2,'sent':2})
        self.assertEqual(row['telegramState'],'sent')

    def test_late_photo_waits_for_erp_confirmation_not_for_notice(self):
        with server.connection() as db:
            db.execute("UPDATE photos SET upload_state='pending',attachment_id=NULL WHERE id='photo-b'")
        self.service.tick(True)
        self.telegram.assert_called_once();self.photo.assert_called_once()
        self.assertEqual(self.service.listing()['incidents'][0]['telegramState'],'pending')
        with server.connection() as db:
            db.execute("UPDATE photos SET upload_state='confirmed',attachment_id='attachment-b' WHERE id='photo-b'")
        self.service.tick(True)
        self.assertEqual(self.photo.call_count,2)
        self.telegram.assert_called_once()

    def test_purged_local_photo_uses_erp_without_persisting_copy(self):
        with server.connection() as db:db.execute("UPDATE photos SET data=X''")
        self.service.tick(True);self.service.tick(True)
        self.assertEqual(self.read.call_count,2)
        self.assertTrue(all(c.args[0]['data']==b'jpeg-from-erp' for c in self.photo.call_args_list))
        with server.connection() as db:self.assertEqual(db.execute('SELECT sum(length(data)) FROM photos').fetchone()[0],0)

    def test_definite_failure_retries_only_failed_photo(self):
        self.photo.side_effect=[RemoteFailure('rejected'),'ok','ok']
        self.service.tick(True);self.service.tick(True);self.service.tick(True)
        self.assertEqual([c.args[0]['id'] for c in self.photo.call_args_list],['photo-a','photo-b','photo-a'])
        self.telegram.assert_called_once()

    def test_uncertain_photo_is_not_resent_without_manual_review(self):
        self.photo.side_effect=[RemoteFailure('timeout',True),'ok','ok']
        self.service.tick(True);self.service.tick(True)
        self.assertEqual(self.photo.call_count,2)
        self.assertEqual(self.service.listing()['incidents'][0]['telegramState'],'review')
        self.service.delivery.resolve({'id':'incident:incident-report:photo:photo-a','decision':'retry','note':'Confirmado que no se envió','verified':True})
        self.service.tick(True)
        self.assertEqual(self.photo.call_count,3)

    def test_no_photos_without_confirmed_notice_or_in_demo(self):
        self.service.tick(False)
        self.telegram.assert_not_called();self.photo.assert_not_called()
        self.telegram.side_effect=RemoteFailure('timeout',True)
        self.service.tick(True);self.service.tick(True)
        self.photo.assert_not_called()

    def test_erp_read_failure_retries_without_attempting_telegram_photo(self):
        with server.connection() as db:db.execute("UPDATE photos SET data=X''")
        self.read.side_effect=RemoteFailure('ERP offline',True)
        self.service.tick(True)
        self.photo.assert_not_called()
        self.read.side_effect=None
        self.service.tick(True)
        self.assertEqual(self.photo.call_count,2)

    def test_quarantined_test_reports_never_send(self):
        with server.connection() as db:db.execute("UPDATE reports SET state='evidence_review'")
        self.service.tick(True)
        self.telegram.assert_not_called();self.photo.assert_not_called()

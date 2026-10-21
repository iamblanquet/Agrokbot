import copy
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch
from backend.project_archives import ProjectArchives, finished
from backend.project_pdf import render_dossier
from backend.http_client import RemoteFailure


def example():
    return {'id':'p1','name':'Proyecto de demostración','progressBps':10000,'status':'FINISHED',
            'activities':[{'name':'Campo','tasks':[{'id':'t1','name':'Revisión de terreno',
                'operationLogs':[{'id':'l1','operationDate':'2026-10-20','notes':'Trabajo terminado.',
                                  'attachments':[]}]}]}]}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.db'
        @contextmanager
        def connection():
            db=sqlite3.connect(self.path)
            db.row_factory=sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()
        self.connection=connection
        with connection() as db:
            db.executescript('''
                CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE reports(id TEXT,user TEXT,project_id TEXT,state TEXT,erp_log_id TEXT,payload TEXT,created TEXT);
                CREATE TABLE photos(id TEXT,report_id TEXT,attachment_id TEXT,upload_state TEXT,message_id TEXT,data BLOB);
                CREATE TABLE incidents(id TEXT,project_id TEXT,payload TEXT,created TEXT);
                CREATE TABLE incident_events(id INTEGER,incident_id TEXT,actor TEXT,status TEXT,note TEXT,created TEXT);
                CREATE TABLE clarifications(id TEXT,report_id TEXT,user TEXT,note TEXT,created TEXT);
                CREATE TABLE topics(project_id TEXT,thread_id INTEGER,title TEXT);
                INSERT INTO topics VALUES ('p1',10,'Proyecto');
            ''')
        self.project=example()
        self.erp=Mock()
        self.erp.request.side_effect=lambda path:copy.deepcopy({'projects':[self.project]} if path=='/external/projects' else {'project':self.project})
        self.telegram=Mock(side_effect=lambda method,body: {'message_thread_id':20} if method=='createForumTopic' else {'message_id':30} if method=='sendMessage' else True)
        self.document=Mock(return_value={'message_id':40,'file_id':'file'})
        self.renderer=Mock(return_value=(b'%PDF-test',[]))
        self.service=ProjectArchives(connection,self.erp,self.telegram,self.document,'chat',lambda:'2026-10-21',self.renderer)
        self.service.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        return self.service.listing()['archives'][0]['state']

    def report(self,state='published',payload=None):
        with self.connection() as db:
            db.execute('INSERT INTO reports VALUES (?,?,?,?,?,?,?)',('r1','dev','p1',state,'l1',json.dumps(payload or {}),'2026-10-20'))

    def test_full_flow_once_and_preserves_topic(self):
        self.service.tick()
        self.service.tick()
        self.assertEqual(self.state(),'closed')
        self.document.assert_called_once()
        self.assertEqual([c.args[0] for c in self.telegram.call_args_list],['createForumTopic','sendMessage','editForumTopic','closeForumTopic'])
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM topics').fetchone()[0],1)
            self.assertIsNotNone(db.execute('SELECT pdf FROM project_archives').fetchone()[0])

    def test_project_not_task_completion(self):
        self.project['progressBps']=9900
        self.service.process('p1')
        self.assertEqual(self.state(),'waiting')
        self.document.assert_not_called()
        for value in (None,True,'10000',9999):
            self.assertFalse(finished({'progressBps':value}))

    def test_pending_test_reports_not_resent(self):
        self.report('evidence_review')
        self.service.process('p1')
        self.assertEqual(self.state(),'waiting')
        self.document.assert_not_called()

    def test_incident_must_be_ingested(self):
        self.report(payload={'details':{'incident':{'description':'Fuga'}}})
        self.service.process('p1')
        self.assertEqual(self.state(),'waiting')
        self.document.assert_not_called()

    def test_missing_photo_confirmation_blocks(self):
        self.report(payload={'photos':['a1']})
        self.service.process('p1')
        self.assertEqual(self.state(),'waiting')
        self.document.assert_not_called()

    def test_missing_erp_log_blocks(self):
        self.report()
        self.project['activities'][0]['tasks'][0]['operationLogs']=[]
        self.service.process('p1')
        self.assertEqual(self.state(),'waiting')

    def test_ambiguous_upload_not_repeated_after_restart(self):
        self.document.side_effect=RemoteFailure('timeout',True)
        self.service.tick()
        self.service.initialize()
        self.service.tick()
        self.assertEqual(self.state(),'review')
        self.document.assert_called_once()
        self.assertNotIn('closeForumTopic',[c.args[0] for c in self.telegram.call_args_list])

    def test_definite_rejection_retries(self):
        self.document.side_effect=[RemoteFailure('rejected',False),{'message_id':40}]
        self.service.tick()
        self.service.tick()
        self.assertEqual(self.state(),'closed')
        self.assertEqual(self.document.call_count,2)

    def test_change_during_upload_does_not_close(self):
        def send(*args):
            self.project['name']='Cambiado'
            return {'message_id':40}
        self.document.side_effect=send
        self.service.tick()
        self.service.tick()
        self.assertEqual(self.state(),'review')
        self.document.assert_called_once()
        self.assertNotIn('closeForumTopic',[c.args[0] for c in self.telegram.call_args_list])

    def test_interrupted_action_requires_review(self):
        with self.connection() as db:
            db.execute("INSERT INTO project_archive_actions VALUES ('p1','document','sending',NULL,NULL)")
        self.service.initialize()
        self.service.tick()
        self.document.assert_not_called()
        self.assertEqual(self.state(),'review')

    def test_manual_confirmation_resumes_without_resend(self):
        self.document.side_effect=RemoteFailure('timeout',True)
        self.service.tick()
        self.service.resolve({'projectId':'p1','step':'document','decision':'sent','messageId':40,'verified':True,'note':'Verificado en Telegram'})
        self.service.tick()
        self.assertEqual(self.state(),'closed')
        self.document.assert_called_once()
        with self.assertRaises(ValueError):
            self.service.resolve({'verified':False})

    def test_close_failure_does_not_resend_pdf(self):
        normal=self.telegram.side_effect
        def dispatch(method,body):
            if method=='closeForumTopic':
                raise RemoteFailure('denied',False)
            return normal(method,body)
        self.telegram.side_effect=dispatch
        self.service.tick()
        self.assertEqual(self.state(),'review')
        self.telegram.side_effect=normal
        self.service.tick()
        self.assertEqual(self.state(),'closed')
        self.document.assert_called_once()
        self.assertEqual([c.args[0] for c in self.telegram.call_args_list].count('sendMessage'),1)

    def test_safe_rejection_can_rebuild_changed_source(self):
        self.document.side_effect=[RemoteFailure('denied',False),{'message_id':40}]
        self.service.tick()
        self.project['name']='Nombre actualizado'
        self.service.tick()
        self.assertEqual(self.state(),'closed')
        self.assertEqual(self.renderer.call_count,2)

    def test_pdf_contains_actual_image(self):
        from PIL import Image
        from pypdf import PdfReader
        image=io.BytesIO()
        Image.new('RGB',(100,80),'green').save(image,format='PNG')
        snapshot=self.service.source('p1')
        snapshot['cutoff']='2026-10-21'
        snapshot['logs'][0]['attachments']=[{'id':'a1'}]
        pdf,warnings=render_dossier(snapshot,lambda _:image.getvalue())
        self.assertEqual(warnings,[])
        self.assertGreaterEqual(sum(len(page.images) for page in PdfReader(io.BytesIO(pdf)).pages),1)

    def test_document_transport_and_ambiguous_response(self):
        from backend.telegram import TelegramClient
        client=TelegramClient(None,lambda:{'token':'synthetic','chat_id':'chat'})
        response=io.BytesIO(json.dumps({'ok':True,'result':{'message_id':9,'document':{'file_id':'file'}}}).encode())
        with patch('urllib.request.urlopen',return_value=response) as send:
            self.assertEqual(client.document(b'%PDF-test',20,'test.pdf','Prueba')['message_id'],9)
            request=send.call_args.args[0]
            self.assertIn(b'name="document"',request.data)
            self.assertIn(b'name="message_thread_id"',request.data)
        with patch('urllib.request.urlopen',side_effect=TimeoutError):
            with self.assertRaises(RemoteFailure) as caught:
                client.document(b'%PDF-test',20,'test.pdf','Prueba')
            self.assertTrue(caught.exception.ambiguous)

    def test_pdf_includes_long_notes_missing_images_and_incident_history(self):
        from pypdf import PdfReader
        snapshot=self.service.source('p1')
        snapshot['cutoff']='2026-10-21T12:00:00-06:00'
        snapshot['logs'][0]['notes']=('Observación detallada de campo. '*200)+' FIN_NOTAS'
        snapshot['logs'][0]['attachments']=[{'id':'missing'}]
        snapshot['incidents']=[{'id':'r1','created':'2026-10-20','erp_log_id':'l1','status':'resolved','payload':{'description':'Fuga reparada'},'events':[{'created':'2026-10-21','actor':'Ana','status':'resolved','note':'CIERRE_VERIFICADO'}]}]
        pdf,warnings=render_dossier(snapshot,lambda _:None)
        reader=PdfReader(io.BytesIO(pdf))
        text='\n'.join(page.extract_text() for page in reader.pages)
        for expected in ('FIN_NOTAS','CIERRE_VERIFICADO','Fuga reparada','Imagen no disponible'):
            self.assertIn(expected,text)
        self.assertEqual(len(warnings),1)
        self.assertGreater(len(reader.pages),2)


if __name__=='__main__':
    unittest.main()

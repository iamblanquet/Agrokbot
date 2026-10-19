import io
import base64
import hashlib
import hmac
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import server


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, 'DATA', Path(self.directory.name)), patch.object(server, 'DB', Path(self.directory.name) / 'test.sqlite3'), patch.object(server, 'ERP_MODE', 'demo'), patch.object(server, 'TG_MODE', 'demo')]
        for p in self.patches:
            p.start()
        server.initialize()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.directory.cleanup()

    def payload(self, **updates):
        data = {'id': str(uuid.uuid4()), 'taskId': 'demo-t1', 'baseProgressBps': 6400, 'progressBps': 6500, 'notes': 'Reporte de prueba', 'operationDate': '2026-01-01'}
        data.update(updates)
        return data

    def test_employee_lifecycle_and_offline_history(self):
        employee = server.save_employee({'name': 'Ana Pérez', 'roles': ['operator', 'technician']})
        crew = [{**employee, 'role': 'operator'}]
        updated = server.save_employee({**employee, 'name': 'Ana López', 'roles': ['assistant']})
        with self.assertRaises(server.Problem) as caught:
            server.save_employee({**employee, 'name': 'Edición antigua'})
        self.assertEqual(caught.exception.status, 409)
        server.save_employee(updated, delete=True)
        self.assertEqual(server.catalog()['employees'], [])
        body = self.payload(crew=crew)
        receipt = server.create_report(body, 'dev')
        self.assertEqual(receipt['payload']['crew'][0]['name'], 'Ana Pérez')
        self.assertIn('Operadores: Ana Pérez', receipt['message'])
        server.initialize()
        self.assertEqual(server.create_report(body, 'dev')['id'], receipt['id'])
        self.assertEqual(server.employees(), [])

    def test_invalid_and_duplicate_crew(self):
        employee = server.save_employee({'name': 'Luis', 'roles': ['operator']})
        member = {**employee, 'role': 'operator'}
        for crew in [[member, member], [{**member, 'role': 'assistant'}], [{**member, 'version': 999}], 'invalid']:
            with self.assertRaises(server.Problem):
                server.create_report(self.payload(crew=crew), 'dev')
        for body in [{'name': '', 'roles': ['operator']}, {'name': 'Luis', 'roles': []}, {'name': 'Luis', 'roles': ['unknown']}]:
            with self.assertRaises(server.Problem):
                server.save_employee(body)

    def test_crew_metadata_sent_to_erp(self):
        employee = server.save_employee({'name': 'María', 'roles': ['technician']})
        data = server.catalog()
        with patch.object(server, 'ERP_MODE', 'live'), patch.object(server, 'catalog', return_value=data), patch.object(server, 'erp', return_value={'operationLog': {'id': 'test-log'}}) as api:
            receipt = server.create_report(self.payload(crew=[{**employee, 'role': 'technician'}]), 'dev')
        metadata = api.call_args.args[1]['metadataJson']
        self.assertEqual(metadata['personnelCount'], 1)
        self.assertEqual(metadata['crew'], receipt['payload']['crew'])
        self.assertIn('Técnicos: María', receipt['message'])

    def photo(self, rid):
        pid = str(uuid.uuid4())
        body = {'id': pid, 'reportId': rid, 'data': base64.b64encode(b'\xff\xd8\xfftest-image\xff\xd9').decode()}
        server.save_photo(body, 'dev')
        return body

    def details(self):
        return {'author': 'Abner Díaz', 'title': 'Residente de Campo', 'capturedAt': '2026-09-03T19:20:00Z', 'timezoneOffset': 360, 'offline': True, 'quantity': 2.5, 'unit': 'ha', 'machinery': [{'name': 'Máquina', 'hours': 8, 'liters': 140}]}

    def test_incident_is_in_erp_diary_and_notifies_without_waiting_for_delivery(self):
        from backend.incidents import IncidentService
        from unittest.mock import Mock
        incident={'description':'Fuga en tubería','priority':'high','stopsWork':True}
        body=self.payload(details={**self.details(),'incident':incident})
        catalog=server.catalog()
        with patch.object(server,'ERP_MODE','live'),patch.object(server,'catalog',return_value=catalog),patch.object(server,'erp',return_value={'operationLog':{'id':'erp-incident'}}) as erp:
            server.create_report(body,'dev')
        self.assertEqual(erp.call_args.args[1]['metadataJson']['fieldReport']['incident'],incident)
        self.assertIn('Fuga en tubería',erp.call_args.args[1]['notes'])
        telegram=Mock(return_value={'message_id':5})
        service=IncidentService(server.connection,server.now,telegram,'group',server.Problem)
        with server.connection() as db:
            db.execute("INSERT INTO settings VALUES ('incident_topic','33')")
        service.tick(True);service.tick(True)
        telegram.assert_called_once()
        rows=service.listing()['incidents'];self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['erp_log_id'],'erp-incident')
        with server.connection() as db:
            db.execute("UPDATE reports SET state='published' WHERE id=?",(body['id'],))
        service.tick(True);service.tick(True)
        telegram.assert_called_once()
        self.assertEqual(telegram.call_args.args[1]['message_thread_id'],33)
        self.assertIn('Fuga en tubería',telegram.call_args.args[1]['text'])
        service.update({'id':body['id'],'version':1,'status':'in_progress','note':'Se asignó técnico'},'manager')
        with self.assertRaises(server.Problem):
            service.update({'id':body['id'],'version':1,'status':'resolved','note':'Comentario desactualizado'},'manager')
        service.update({'id':body['id'],'version':2,'status':'resolved','note':'Reparada'},'manager')
        service.update({'id':body['id'],'version':3,'status':'open','note':'Volvió la fuga'},'manager')
        row=service.listing()['incidents'][0]
        self.assertEqual((row['status'],len(row['events'])),('open',4))
        service.tick(True);service.tick(True)
        self.assertEqual(telegram.call_count,4)
        self.assertIn('SEGUIMIENTO DE INCIDENCIA',telegram.call_args_list[2].args[1]['text'])
        self.assertIn('Nuevo estado: Resuelta',telegram.call_args_list[2].args[1]['text'])
        self.assertIn('Reparada',telegram.call_args_list[2].args[1]['text'])
        row=service.listing()['incidents'][0]
        self.assertTrue(all(ev['telegramState']=='sent' for ev in row['events']))

    def test_incident_rejected_erp_never_notifies(self):
        from backend.http_client import RemoteFailure
        body=self.payload(details={**self.details(),'incident':{'description':'Falla','priority':'normal','stopsWork':False}})
        catalog=server.catalog()
        with patch.object(server,'ERP_MODE','live'),patch.object(server,'catalog',return_value=catalog),patch.object(server,'erp',side_effect=RemoteFailure('ERP no disponible')):
            server.create_report(body,'dev')
        server.INCIDENTS.ingest()
        self.assertEqual(server.INCIDENTS.listing()['incidents'],[])

    def test_invalid_incident_is_not_saved(self):
        for incident in [{},{'description':'','priority':'high','stopsWork':False},{'description':'Falla','priority':'urgent','stopsWork':False},{'description':'Falla','priority':'normal','stopsWork':'yes'}]:
            with self.assertRaises(server.Problem):
                server.create_report(self.payload(details={**self.details(),'incident':incident}),'dev')

    def test_field_message_photo_storage_and_metadata(self):
        body = self.payload(details=self.details())
        photo = self.photo(body['id'])
        body['photos'] = [photo['id']]
        catalog = server.catalog()
        with patch.object(server, 'ERP_MODE', 'live'), patch.object(server, 'catalog', return_value=catalog), patch.object(server, 'erp', return_value={'operationLog': {'id': 'test'}}) as api:
            receipt = server.create_report(body, 'dev')
        for text in ['Hora Captura (Sin Internet): 13:20:00 hrs', 'Autor: Abner Díaz - Residente de Campo', 'Avance: 2.5 ha', 'Maquinaria: Máquina: 8 hrs (140 L)']:
            self.assertIn(text, receipt['message'])
        for text in ['Proyecto:', 'Cuenta:', 'Evidencias fotográficas:']:
            self.assertNotIn(text, receipt['message'])
        metadata = api.call_args.args[1]['metadataJson']
        self.assertEqual(metadata['photoCount'], 1)
        self.assertEqual(metadata['fieldReport'], self.details())
        self.assertNotIn(photo['data'], json.dumps(api.call_args.args[1]))
        server.deliver()
        self.assertEqual(server.create_report(body, 'dev')['state'], 'demo_published')

    def test_photo_upload_idempotence_and_ownership(self):
        rid = str(uuid.uuid4())
        photo = self.photo(rid)
        self.assertEqual(server.save_photo(photo, 'dev')['id'], photo['id'])
        with self.assertRaises(server.Problem):
            server.save_photo(photo, 'other')
        with self.assertRaises(server.Problem):
            server.create_report(self.payload(photos=[photo['id']]), 'dev')
        with self.assertRaises(server.Problem):
            server.create_report(self.payload(id=rid, photos=[photo['id']]), 'other')
        with self.assertRaises(server.Problem):
            server.save_photo({**photo, 'data': 'invalid'}, 'dev')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM photos').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0], 0)

    def test_photo_partial_failure_retries_only_unconfirmed_photo(self):
        body = self.payload(details=self.details())
        photos = [self.photo(body['id']), self.photo(body['id'])]
        body['photos'] = [p['id'] for p in photos]
        server.create_report(body, 'dev')
        with server.connection() as db:
            db.execute("INSERT INTO topics VALUES ('demo-stere','123','Proyecto')")
            db.execute("UPDATE reports SET message_id='321',thread_id='123' WHERE id=?", (body['id'],))
            db.execute("UPDATE photos SET message_id='321' WHERE id=?", (photos[0]['id'],))
        with patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'telegram_photo', side_effect=server.RemoteFailure('rechazo', False)) as image:
            server.deliver()
            self.assertEqual(image.call_count, 1)
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT state FROM reports').fetchone()[0], 'telegram_failed')
            db.execute("UPDATE reports SET state='telegram_pending'")
        with patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'telegram_photo', return_value='323') as image:
            server.deliver()
            self.assertEqual(image.call_count, 1)
            self.assertEqual(image.call_args.args[0]['id'], photos[1]['id'])
        self.assertEqual(server.create_report(body, 'dev')['state'], 'published')

    def test_uncertain_photo_is_not_automatically_retried(self):
        body = self.payload()
        body['photos'] = [self.photo(body['id'])['id']]
        server.create_report(body, 'dev')
        with server.connection() as db:
            db.execute("INSERT INTO topics VALUES ('demo-stere','123','Proyecto')")
        with patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'telegram', return_value={'message_id': 321}), patch.object(server, 'telegram_photo', side_effect=server.RemoteFailure('timeout', True)) as image:
            server.deliver()
            server.deliver()
            self.assertEqual(image.call_count, 1)
        server.initialize()
        self.assertEqual(server.create_report(body, 'dev')['state'], 'telegram_review')

    def test_multipart_photo_transport(self):
        photo = {'data': b'\xff\xd8\xffphoto\xff\xd9'}
        with patch.object(server, 'BOT_TOKEN', 'test-token'), patch.object(server, 'CHAT_ID', '-100123'), patch.object(server.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"ok":true,"result":{"message_id":456}}')) as upload:
            self.assertEqual(server.telegram_photo(photo, '123', '321', 'Evidencia 1/1'), '456')
        request = upload.call_args.args[0]
        self.assertTrue(request.full_url.endswith('/sendPhoto'))
        self.assertIn(b'name="message_thread_id"', request.data)
        self.assertIn(b'"message_id": 321', request.data)
        self.assertIn(photo['data'], request.data)
        self.assertIn('multipart/form-data', request.headers['Content-type'])

    def test_stoppage_preserves_progress_and_is_reported(self):
        details = {**self.details(), 'quantity': 0, 'stoppage': {'reason': 'Lluvia', 'description': ''}}
        body = self.payload(progressBps=6400, details=details)
        receipt = server.create_report(body, 'dev')
        self.assertIn('Día sin actividad (Paro)', receipt['message'])
        self.assertIn('Motivo: Lluvia', receipt['message'])
        self.assertEqual(receipt['payload']['details']['stoppage']['reason'], 'Lluvia')
        self.assertEqual(next(t for t in server.catalog()['tasks'] if t['id']=='demo-t1')['progressBps'], 6400)
        self.assertEqual(server.create_report(body, 'dev')['id'], receipt['id'])

    def test_invalid_stoppages_are_rejected(self):
        for quantity, progress, stop in [(1, 6400, {'reason': 'Lluvia'}), (0, 6500, {'reason': 'Lluvia'}), (0, 6400, {'reason': 'Otro'}), (0, 6400, {'reason': 'Inválido'})]:
            with self.assertRaises(server.Problem):
                server.create_report(self.payload(progressBps=progress, details={**self.details(), 'quantity': quantity, 'stoppage': stop}), 'dev')

    def test_rejected_report_cannot_be_modified(self):
        body = self.payload(baseProgressBps=0)
        with self.assertRaises(server.Problem):
            server.create_report(body, 'dev')
        with self.assertRaises(server.Problem) as caught:
            server.create_report({**body, 'baseProgressBps': 6400}, 'dev')
        self.assertEqual(caught.exception.code, 'immutable')
        server.initialize()
        with self.assertRaises(server.Problem) as caught:
            server.create_report({**body, 'notes': 'Cambio posterior'}, 'dev')
        self.assertEqual(caught.exception.code, 'immutable')
        with server.connection() as db:
            self.assertEqual(json.loads(db.execute('SELECT payload FROM submissions').fetchone()[0]), body)

    def test_field_validation(self):
        for changes in [{'quantity': float('nan')}, {'unit': 'invalid'}, {'author': ''}, {'offline': 'yes'}, {'timezoneOffset': 9999}, {'capturedAt': 'invalid'}, {'machinery': [{'name': 'Máquina', 'hours': 25, 'liters': 0}]}]:
            with self.assertRaises(server.Problem):
                server.create_report(self.payload(details={**self.details(), **changes}), 'dev')

    def test_sync_and_retry_do_not_duplicate(self):
        body = self.payload()
        server.create_report(body, 'dev')
        server.deliver()
        repeated = server.create_report(body, 'dev')
        self.assertEqual(repeated['state'], 'demo_published')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM topics').fetchone()[0], 1)

    def test_stale_or_decreasing_progress_rejected(self):
        server.create_report(self.payload(), 'dev')
        for data in [self.payload(), self.payload(baseProgressBps=6500, progressBps=6000)]:
            with self.assertRaises(server.Problem) as caught:
                server.create_report(data, 'dev')
            self.assertEqual(caught.exception.code, 'conflict')
            self.assertEqual(caught.exception.extra['currentProgressBps'], 6500)

    def test_final_report_allowed_and_idempotent_but_new_reports_blocked(self):
        body=self.payload(progressBps=10000)
        receipt=server.create_report(body,'dev')
        self.assertEqual(server.create_report(body,'dev')['id'],receipt['id'])
        with patch.object(server,'erp') as erp:
            with self.assertRaises(server.Problem) as caught:
                server.create_report(self.payload(baseProgressBps=10000,progressBps=10000),'dev')
            self.assertEqual(caught.exception.code,'task_completed')
            erp.assert_not_called()
        server.deliver()
        self.assertEqual(server.create_report(body,'dev')['state'],'demo_published')
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0],1)

    def test_completed_status_or_stale_offline_catalog_cannot_bypass_block(self):
        for status,progress in [('FINISHED',9000),('COMPLETED',9000),('IN_PROGRESS',10000)]:
            with self.subTest(status=status,progress=progress):
                with server.connection() as db:
                    row=db.execute("SELECT payload FROM catalog WHERE kind='task' AND id='demo-t1'").fetchone()
                    task=json.loads(row[0]);task.update(status=status,progressBps=progress)
                    db.execute("UPDATE catalog SET payload=? WHERE kind='task' AND id='demo-t1'",(json.dumps(task),))
                with self.assertRaises(server.Problem) as caught:
                    server.create_report(self.payload(),'dev')
                self.assertEqual(caught.exception.code,'task_completed')

    def test_one_topic_for_multiple_tasks_in_project(self):
        server.create_report(self.payload(), 'dev')
        server.create_report(self.payload(taskId='demo-t2', baseProgressBps=4500, progressBps=4600), 'dev')
        server.deliver()
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM topics').fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM reports WHERE state='demo_published'").fetchone()[0], 2)

    def test_ambiguous_erp_result_is_not_retried(self):
        data = server.catalog()
        body = self.payload()
        with patch.object(server, 'ERP_MODE', 'live'), patch.object(server, 'catalog', return_value=data), patch.object(server, 'erp', side_effect=server.RemoteFailure('timeout', True)) as api:
            first = server.create_report(body, 'dev')
            second = server.create_report(body, 'dev')
            self.assertEqual(first['state'], 'erp_review')
            self.assertEqual(second['state'], 'erp_review')
            self.assertEqual(api.call_count, 1)
            with self.assertRaises(server.Problem) as caught:
                server.create_report(self.payload(), 'dev')
            self.assertEqual(caught.exception.code, 'erp_unresolved')
        server.deliver()
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM topics').fetchone()[0], 0)

    def test_ambiguous_telegram_result_is_not_retried(self):
        server.create_report(self.payload(), 'dev')
        with server.connection() as db:
            db.execute("INSERT INTO topics VALUES ('demo-stere','123','Proyecto')")
        with patch.object(server, 'TG_MODE', 'live'), patch.object(server, 'telegram', side_effect=server.RemoteFailure('timeout', True)) as api:
            server.deliver()
            server.deliver()
            self.assertEqual(api.call_count, 1)
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT state FROM reports').fetchone()[0], 'telegram_review')

    def test_report_id_cannot_be_reassigned(self):
        body = self.payload()
        server.create_report(body, 'dev')
        for modified, user in [(body, 'other'), ({**body, 'notes': 'changed'}, 'dev')]:
            with self.assertRaises(server.Problem) as caught:
                server.create_report(modified, user)
            self.assertEqual(caught.exception.status, 409)

    def test_restart_recovers_inflight_safely(self):
        server.create_report(self.payload(), 'dev')
        with server.connection() as db:
            db.execute("UPDATE reports SET state='telegram_sending'")
        server.initialize()
        with server.connection() as db:
            self.assertEqual(db.execute('SELECT state FROM reports').fetchone()[0], 'telegram_review')


if __name__ == '__main__':
    unittest.main()

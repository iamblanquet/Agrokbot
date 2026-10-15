"""Disposable local UI fixture: python tests/preview_journal.py. No external writes."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from test_journal import project_fixture

temp=tempfile.TemporaryDirectory()
server.DB=Path(temp.name)/'preview.sqlite3'
server.ERP_MODE=server.TG_MODE='demo'
server.USER='dev';server.PASSWORD='test-journal'
server.initialize()
fixture=project_fixture()
logs=fixture['project']['activities'][0]['tasks'][0]['operationLogs']
logs.extend([{**logs[0],'id':f'log-{i}','attachments':[]} for i in range(23)])
server.ERP.request=lambda path,payload=None: {'projects':[fixture['project']]} if path=='/external/projects' else fixture
server.ERP.reference_image=lambda *args: (__import__('base64').b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6zWQAAAAASUVORK5CYII='),'image/png')
print('Journal preview on http://127.0.0.1:8799',flush=True)
server.ThreadingHTTPServer(('127.0.0.1',8799),server.Handler).serve_forever()

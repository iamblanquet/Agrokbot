import unittest
from unittest.mock import Mock
from backend.journal import JournalService, presentation


def project_fixture():
    return {'project': {'id':'p1','folio':'PRJ-001','name':'Proyecto de prueba','activities':[{'name':'Actividad','tasks':[{'id':'t1','name':'Limpieza','code':'T-01','responsibleName':'Responsable', 'operationLogs':[
        {'id':'log1','operationDate':'2026-10-14','reporterName':'Ana','notes':'Registro externo','progressBps':3500,'attachments':[{'id':'a1','mimeType':'image/png','originalFileName':'foto.png'}]},
        {'id':'log2','operationDate':'2026-10-15','metadataJson':{'fieldReport':{'author':'Luis'}},'attachments':[]}
    ]}]}]}}


class JournalTests(unittest.TestCase):
    def test_generated_notes_are_unwrapped_without_losing_free_text(self):
        notes = ('📅 Fecha Operativa: 2026-10-15\n⏰ Hora Captura (Con Internet): 11:15:52 hrs\n'
                 '👤 Responsable: Ana\n📊 Avance: 1 ha\n👥 Cuadrilla (2 personas):\n'
                 '  • Técnicos: Juan\n  • Auxiliares: Luis\n🚜 Maquinaria: Dron: 1 hrs (0 L)\n\n'
                 'Tarea: Preparación\nAvance acumulado: 12 %\nCapturado: 2026-10-15 11:15:52 -0600\n\n'
                 'Prueba\n\nRef: esta línea es parte de la nota\n\nRef: reporte-1')
        result = presentation({'notes': notes}, {}, {})
        self.assertTrue(result['parsed'])
        self.assertEqual(result['reportedBy'], 'Ana')
        self.assertEqual(result['observations'], 'Prueba\n\nRef: esta línea es parte de la nota')
        self.assertEqual(result['clientReference'], 'reporte-1')
        self.assertIn({'label':'Maquinaria','value':'Dron: 1 hrs (0 L)'},result['resources'])

    def test_unknown_or_incomplete_notes_are_preserved(self):
        for notes in ('Responsable: Ana\nPrueba', '📅 Fecha Operativa: 2026-10-15\nTexto', '<script>alert(1)</script>', ''):
            result = presentation({'notes': notes}, {}, {})
            self.assertFalse(result['parsed'])
            self.assertEqual(result['observations'], notes)

    def test_external_entries_are_sorted_without_local_database(self):
        erp=Mock();erp.request.return_value=project_fixture()
        rows=JournalService(erp).entries('p1')['entries']
        self.assertEqual([r['id'] for r in rows],['log2','log1'])
        self.assertEqual(rows[0]['author'],'Luis')
        self.assertEqual(rows[1]['author'],'Ana')
        self.assertEqual(rows[1]['attachments'][0]['id'],'a1')
        erp.request.assert_called_once_with('/external/projects/p1')

    def test_attachment_must_belong_to_selected_entry(self):
        erp=Mock();erp.request.return_value=project_fixture()
        service=JournalService(erp)
        with self.assertRaises(LookupError):service.attachment('p1','log2','a1')
        erp.reference_image.assert_not_called()
        erp.reference_image.return_value=(b'image','image/png')
        self.assertEqual(service.attachment('p1','log1','a1'),(b'image','image/png'))
        erp.reference_image.assert_called_once_with('a1',True)

    def test_project_required(self):
        with self.assertRaises(ValueError):JournalService(Mock()).entries('')

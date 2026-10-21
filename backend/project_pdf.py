"""Bounded, chronological project dossier. No network or persistent image copies."""
import io
from xml.sax.saxutils import escape


def render_dossier(snapshot, image_loader):
    from PIL import Image as PILImage, ImageOps
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
    from pypdf import PdfReader

    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Copy', fontName='Helvetica', fontSize=10, leading=15, spaceAfter=7, splitLongWords=True))
    styles['Title'].textColor = colors.HexColor('#314525')
    styles['Heading2'].textColor = colors.HexColor('#314525')
    story, warnings = [], []
    image_bytes = 0
    labels = {'id':'Identificador','name':'Nombre','code':'Código','folio':'Folio',
              'progressBps':'Avance (puntos base; 10000 = 100 %)','status':'Estado',
              'operationDate':'Fecha operativa','createdAt':'Fecha de registro',
              'notes':'Observaciones','description':'Descripción','priority':'Prioridad',
              'activityName':'Actividad','taskId':'Identificador de tarea','user':'Usuario',
              'created':'Fecha de captura','payload':'Datos de captura','details':'Detalle',
              'responsible':'Responsable','fullName':'Nombre completo',
              'plannedStartDate':'Inicio programado','plannedEndDate':'Fin programado',
              'stopsWork':'Detiene la actividad','author':'Reportó','incident':'Incidencia'}
    states={'open':'Abierta','in_progress':'En seguimiento','resolved':'Resuelta',
            'FINISHED':'Finalizado','high':'Alta','medium':'Media','low':'Baja'}

    def text(value, style='Copy'):
        # Built-in PDF fonts support Spanish; remove decorative emoji, not words.
        value = str(value if value is not None else 'No informado').encode('cp1252', 'ignore').decode('cp1252')
        for part in value.split('\n'):
            story.append(Paragraph(escape(part) or ' ', styles[style]))

    def fields(value):
        if isinstance(value, dict):
            for key, item in value.items():
                text(labels.get(key,key), 'Heading3')
                fields(states.get(item,item) if key in ('status','priority') and isinstance(item,str) else item)
        elif isinstance(value, list):
            for item in value:
                fields(item)
        else:
            text(value)

    project = snapshot['project']
    text('EXPEDIENTE DE CIERRE', 'Title')
    text(project.get('name') or project['id'], 'Heading1')
    text('Folio: '+str(project.get('folio') or project.get('code') or project['id']))
    text('Corte documental: '+snapshot['cutoff']+' (hora de Campeche)')
    state=project.get('status','No informado')
    text(f"Avance ERP: {project['progressBps']/100:g} % | Estado: {states.get(state,state)}")
    text(f"Reportes: {len(snapshot['logs'])} | Incidencias locales: {len(snapshot['incidents'])}")
    opened = sum(i['status'] != 'resolved' for i in snapshot['incidents'])
    text(f'Incidencias abiertas al corte: {opened}. El cierre del proyecto no las resuelve automáticamente.')
    text('Alcance: diario ERP, evidencias disponibles, incidencias y aclaraciones registradas en Campo. No es una copia de las conversaciones de Telegram ni incluye capturas aún sin sincronizar en dispositivos.')
    text('Datos generales', 'Heading2')
    fields({k:v for k,v in project.items() if k != 'activities'})
    text('Tareas del proyecto', 'Heading2')
    for task in snapshot['tasks']:
        text(f"{task.get('code','')} - {task.get('name',task['id'])}", 'Heading3')
        fields({k:v for k,v in task.items() if k != 'operationLogs'})
    story.append(PageBreak())
    text('Reportes en orden cronológico', 'Heading1')
    for number, log in enumerate(snapshot['logs'], 1):
        text(f"{number}. {log.get('operationDate','Sin fecha')} - {log['taskName']}", 'Heading2')
        text('Asiento ERP: '+log['id'])
        fields({k:v for k,v in log.items() if k not in ('id','taskName','attachments','local')})
        if log.get('local'):
            text('Captura original de Campo', 'Heading3')
            fields(log['local'])
        for attachment in log['attachments']:
            label = str(attachment.get('originalFileName') or attachment['id'])
            text('Evidencia: '+label, 'Heading3')
            try:
                raw = image_loader(attachment)
                if not raw or len(raw)>16000000:
                    raise ValueError('Imagen no disponible')
                with PILImage.open(io.BytesIO(raw)) as source:
                    if source.width*source.height > 40000000:
                        raise ValueError('Imagen excesivamente grande')
                    normalized = ImageOps.exif_transpose(source).convert('RGB')
                    normalized.thumbnail((1600,1600))
                    stream = io.BytesIO()
                    normalized.save(stream,format='JPEG',quality=82)
                image_bytes += stream.tell()
                if image_bytes > 40000000:
                    raise MemoryError('Expediente demasiado grande; requiere dividirse antes de enviarlo.')
                stream.seek(0)
                picture = Image(stream)
                scale = min(470/picture.imageWidth, 430/picture.imageHeight)
                picture.drawWidth, picture.drawHeight = picture.imageWidth*scale,picture.imageHeight*scale
                story.extend([picture, Spacer(1,12)])
            except MemoryError:
                raise
            except Exception:
                warning = f'Imagen no disponible o ilegible: {label} (asiento {log["id"]}).'
                warnings.append(warning)
                text(warning)
    story.append(PageBreak())
    text('Incidencias y seguimiento', 'Heading1')
    for incident in snapshot['incidents']:
        text(f"{incident['created']} - Incidencia {incident['id']}", 'Heading2')
        text('Asiento ERP: '+incident['erp_log_id']+' | Estado: '+states.get(incident['status'],incident['status']))
        fields(incident['payload'])
        for event in incident['events']:
            text(f"{event['created']} | {event['actor']} | {states.get(event['status'],event['status'])}", 'Heading3')
            text(event['note'])
    if not snapshot['incidents']:
        text('Sin incidencias locales registradas. Las incidencias incluidas en metadatos ERP se conservan en cada reporte.')
    text('Aclaraciones registradas', 'Heading1')
    for item in snapshot['clarifications']:
        text(f"{item['created']} | {item['user']} | Reporte {item['report_id']}", 'Heading3')
        text(item['note'])
    if not snapshot['clarifications']:
        text('Sin aclaraciones registradas.')
    text('Resumen de cierre y limitaciones', 'Heading1')
    text(f"{len(snapshot['logs'])} reportes; {opened} incidencias sin resolver; {len(warnings)} imágenes no disponibles.")
    for warning in warnings:
        text(warning)
    text('Las evidencias retiradas del ERP y ausentes del almacenamiento local no se pueden reconstruir desde el historial del bot. Las no identificables no pueden enumerarse. Se conserva el tema original de Telegram.')

    def footer(canvas, doc):
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#53634b'))
        canvas.drawString(40,25,'Campo - Expediente documental de cierre')
        canvas.drawRightString(A4[0]-40,25,f'Página {doc.page}')

    SimpleDocTemplate(output,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=40,bottomMargin=45,
                      title='Expediente de cierre',author='Campo').build(story,onFirstPage=footer,onLaterPages=footer)
    result = output.getvalue()
    if len(result)>45000000 or not PdfReader(io.BytesIO(result)).pages:
        raise ValueError('PDF inválido o demasiado grande para enviar.')
    return result, warnings

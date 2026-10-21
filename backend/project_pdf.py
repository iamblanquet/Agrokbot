"""Bounded, chronological project dossier with AgroKool visual identity."""
import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, KeepTogether, PageBreak
)
from pypdf import PdfReader


# AgroKool Corporate Brand Colors
BRAND_PRIMARY = colors.HexColor('#2c4001')       # Deep Forest / Dark Olive
BRAND_PRIMARY_DARK = colors.HexColor('#1e2d01')  # Header dark tint
BRAND_PRIMARY_SOFT = colors.HexColor('#edf4e4')  # Card header soft olive
BRAND_LIME = colors.HexColor('#a1c62e')          # Plant Lime Green accent
BRAND_LIME_SOFT = colors.HexColor('#f3f8e6')     # Subtle lime background
BRAND_GOLD = colors.HexColor('#a87d13')          # Harvest Gold / Ochre
BRAND_GOLD_SOFT = colors.HexColor('#fdf7e7')     # Soft amber
TEXT_PRIMARY = colors.HexColor('#192602')        # Main readable text
TEXT_SECONDARY = colors.HexColor('#536647')      # Secondary / label text
TEXT_MUTED = colors.HexColor('#798d6c')          # Muted timestamps
BG_CARD = colors.HexColor('#f8faf5')             # Off-white / light green card surface
BORDER_LIGHT = colors.HexColor('#d6e2cf')        # Subtle card border
BORDER_ACCENT = colors.HexColor('#b6cca9')       # Stronger border

# Status Badges
STATUS_GREEN_BG = colors.HexColor('#eaf5d8')
STATUS_GREEN_TXT = colors.HexColor('#2c5908')
STATUS_AMBER_BG = colors.HexColor('#fdf5de')
STATUS_AMBER_TXT = colors.HexColor('#8a650d')
STATUS_RED_BG = colors.HexColor('#fde8e5')
STATUS_RED_TXT = colors.HexColor('#9e2a1b')
STATUS_BLUE_BG = colors.HexColor('#e6f0fa')
STATUS_BLUE_TXT = colors.HexColor('#1d5588')


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for running header and dynamic 'Página X de Y' footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        w, h = A4
        margin = 36

        # Running header on page 2 and later
        if self._pageNumber > 1:
            self.setFont('Helvetica-Bold', 7.5)
            self.setFillColor(BRAND_PRIMARY)
            self.drawString(margin, h - 24, 'AGROKOOL CAMPO')
            self.setFont('Helvetica', 7.5)
            self.setFillColor(TEXT_SECONDARY)
            self.drawString(margin + 80, h - 24, '|  Expediente Documental de Cierre')

            # Accent line under header
            self.setStrokeColor(BRAND_LIME)
            self.setLineWidth(1)
            self.line(margin, h - 28, w - margin, h - 28)

        # Running footer on every page
        self.setStrokeColor(BORDER_LIGHT)
        self.setLineWidth(0.6)
        self.line(margin, 30, w - margin, 30)

        self.setFont('Helvetica', 7.5)
        self.setFillColor(TEXT_SECONDARY)
        self.drawString(margin, 20, 'AgroKool Campo  -  Expediente Documental de Cierre de Proyecto')

        self.setFont('Helvetica-Bold', 7.5)
        self.drawRightString(w - margin, 20, f'Pagina {self._pageNumber} de {page_count}')
        self.restoreState()


def clean_str(val):
    if val is None:
        return 'No informado'
    s = str(val).strip()
    return s.encode('cp1252', 'replace').decode('cp1252')


def parse_log_presentation(log):
    notes = log.get('notes') or ''
    match = re.fullmatch(
        r'(?:📅\s*)?Fecha Operativa: [^\n]+\n(?:⏰\s*)?Hora Captura [^\n]+\n'
        r'(?P<body>.*?)\n\nTarea: [^\n]+\nAvance acumulado: [^\n]+\n'
        r'Capturado: (?P<captured>[^\n]+)\n\n(?P<notes>.*?)\n\nRef: (?P<reference>[^\n]+)',
        notes, re.DOTALL)

    local = log.get('local') or {}
    payload = local.get('payload') or {}
    details = payload.get('details') or {}

    author = log.get('reporterName') or details.get('author') or local.get('user') or 'Sin autor informado'
    captured_at = details.get('capturedAt') or local.get('created') or log.get('createdAt') or ''
    crew = payload.get('crew') or details.get('crew') or ''
    quantity = details.get('quantity')
    unit = details.get('unit') or ''
    advance_str = f"{quantity:g} {unit}".strip() if quantity is not None else ''
    machines = details.get('machinery') or ''
    observations = notes

    if match:
        observations = match['notes'].strip()
        captured_at = match['captured'].strip()
        for line in match['body'].splitlines():
            clean_line = line.strip().lstrip('👤📊👥🚜☂• ').strip()
            k, sep, v = clean_line.partition(':')
            if sep:
                k_l = k.strip().lower()
                if 'autor' in k_l or 'responsable' in k_l:
                    author = v.strip()
                elif 'cuadrilla' in k_l:
                    crew = v.strip()
                elif 'maquinaria' in k_l:
                    machines = v.strip()
                elif 'avance' in k_l:
                    advance_str = v.strip()

    return {
        'author': author,
        'capturedAt': captured_at,
        'crew': crew,
        'advance': advance_str,
        'machines': machines,
        'observations': observations or 'Sin observaciones registradas para este asiento.'
    }


def render_dossier(snapshot, image_loader):
    output = io.BytesIO()
    doc_width = 523.27  # A4 width (595.27) - 2 * 36 pt margin

    # Find logo path dynamically
    logo_path = None
    for candidate in [
        Path('public/agrokool-horizontal.png'),
        Path(__file__).resolve().parents[1] / 'public' / 'agrokool-horizontal.png',
        Path(__file__).resolve().parents[2] / 'public' / 'agrokool-horizontal.png',
    ]:
        if candidate.is_file():
            logo_path = candidate
            break

    # Paragraph Styles
    style_title = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=BRAND_PRIMARY)
    style_subtitle = ParagraphStyle('DocSubtitle', fontName='Helvetica', fontSize=8.5, leading=11, textColor=TEXT_SECONDARY)
    style_h1 = ParagraphStyle('DocH1', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=BRAND_PRIMARY, spaceBefore=10, spaceAfter=6)
    style_body = ParagraphStyle('DocBody', fontName='Helvetica', fontSize=8.5, leading=12, textColor=TEXT_PRIMARY)
    style_bold = ParagraphStyle('DocBold', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=TEXT_PRIMARY)
    style_muted = ParagraphStyle('DocMuted', fontName='Helvetica', fontSize=7.5, leading=10, textColor=TEXT_MUTED)
    style_kpi_num = ParagraphStyle('DocKpiNum', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1)
    style_kpi_lbl = ParagraphStyle('DocKpiLbl', fontName='Helvetica-Bold', fontSize=7, leading=9, alignment=1, textColor=TEXT_SECONDARY)
    style_kpi_sub = ParagraphStyle('DocKpiSub', fontName='Helvetica', fontSize=6.5, leading=8, alignment=1, textColor=TEXT_MUTED)
    style_notes = ParagraphStyle('DocNotes', fontName='Helvetica', fontSize=8.5, leading=12.5, textColor=TEXT_PRIMARY)
    style_caption = ParagraphStyle('DocCaption', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, alignment=1, textColor=TEXT_SECONDARY)
    style_badge = ParagraphStyle('DocBadge', fontName='Helvetica-Bold', fontSize=7.5, leading=9, alignment=1)

    story = []
    warnings = []
    image_bytes = 0

    project = snapshot['project']
    project_name = project.get('name') or project.get('id') or 'Proyecto sin nombre'
    project_folio = project.get('folio') or project.get('code') or project['id']
    cutoff = snapshot.get('cutoff', 'Sin fecha')
    progress_bps = project.get('progressBps', 10000)
    progress_pct = f"{progress_bps/100:g} %"
    opened_incidents = sum(i.get('status') != 'resolved' for i in snapshot.get('incidents', []))

    # =========================================================================
    # 1. HEADER BANNER CON IDENTIDAD AGROKOOL
    # =========================================================================
    header_cols = []
    if logo_path and logo_path.is_file():
        try:
            logo_w = 125
            logo_h = 39
            logo_img = Image(str(logo_path), width=logo_w, height=logo_h)
            header_cols.append(logo_img)
        except Exception:
            header_cols.append(Paragraph('<b>AGROKOOL</b>', style_title))
    else:
        header_cols.append(Paragraph('<b>AGROKOOL</b>', style_title))

    header_text_cells = [
        Paragraph('AGROKOOL CAMPO  ·  SISTEMA INTEGRAL DE GESTIÓN', style_muted),
        Paragraph('EXPEDIENTE DE CIERRE DE PROYECTO', style_title),
        Paragraph(f'<b>Folio:</b> {escape(clean_str(project_folio))}   |   <b>Corte:</b> {escape(clean_str(cutoff))} (Hora de Campeche)', style_subtitle)
    ]
    header_table = Table([[header_cols[0], header_text_cells]], colWidths=[135, doc_width - 135])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (1,0), (1,0), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(header_table)

    # Accent corporate bar (Forest Green + Lime Accent + Gold tip)
    bar_table = Table([['', '', '']], colWidths=[doc_width * 0.70, doc_width * 0.22, doc_width * 0.08], rowHeights=[3])
    bar_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), BRAND_PRIMARY),
        ('BACKGROUND', (1,0), (1,0), BRAND_LIME),
        ('BACKGROUND', (2,0), (2,0), BRAND_GOLD),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(bar_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 2. HERO / PROJECT TITLE BANNER
    # =========================================================================
    status_label = 'FINALIZADO' if progress_bps >= 10000 else 'EN SEGUIMIENTO'
    status_badge_p = Paragraph(f'<font color="{STATUS_GREEN_TXT.hexval()}">● {status_label}</font>', style_badge)

    hero_left = [
        Paragraph(f'<b>{escape(clean_str(project_name))}</b>', ParagraphStyle('HeroTitle', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=BRAND_PRIMARY_DARK)),
        Paragraph('Cierre documental definitivo conforme a bitácora y diario ERP', style_muted)
    ]
    hero_table = Table([[hero_left, status_badge_p]], colWidths=[doc_width - 100, 100])
    hero_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (1,0), (1,0), STATUS_GREEN_BG),
        ('LINEBEFORE', (1,0), (1,0), 1, colors.HexColor('#b8dc92')),
        ('LINEAFTER', (1,0), (1,0), 1, colors.HexColor('#b8dc92')),
        ('LINETOP', (1,0), (1,0), 1, colors.HexColor('#b8dc92')),
        ('LINEBELOW', (1,0), (1,0), 1, colors.HexColor('#b8dc92')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(hero_table)
    story.append(Spacer(1, 7))

    # =========================================================================
    # 3. STATS DASHBOARD (4 TARJETAS COMPACTAS COMO LA BITÁCORA)
    # =========================================================================
    total_logs = len(snapshot.get('logs', []))
    total_tasks = len(snapshot.get('tasks', []))
    total_incidents = len(snapshot.get('incidents', []))

    kpi_col_w = doc_width / 4.0
    kpi_cells = [
        [
            Paragraph('AVANCE ERP', style_kpi_lbl),
            Paragraph(f'<font color="{BRAND_PRIMARY.hexval()}">{escape(progress_pct)}</font>', style_kpi_num),
            Paragraph('100 % Ejecutado', style_kpi_sub)
        ],
        [
            Paragraph('BITÁCORA', style_kpi_lbl),
            Paragraph(f'<font color="{BRAND_GOLD.hexval()}">{total_logs}</font>', style_kpi_num),
            Paragraph('Asientos conciliados', style_kpi_sub)
        ],
        [
            Paragraph('TAREAS', style_kpi_lbl),
            Paragraph(f'<font color="{BRAND_PRIMARY.hexval()}">{total_tasks}</font>', style_kpi_num),
            Paragraph('Actividades de obra', style_kpi_sub)
        ],
        [
            Paragraph('INCIDENCIAS', style_kpi_lbl),
            Paragraph(f'<font color="{STATUS_RED_TXT.hexval() if opened_incidents else STATUS_BLUE_TXT.hexval()}">{total_incidents}</font>', style_kpi_num),
            Paragraph(f'{opened_incidents} abiertas al corte', style_kpi_sub)
        ]
    ]
    kpi_table = Table([kpi_cells], colWidths=[kpi_col_w] * 4)
    kpi_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
        ('LINEBEFORE', (0,0), (0,0), 3, BRAND_PRIMARY),
        ('LINEBEFORE', (1,0), (1,0), 3, BRAND_GOLD),
        ('LINEBEFORE', (2,0), (2,0), 3, BRAND_LIME),
        ('LINEBEFORE', (3,0), (3,0), 3, STATUS_RED_TXT if opened_incidents else STATUS_BLUE_TXT),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 4. DATOS GENERALES Y TAREAS DEL PROYECTO
    # =========================================================================
    story.append(Paragraph('Datos generales del proyecto', style_h1))
    meta_rows = [
        [Paragraph('<b>Identificador:</b>', style_bold), Paragraph(escape(clean_str(project.get('id'))), style_body),
         Paragraph('<b>Estado ERP:</b>', style_bold), Paragraph(escape(clean_str(project.get('status', 'Finalizado'))), style_body)],
        [Paragraph('<b>Código / Folio:</b>', style_bold), Paragraph(escape(clean_str(project.get('code') or project_folio)), style_body),
         Paragraph('<b>Avance ERP:</b>', style_bold), Paragraph(f"{progress_bps/100:g} % (10000 bps)", style_body)],
        [Paragraph('<b>Fecha de corte:</b>', style_bold), Paragraph(escape(clean_str(cutoff)), style_body),
         Paragraph('<b>Responsable:</b>', style_bold), Paragraph(escape(clean_str(project.get('responsible') or 'No informado')), style_body)],
    ]
    meta_table = Table(meta_rows, colWidths=[85, (doc_width - 170)/2, 85, (doc_width - 170)/2])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Tareas del proyecto (tabla estructurada)
    story.append(Paragraph('Tareas y actividades registradas', style_h1))
    task_rows = [[
        Paragraph('<b>Código</b>', style_badge),
        Paragraph('<b>Nombre de la tarea</b>', ParagraphStyle('THL', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)),
        Paragraph('<b>Actividad</b>', ParagraphStyle('THL2', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)),
        Paragraph('<b>Avance</b>', style_badge),
        Paragraph('<b>Estado</b>', style_badge)
    ]]
    for idx, t in enumerate(snapshot.get('tasks', [])):
        code = t.get('code') or t.get('id') or f'T-{idx+1}'
        name = t.get('name') or t.get('id')
        act = t.get('activityName') or 'Sin actividad'
        bps = t.get('progressBps', 10000)
        task_rows.append([
            Paragraph(escape(clean_str(code)), style_muted),
            Paragraph(f'<b>{escape(clean_str(name))}</b>', style_body),
            Paragraph(escape(clean_str(act)), style_muted),
            Paragraph(f'{bps/100:g} %', style_body),
            Paragraph('Completada', ParagraphStyle('TCmp', fontName='Helvetica-Bold', fontSize=7.5, textColor=BRAND_PRIMARY))
        ])

    tasks_table = Table(task_rows, colWidths=[65, doc_width * 0.42, doc_width * 0.23, 45, 55])
    tasks_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BRAND_PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (-1,-1), 'CENTER'),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_CARD]),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(tasks_table)

    # Alcance y nota de corte
    story.append(Spacer(1, 7))
    scope_p = Paragraph(
        '<b>Alcance del expediente:</b> Diario ERP conciliado, evidencias fotográficas disponibles, incidencias y aclaraciones registradas en Campo. No incluye conversaciones informales de mensajería ni capturas locales sin sincronizar.',
        style_muted
    )
    story.append(scope_p)

    # Salto de página para comenzar la bitácora ordenada cronológicamente
    story.append(PageBreak())

    # =========================================================================
    # 5. BITÁCORA CRONOLÓGICA DE REPORTES (CARDS ORDENADAS)
    # =========================================================================
    story.append(Paragraph('Bitácora y reportes de obra (orden cronológico)', style_h1))
    story.append(Paragraph('Relación ordenada de asientos del diario ERP y capturas de campo con evidencias fotográficas.', style_subtitle))
    story.append(Spacer(1, 6))

    for number, log in enumerate(snapshot.get('logs', []), 1):
        parsed = parse_log_presentation(log)
        task_name = log.get('taskName') or log.get('taskId') or 'Tarea de campo'
        op_date = log.get('operationDate') or 'Sin fecha operativa'
        log_id = log.get('id', 'Sin asiento')

        card_elements = []

        # Barra superior del asiento
        header_p_left = Paragraph(f'<b>Asiento #{number}  ·  {escape(clean_str(op_date))}</b>  -  {escape(clean_str(task_name))}',
                                  ParagraphStyle('LogH', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=BRAND_PRIMARY))
        header_p_right = Paragraph(f'<b>ID ERP:</b> {escape(clean_str(log_id))}',
                                   ParagraphStyle('LogId', fontName='Helvetica', fontSize=7.5, leading=10, alignment=2, textColor=TEXT_SECONDARY))

        card_header_table = Table([[header_p_left, header_p_right]], colWidths=[doc_width * 0.72, doc_width * 0.28])
        card_header_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BRAND_PRIMARY_SOFT),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LINELEFT', (0,0), (0,0), 3, BRAND_PRIMARY),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        card_elements.append(card_header_table)

        # Meta grid con datos de captura
        meta_items = [
            [Paragraph('<b>Reportó:</b>', style_muted), Paragraph(escape(clean_str(parsed['author'])), style_body),
             Paragraph('<b>Captura:</b>', style_muted), Paragraph(escape(clean_str(parsed['capturedAt'] or op_date)), style_body)]
        ]
        if parsed['crew'] or parsed['advance']:
            meta_items.append([
                Paragraph('<b>Cuadrilla:</b>', style_muted), Paragraph(escape(clean_str(parsed['crew'] or 'Sin cuadrilla')), style_body),
                Paragraph('<b>Avance:</b>', style_muted), Paragraph(escape(clean_str(parsed['advance'] or 'Sin detalle')), style_body)
            ])
        if parsed['machines']:
            meta_items.append([
                Paragraph('<b>Maquinaria:</b>', style_muted), Paragraph(escape(clean_str(parsed['machines'])), style_body),
                Paragraph('', style_body), Paragraph('', style_body)
            ])

        meta_grid_table = Table(meta_items, colWidths=[55, (doc_width - 110)/2, 55, (doc_width - 110)/2])
        meta_grid_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        card_elements.append(meta_grid_table)

        # Caja de observaciones de campo
        obs_text = parsed['observations']
        obs_table = Table([[
            Paragraph('<b>Observaciones de campo:</b><br/>' + escape(clean_str(obs_text)), style_notes)
        ]], colWidths=[doc_width])
        obs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.white),
            ('LINELEFT', (0,0), (0,0), 2.5, BRAND_LIME),
            ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        card_elements.append(obs_table)

        # Aclaraciones vinculadas al reporte
        report_clarifications = [c for c in snapshot.get('clarifications', []) if str(c.get('report_id')) in (str(log_id), str((log.get('local') or {}).get('id')))]
        for cl in report_clarifications:
            cl_p = Paragraph(f'<b>Aclaración de {escape(clean_str(cl.get("user")))} ({escape(clean_str(cl.get("created")))}):</b> {escape(clean_str(cl.get("note")))}', style_body)
            cl_box = Table([[cl_p]], colWidths=[doc_width])
            cl_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), BRAND_GOLD_SOFT),
                ('LINELEFT', (0,0), (0,0), 2.5, BRAND_GOLD),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#ecd498')),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            card_elements.append(Spacer(1, 2))
            card_elements.append(cl_box)

        # Evidencias fotográficas asociadas al reporte
        attachments = log.get('attachments', [])
        for att in attachments:
            label = str(att.get('originalFileName') or att.get('id'))
            try:
                raw = image_loader(att)
                if not raw or len(raw) > 16000000:
                    raise ValueError('Imagen no disponible')
                with PILImage.open(io.BytesIO(raw)) as source:
                    if source.width * source.height > 40000000:
                        raise ValueError('Imagen excesivamente grande')
                    normalized = ImageOps.exif_transpose(source).convert('RGB')
                    normalized.thumbnail((1600, 1600))
                    stream = io.BytesIO()
                    normalized.save(stream, format='JPEG', quality=82)
                image_bytes += stream.tell()
                if image_bytes > 40000000:
                    raise MemoryError('Expediente demasiado grande; requiere dividirse antes de enviarlo.')
                stream.seek(0)
                picture = Image(stream)
                max_w = min(440, doc_width - 20)
                max_h = 250
                scale = min(max_w / picture.imageWidth, max_h / picture.imageHeight)
                picture.drawWidth = picture.imageWidth * scale
                picture.drawHeight = picture.imageHeight * scale

                caption_p = Paragraph(f'Evidencia: <b>{escape(clean_str(label))}</b>', style_caption)
                photo_frame = Table([[picture], [caption_p]], colWidths=[doc_width])
                photo_frame.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
                    ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ]))
                card_elements.append(Spacer(1, 3))
                card_elements.append(photo_frame)
            except MemoryError:
                raise
            except Exception:
                warning = f'Imagen no disponible o ilegible: {label} (asiento {log_id}).'
                warnings.append(warning)
                warn_box = Table([[
                    Paragraph(f'<b>Aviso:</b> Imagen no disponible o ilegible: {escape(clean_str(label))} (asiento {escape(clean_str(log_id))})', ParagraphStyle('WarnTxt', fontName='Helvetica', fontSize=7.5, textColor=STATUS_AMBER_TXT))
                ]], colWidths=[doc_width])
                warn_box.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), STATUS_AMBER_BG),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#ecd498')),
                    ('TOPPADDING', (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ]))
                card_elements.append(Spacer(1, 2))
                card_elements.append(warn_box)

        # KeepTogether keeps card cohesive while ReportLab handles multi-page if necessary
        story.append(KeepTogether(card_elements))
        story.append(Spacer(1, 8))

    # =========================================================================
    # 6. INCIDENCIAS Y SEGUIMIENTO TÉCNICO
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph('Incidencias y seguimiento de obra', style_h1))
    incidents = snapshot.get('incidents', [])

    if not incidents:
        no_inc_p = Paragraph('Sin incidencias registradas en el seguimiento local. Las observaciones operativas se conservan en cada asiento del diario ERP.', style_body)
        no_inc_box = Table([[no_inc_p]], colWidths=[doc_width])
        no_inc_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
            ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(no_inc_box)
    else:
        for incident in incidents:
            inc_id = incident.get('id', 'S/N')
            erp_log = incident.get('erp_log_id', 'S/N')
            status = incident.get('status', 'open')
            status_desc = 'Resuelta' if status == 'resolved' else 'En seguimiento' if status == 'in_progress' else 'Abierta'
            payload = incident.get('payload') or {}
            desc = payload.get('description') or 'Sin descripción'
            priority = (payload.get('priority') or 'media').capitalize()

            inc_header = Table([[
                Paragraph(f'<b>Incidencia {escape(clean_str(inc_id))}</b>  ·  Asiento ERP: {escape(clean_str(erp_log))}', ParagraphStyle('IncH', fontName='Helvetica-Bold', fontSize=9, textColor=BRAND_PRIMARY)),
                Paragraph(f'<b>Prioridad:</b> {escape(clean_str(priority))}   |   <b>Estado:</b> {escape(clean_str(status_desc))}', ParagraphStyle('IncSt', fontName='Helvetica', fontSize=8, alignment=2, textColor=STATUS_GREEN_TXT if status == 'resolved' else STATUS_RED_TXT))
            ]], colWidths=[doc_width * 0.60, doc_width * 0.40])
            inc_header.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), STATUS_GREEN_BG if status == 'resolved' else STATUS_RED_BG),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))

            desc_box = Table([[
                Paragraph(f'<b>Detalle del reporte:</b> {escape(clean_str(desc))}', style_body)
            ]], colWidths=[doc_width])
            desc_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))

            inc_elements = [inc_header, desc_box]

            # Timeline de eventos
            events = incident.get('events', [])
            if events:
                event_rows = [[
                    Paragraph('<b>Fecha</b>', style_badge),
                    Paragraph('<b>Responsable / Actor</b>', ParagraphStyle('THAct', fontName='Helvetica-Bold', fontSize=7.5, textColor=BRAND_PRIMARY)),
                    Paragraph('<b>Estado</b>', style_badge),
                    Paragraph('<b>Acción / Observación</b>', ParagraphStyle('THObs', fontName='Helvetica-Bold', fontSize=7.5, textColor=BRAND_PRIMARY))
                ]]
                for ev in events:
                    ev_st = ev.get('status', '')
                    ev_st_lbl = 'Resuelta' if ev_st == 'resolved' else 'Abierta' if ev_st == 'open' else ev_st
                    event_rows.append([
                        Paragraph(escape(clean_str(ev.get('created'))), style_muted),
                        Paragraph(escape(clean_str(ev.get('actor'))), style_body),
                        Paragraph(escape(clean_str(ev_st_lbl)), style_bold),
                        Paragraph(escape(clean_str(ev.get('note'))), style_body)
                    ])
                ev_table = Table(event_rows, colWidths=[65, 85, 55, doc_width - 205])
                ev_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), BRAND_PRIMARY_SOFT),
                    ('BOX', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
                    ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
                    ('TOPPADDING', (0,0), (-1,-1), 2.5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
                    ('LEFTPADDING', (0,0), (-1,-1), 4),
                    ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ]))
                inc_elements.append(ev_table)

            story.append(KeepTogether(inc_elements))
            story.append(Spacer(1, 6))

    # =========================================================================
    # 7. RESUMEN DE CIERRE Y LIMITACIONES DOCUMENTALES
    # =========================================================================
    story.append(Spacer(1, 8))
    story.append(Paragraph('Resumen documental y limitaciones del expediente', style_h1))

    summary_text = (
        f'<b>Cierre documental:</b> {total_logs} reportes conciliados; {opened_incidents} incidencias sin resolver al corte; '
        f'{len(warnings)} evidencias fotográficas no disponibles o ilegibles.<br/>'
        'Las evidencias retiradas del ERP y ausentes del almacenamiento local no se pueden reconstruir desde el historial del bot. '
        'Las capturas aún no sincronizadas en dispositivos móviles no forman parte de este corte. '
        'Se conserva el tema original de Telegram y su historial completo para auditoría.'
    )
    if warnings:
        summary_text += '<br/><br/><b>Advertencias de evidencias:</b><br/>' + '<br/>'.join(f'• {escape(clean_str(w))}' for w in warnings)

    summary_box = Table([[Paragraph(summary_text, style_body)]], colWidths=[doc_width])
    summary_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
        ('BOX', (0,0), (-1,-1), 1, BORDER_ACCENT),
        ('LINELEFT', (0,0), (0,0), 3.5, BRAND_PRIMARY),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 9),
        ('RIGHTPADDING', (0,0), (-1,-1), 9),
    ]))
    story.append(summary_box)

    # Construir documento
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title='Expediente de Cierre de Proyecto',
        author='AgroKool Campo'
    )
    doc.build(story, canvasmaker=NumberedCanvas)
    result = output.getvalue()

    if len(result) > 45000000 or not PdfReader(io.BytesIO(result)).pages:
        raise ValueError('PDF inválido o demasiado grande para enviar.')

    return result, warnings

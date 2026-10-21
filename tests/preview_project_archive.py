"""Generate a synthetic dossier and page images; no ERP/Telegram requests."""
import io
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from backend.project_pdf import render_dossier


def main():
    root=Path(__file__).resolve().parents[1]
    target=root/'output'/'pdf'
    target.mkdir(parents=True,exist_ok=True)
    picture=Image.new('RGB',(1200,650),'#e6eddf')
    draw=ImageDraw.Draw(picture)
    draw.rectangle((90,90,1110,560),outline='#365528',width=8)
    draw.text((130,150),'EVIDENCIA SINTETICA - NO ES UN REPORTE REAL',fill='#365528',font_size=28)
    stream=io.BytesIO()
    picture.save(stream,format='PNG')
    snapshot={'project':{'id':'DEMO-001','name':'Demostración del expediente de cierre','progressBps':10000,'status':'FINISHED'},
              'cutoff':'2026-10-21T12:00:00-06:00','tasks':[{'id':'T-1','name':'Inspección del sistema de riego'}],
              'logs':[{'id':'ERP-DEMO-1','taskName':'Inspección del sistema de riego','operationDate':'2026-10-20',
                       'notes':'Se detectó una fuga durante la inspección. Se sustituyó la conexión y se verificó la presión de trabajo.',
                       'attachments':[{'id':'foto1','originalFileName':'Evidencia de demostración'},{'id':'missing','originalFileName':'Ejemplo de imagen no disponible'}]}],
              'incidents':[{'id':'INC-DEMO-1','created':'2026-10-20','erp_log_id':'ERP-DEMO-1','status':'resolved',
                            'payload':{'description':'Fuga en conexión principal','priority':'high'},
                            'events':[{'created':'2026-10-20','actor':'Ana Pérez','status':'open','note':'Se detuvo el riego para revisar la conexión.'},
                                      {'created':'2026-10-21','actor':'Luis García','status':'resolved','note':'Conexión sustituida. Prueba de presión satisfactoria.'}]}],
              'clarifications':[{'created':'2026-10-21','user':'Ana Pérez','report_id':'ERP-DEMO-1','note':'El trabajo quedó revisado por supervisión.'}]}
    pdf,warnings=render_dossier(snapshot,lambda a:stream.getvalue() if a['id']=='foto1' else None)
    path=target/'expediente-demostracion.pdf'
    path.write_bytes(pdf)
    import pymupdf
    pages=root/'tmp'/'pdfs'
    pages.mkdir(parents=True,exist_ok=True)
    with pymupdf.open(stream=pdf,filetype='pdf') as document:
        for index,page in enumerate(document):
            page.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(str(pages/f'expediente-{index+1}.png'))
        print(f'{path}\nPages: {len(document)}; missing images: {len(warnings)}')


if __name__=='__main__':
    main()

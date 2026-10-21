# Expedientes de proyectos finalizados

El trabajador revisa el ERP cada cinco minutos cuando ERP y Telegram están en modo
`live`. Se puede desactivar con `PROJECT_ARCHIVES_ENABLED=false` (por defecto true).
No utiliza los porcentajes de una sola tarea para cerrar un proyecto: exige
`progressBps >= 10000` en el proyecto y descarta proyectos cancelados.

## Condiciones y contenido

- Consulta de nuevo el proyecto, tareas, diario y referencias de evidencias.
- Espera a que todos los reportes locales estén publicados y conciliados con su
  asiento ERP. Los reportes de prueba en revisión no se reenvían ni se eliminan.
- Espera confirmación de las fotografías declaradas y registro de las incidencias.
- Genera un PDF cronológico con datos de proyecto/tareas, diario completo,
  imágenes disponibles, capturas originales, incidencias, eventos y aclaraciones.
- Expone fecha de corte en hora de Campeche, incidencias abiertas e imágenes
  conocidas que no se pudieron obtener. No resuelve incidencias automáticamente.
- Conserva PDF, instantánea y SHA-256 en SQLite. Se incluyen en el respaldo normal
  de la base. No guarda copias adicionales individuales de fotografías.

El expediente no incluye conversaciones del grupo ni reportes que todavía estén
sin sincronizar en un dispositivo. Evidencias eliminadas del ERP y sin copia local
no se recuperan del historial de Telegram. El PDF declara estas limitaciones.
Las imágenes se normalizan a JPEG de hasta 1600 px. Si excede el presupuesto de
40 MB de imágenes o 45 MB de PDF, se bloquea sin enviar un expediente truncado ni
cerrar el tema; requiere una futura división del expediente.

## Publicación y seguridad

1. Crea/reutiliza el tema `Proyectos finalizados`.
2. Envía el PDF y persiste el identificador confirmado del mensaje.
3. Consulta nuevamente los datos; si cambiaron, deja el tema abierto para revisión.
4. Publica un resumen en el tema original, lo renombra `✅ Finalizado · Nombre`
   y lo cierra. No borra temas, mensajes, reportes ni fotografías.

El bot necesita permisos para enviar documentos y gestionar temas. El tema cerrado
sigue existiendo y su historial continúa accesible. No se oculta ni se elimina.
Cada acción tiene su propio recibo persistente. Un error ambiguo o una interrupción
durante el envío exige conciliación manual; no se repite automáticamente un envío
posiblemente exitoso. Rechazos definitivos se reintentan en la siguiente revisión.
Los cambios previos al primer envío seguro regeneran el PDF. Cambios posteriores
al envío no sustituyen automáticamente el expediente histórico ni cierran el tema.

## Administración (API autenticada, solo administrador)

- `GET /api/admin/project-archives`: estado y recibos, sin contenido del PDF.
- `GET /api/admin/project-archives/pdf?projectId=ID`: descarga la copia verificada.
- `POST /api/admin/project-archives/resolve`: conciliación con `verified:true`,
  `note`, `projectId`, `step` (`document`, `summary`, `rename`, `close`) y
  `decision` (`sent` o `retry`). Para confirmar mensajes añade `messageId`.
  Nunca marcar `retry` sin verificar que la operación no se realizó en Telegram.
- Para creación ambigua del tema: `step:"topic"`, `verified:true`, `note` y
  `topicId`; cero significa que se verificó que el tema no existe.

Las conciliaciones quedan en auditoría. No se ha añadido una pantalla nueva para
estos endpoints. Un expediente cuyo contenido cambió después de publicarse queda
en revisión y requiere decisión administrativa, no una repetición automática.

## Pruebas locales

`python -m unittest discover -s tests -p test_project_archives.py`
valida elegibilidad, esperas, envío único, reinicios, conciliación, cambios durante
la publicación y contenido PDF. `python tests/preview_project_archive.py` genera
una muestra sintética en `output/pdf` y páginas PNG en `tmp/pdfs`, sin envíos reales.

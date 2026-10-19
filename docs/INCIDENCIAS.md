# Incidencias de campo

La casilla Reportar incidencia forma parte del reporte inmutable. Guarda
descripción (1–800 caracteres), prioridad e impacto en details.incident. Funciona
en la misma cola IndexedDB y conserva sus fotos cuando no hay conexión. El paro
operativo es independiente: una incidencia que detiene una actividad no implica
necesariamente una jornada completa sin avance.

## Diario ERP

Se utiliza la ruta documentada de operation-log: el texto queda en notes y los
datos estructurados en metadataJson.fieldReport.incident. No se crea un asiento
adicional ni se modifica el avance por gestionar el seguimiento. Las fotografías
continúan asociadas al asiento original por la API de evidencias.

La documentación suministrada NO define una API externa de gestión de incidencias
del ERP. No se inventa un incidentId nativo ni se enlazan adjuntos a ese modelo.
Los comentarios y cambios de estado posteriores se guardan en esta aplicación,
vinculados al identificador del asiento; no modifican el diario original.

## Telegram

El worker registra una incidencia local por report.id únicamente tras confirmar
ERP. Espera a que el reporte y sus fotografías terminen su publicación normal
antes de enviar un aviso textual al tema Incidencias. No duplica fotografías ni
crea copias locales nuevas. Los registros ERP inciertos/rechazados no se publican.

settings.incident_topic conserva el tema. Si no existe configuración, el primer
envío crea Incidencias una sola vez. Si ya existe un tema creado manualmente,
registrar su ID antes del primer envío para evitar otro tema con el mismo nombre.
El ledger reminder_deliveries usa incident:<reportId>; los resultados ambiguos
quedan en review y no se reenvían automáticamente. La ventana muestra ese estado.
Los cambios de seguimiento no generan nuevos avisos en Telegram.

## Seguimiento y permisos

Administración permite conceder/revocar Gestionar incidencias sin cambiar PIN.
El permiso da acceso global a las incidencias capturadas por esta aplicación:
consulta, comentarios, estados Abierta / En atención / Resuelta y reapertura.
Los administradores también tienen acceso. El servidor valida sesión, cuenta
activa y permiso en cada petición, no solo al mostrar el menú. La captura no
requiere permiso de seguimiento. Los usuarios sin permiso no acceden a la lista.

Los comentarios son obligatorios para actualizar y quedan en incident_events
con actor y fecha. version impide sobrescribir una modificación concurrente.
La ventana requiere internet y muestra hasta las 500 incidencias más recientes.
El esquema se añade sin borrar reportes existentes. Respaldar el volumen /data.

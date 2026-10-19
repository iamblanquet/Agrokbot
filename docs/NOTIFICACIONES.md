# Avisos diarios

Activación en producción: `REMINDERS_ENABLED=true` en .env y recrear el servicio.
El proceso revisa cada minuto: lunes a sábado a partir de las 21:00, zona
America/Mexico_City. Si reinicia después de las 21:00 recupera el corte de ese día,
no días anteriores. La primera consulta exitosa fija el corte; no cambia por
reportes enviados después. La entrega del push depende del dispositivo y de su conexión.

Programadas = plannedStartDate <= fecha operativa <= plannedEndDate, inclusive.
No incluye finalizadas/canceladas ni fechas ausentes/inválidas. Un asiento con
operationDate del día cuenta independientemente de su origen o de sus fotografías.
Se exige operationLogs completo; un fallo del ERP no se interpreta como ausencia.

El tema Tablero se crea una sola vez y se conserva en settings.reminder_topic.
No se puede detectar automáticamente un tema homónimo creado manualmente con Bot API;
si ya existe, registrar su message_thread_id antes de activar.

Los usuarios activan los avisos en Conexiones. Solo cuentas activas relacionadas
por assignment_id/employee_number reciben avisos propios. No se asignan por nombre.
El consentimiento se obtiene por dispositivo; iOS requiere la PWA instalada.
La clave privada push-vapid.pem se conserva en /data y debe incluirse en respaldos.

reminder_runs guarda el corte; reminder_deliveries registra sent/retry/review/sending.
Rechazos inequívocos de Telegram se reintentan cada minuto. Envíos inciertos y
caídas durante un envío requieren revisión manual para no duplicar mensajes.
No hay garantía de entrega exactamente una vez por servicios externos.
Las suscripciones caducadas y fallos push quedan para revisión; no se reenvían
automáticamente. Desactivar y volver a activar renueva la suscripción del dispositivo.

Antes de activar: comprobar permisos del bot para gestionar temas, generar VAPID,
crear Tablero, verificar una suscripción real y hacer una prueba consentida.

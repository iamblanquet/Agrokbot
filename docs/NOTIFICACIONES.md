# Avisos diarios

Activación en producción: `REMINDERS_ENABLED=true` en .env y recrear el servicio.
El proceso revisa cada minuto, lunes a sábado, zona America/Mexico_City:

- 07:30: planificación del día en Tablero y push de tareas propias por usuario.
- 21:00: solo push a responsables de tareas programadas sin reporte recibido.
- 21:30: resumen en Tablero de reportes del día, avance acumulado del último
  reporte por tarea y pendientes sin reporte. Reportada no significa finalizada.

Cada horario consulta el ERP por separado y conserva su primer corte exitoso.
Un reporte recibido entre 21:00 y 21:30 entra en el resumen. Incluye también
tareas reportadas hoy que no estaban programadas para hoy. No se infiere trabajo
realizado si no existe reporte en ERP. La planificación incluye tareas finalizadas
programadas para hoy, pero no canceladas; los pendientes excluyen ambas.
Un reinicio recupera la planificación desde 07:30 hasta antes de 21:00 y los cortes
nocturnos después de su hora, solo del día actual. Nunca recupera días anteriores
ni envía en domingo. La entrega del push depende del dispositivo y su conexión.

Programadas = plannedStartDate <= fecha operativa <= plannedEndDate, inclusive.
No incluye finalizadas/canceladas ni fechas ausentes/inválidas. Un asiento con
operationDate del día cuenta independientemente de su origen o de sus fotografías.
Se exige operationLogs completo; un fallo del ERP no se interpreta como ausencia.

El tema Tablero se crea una sola vez y se conserva en settings.reminder_topic.
No se puede detectar automáticamente un tema homónimo creado manualmente con Bot API;
si ya existe, registrar su message_thread_id antes de activar.

Los usuarios activan los avisos con la campana. Solo cuentas activas relacionadas
por assignment_id/employee_number reciben avisos propios. No se asignan por nombre.
El consentimiento se obtiene por dispositivo; iOS requiere la PWA instalada.
La clave privada push-vapid.pem se conserva en /data y debe incluirse en respaldos.

reminder_runs guarda los cortes: fecha para 21:00, fecha:morning para 07:30 y
fecha:evening para 21:30. Se conservan las claves anteriores del push de las 21:00
para evitar reenvíos tras actualizar. reminder_deliveries registra sent/retry/review/sending.
Rechazos inequívocos de Telegram se reintentan cada minuto. Envíos inciertos y
caídas durante un envío requieren revisión manual para no duplicar mensajes.
No hay garantía de entrega exactamente una vez por servicios externos.
Las suscripciones caducadas y fallos push quedan para revisión; no se reenvían
automáticamente. Desactivar y volver a activar renueva la suscripción del dispositivo.

Antes de activar: comprobar permisos del bot para gestionar temas, generar VAPID,
crear Tablero, verificar una suscripción real y hacer una prueba consentida.

## Descarga automática para campo

El inicio de sesión y la apertura sincronizan sin botón adicional. Al recuperar
internet o volver a la ventana se actualiza automáticamente; eventos de foco
se agrupan durante 30 segundos. El push matutino solicita sincronizar a ventanas
abiertas. Con la PWA cerrada no se garantiza ejecución en segundo plano; al abrir
se descarga, siempre que haya internet y sesión válida.

Antes de procesar la cola se descargan catálogo, tareas, empleados, configuración
y reportes. El snapshot y la fecha offlineSavedAt se confirman en IndexedDB antes
de mostrar datos guardados. Un fallo de red o almacenamiento conserva el catálogo
anterior y muestra el error. Se advierte si los datos guardados son de otro día.
Actualizar catálogo no borra reportes ni fotos pendientes: siguen su flujo previo
de envío y confirmación. La aceptación de un push no confirma descarga local.

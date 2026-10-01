# Campo · prototipo Docker

PWA de seguimiento de proyectos con captura offline, acceso de usuarios de campo por PIN, registro en ERP y publicación de reportes en temas de Telegram. La configuración inicial es **demo**: no usa la clave del documento ni escribe en sistemas externos.

## Ejecutar

Requiere Docker Desktop con motor Linux encendido. Desde esta carpeta:

```powershell
docker compose up --build -d
```

Abre **http://localhost:8787**.

- Administrador: `USER` y el PIN administrativo (`APP_PASSWORD`) definidos en `.env`.
- Usuarios de campo: el PIN creado desde **Administración**; el empleado y su asignación se seleccionan desde el catálogo ERP.

No requiere instalar paquetes de Python o Node. El servidor usa Python 3.12 y su biblioteca estándar. La base SQLite y la cola del bot viven en el volumen `campo-data`; sobreviven a reinicios y a `docker compose down` sin `-v`.

```powershell
docker compose ps
docker compose logs --tail 50 campo
docker compose stop
docker compose start
```

Si necesitas cambiar puerto o credenciales, copia `.env.example` a `.env`, edítalo y vuelve a levantar Compose. `.env` está excluido de Git y del contexto Docker. El puerto está limitado a `127.0.0.1` por defecto.

## Recorrido de prueba

1. Entra y comprueba que aparecen dos proyectos y seis tareas.
2. Abre **Conexiones** y activa **Simular modo offline**.
3. En **Proyectos**, pulsa **Reportar** en una tarea. Escribe fecha, avance acumulado y observaciones.
4. El reporte aparece como **Pendiente de sincronizar** en **Mis reportes**. Recarga: se conserva en IndexedDB.
5. Desactiva la simulación. La app sincroniza; también puedes usar **Sincronizar**.
6. El worker publica en unos segundos. **Temas de Telegram** muestra un tema por proyecto y el contenido exacto del reporte simulado.
7. Para probar una desconexión real, después de la primera carga detén el contenedor con `docker compose stop`. Recarga la página y captura un reporte. Arranca con `docker compose start` y pulsa Sincronizar.

El primer acceso y la descarga del catálogo necesitan conexión. El modo offline usa los datos de la última sesión en ese dispositivo; no valida contraseñas sin red. Al sincronizar se exige una sesión válida. La app debe estar abierta para sincronizar: no promete envío con la app cerrada. No borres los datos del navegador si quedan pendientes; se pueden exportar en JSON desde Mis reportes.

## Componentes

```text
PWA / Mini App
  ├── Service worker: interfaz disponible sin servidor
  ├── IndexedDB: catálogo, copia de recibos y reportes pendientes
  └── HTTP con sesión → servidor Python
                         ├── SQLite: usuarios de sesión, catálogo, reportes y temas
                         ├── Adaptador ERP: demo o API externa
                         └── Cola persistente → Bot API → supergrupo → tema del proyecto
```

La misma interfaz se adapta a escritorio y móvil. La PWA no necesita recursos externos para abrir offline. El SDK de Telegram solo se carga si se abre como Mini App. Los tokens del ERP y del bot nunca se entregan al frontend.

## Conectar Telegram real

1. Crea un bot en BotFather y guarda el token únicamente en `.env`.
2. Una persona debe crear el supergrupo, activar **Temas** y agregar el bot como administrador con permiso para administrar temas y enviar mensajes.
3. Obtén el `chat_id` del supergrupo y configura `TELEGRAM_MODE=live`, `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. El servidor comprueba que el chat sea un supergrupo con temas antes de crear el primero.
4. El bot crea el tema al enviar el primer reporte del proyecto y conserva su `message_thread_id` en SQLite. No crea el supergrupo. Los temas son planos: las tareas se representan como mensajes dentro del tema.
5. Para abrir la Mini App, publica la app tras HTTPS y configura esa URL en BotFather como Main Mini App. La Mini App siempre solicita el PIN de la cuenta de Campo; la identidad de Telegram no sustituye el inicio de sesión.
6. Comparte en el grupo un enlace `https://t.me/NOMBRE_DEL_BOT?startapp`. El botón del menú privado del bot también puede abrir la app. No uses un botón `web_app` de teclado como si funcionara en cualquier grupo.

El bot recibe comandos por **long polling** (`getUpdates`); no necesita una URL pública ni webhook para capturar por chat. Solo debe correr una instancia de polling por token. Si hay un webhook configurado, el servicio lo detecta y espera sin borrarlo. `TELEGRAM_POLLING=false` desactiva la recepción y conserva los envíos. `PUBLIC_URL` agrega a los reportes un enlace web a la PWA; el enlace `startapp` se configura por separado en Telegram.

### Capturar directamente en el bot

1. Abre el chat privado del bot y pulsa Iniciar, o escribe `/reportar` en el supergrupo configurado. Si hay varios bots, usa `/reportar@NOMBRE_DEL_BOT`.
2. Selecciona proyecto y tarea con los botones.
3. Elige Hoy (hora de Ciudad de México) o responde con una fecha `AAAA-MM-DD`.
4. Responde con el porcentaje acumulado y después con las observaciones.
5. Revisa el resumen y pulsa **Confirmar reporte**. El bot registra el avance y el worker lo publica en el tema del proyecto.

Comandos: `/reportar`, `/continuar`, `/estado`, `/cancelar`. Los borradores duran 24 horas y sobreviven a reinicios. En grupos, responde al mensaje del bot cuando solicita texto: el bot ignora conversaciones ajenas. Los botones pertenecen a la captura y al usuario que la inició; botones viejos y confirmaciones repetidas no generan otro reporte.

El bot verifica en cada paso que el usuario pertenezca al supergrupo configurado. Si `TELEGRAM_ALLOWED_USERS` contiene IDs, exige además estar en esa lista. La lista vacía permite a los miembros del grupo usar el chat del bot y la **Mini App**. El catálogo del bot también se filtra por la relación ERP de `telegram:ID`; sin esa relación no muestra tareas. Los reportes identifican al autor con su nombre de Telegram e ID; el ERP recibe `externalUserId=telegram:ID` y `metadataJson.clientApp=campo-telegram`.

La captura conversacional necesita conexión a Telegram. La captura offline sigue disponible mediante la PWA instalada. El reporte capturado en Telegram pertenece a ese usuario, por lo que en la PWA aparece en su sesión `telegram:ID`, no en la cuenta demo compartida `dev`.

Para separar datos demo y reales, usa **un volumen nuevo** mediante otro nombre de proyecto Compose y otro puerto:

```powershell
# Primero edita .env con la integración deseada y APP_PORT=8788
docker compose -p campo-real up --build -d
```

El servidor rechaza cambiar de ERP, modo Telegram o grupo sobre una base ya inicializada. Así no reenvía reportes demo accidentalmente a un grupo real. No hace falta borrar el volumen anterior.

## Conectar el ERP real

Configura `ERP_MODE=live`, `ERP_API_URL=https://tu-servidor/api` y `ERP_API_KEY` con una clave para esta aplicación. El adaptador implementa:

- `GET /external/projects`
- `GET /external/project-tasks?projectId=...`
- `POST /external/project-tasks/:taskId/operation-log`

Envía `source=WEBAPP`, el usuario autenticado en `externalUserId` y el identificador local en `metadataJson.clientReportId`. El porcentaje se convierte a basis points (`65 % = 6500`). Para producción, configura HTTPS en la API: la URL HTTP del documento no se usa automáticamente ni se envía una credencial por ese transporte.

Cada cuenta de campo recibe únicamente las tareas cuyo `responsibleAssignmentId` o `employeeNumber` coincide con su relación ERP; el administrador conserva el catálogo completo. **No implementa permisos por proyecto**, creación de proyectos/tareas, compras ni aprobaciones. Solo publica registros hechos desde Campo; el documento no expone un historial de operaciones ni webhooks para recuperar otros cambios.

## HTTPS y teléfono

En el mismo equipo, `localhost` admite service workers. En un teléfono, una dirección LAN HTTP no sirve como equivalente: usa un dominio HTTPS confiable y un proxy que apunte al contenedor. Hay una composición opcional con Caddy:

```powershell
# En .env: APP_DOMAIN=campo.tudominio.com, PUBLIC_URL=https://campo.tudominio.com,
# COOKIE_SECURE=true, APP_PASSWORD=<PIN administrativo de 4 a 8 dígitos>
docker compose -f compose.yaml -f compose.https.yaml up --build -d
```

Debes controlar el dominio, apuntar su DNS al servidor y permitir los puertos 80/443. Esta configuración **no se activa automáticamente**. Después abre la URL desde Chrome/Safari y usa Instalar/Añadir a inicio. El acceso desde Telegram también requiere HTTPS. La instalación y las garantías de almacenamiento dependen del navegador; el flujo offline principal es la PWA externa.

## Consistencia y recuperación

- Cada reporte tiene un UUID. Repetir el mismo UUID y contenido devuelve el recibo existente; no vuelve a enviar el avance.
- La cola local se elimina solo después de recibir confirmación de almacenamiento en el servidor, guardando antes una copia del recibo.
- Se vuelve a leer el avance antes de escribir. Un cambio respecto al valor descargado o un retroceso genera **Revisar avance**. El operador conserva la nota y corrige el avance explícitamente.
- La comprobación no es atómica con escrituras realizadas por otros clientes del ERP. Para resolver esa carrera en producción, la API necesita versión/ETag o comparación y escritura atómica.
- El ERP documentado no tiene idempotencia ni consulta de registros por UUID. Si un envío tiene resultado incierto, queda **Verificar en ERP**, sin reintento automático.
- Una respuesta incierta de Telegram queda **Verificar envío**. La Bot API no ofrece una clave de idempotencia para `sendMessage`; no prometemos entrega exactamente una vez.
- Los errores definitivos de Telegram admiten **Reintentar envío**. Los estados inciertos requieren revisar el sistema externo y reconciliar el registro en SQLite; el prototipo no incluye una consola de conciliación.
- Solo se permite un reporte local pendiente por tarea para evitar cadenas de porcentajes basadas en datos antiguos.
- El porcentaje de una tarjeta de proyecto es el **promedio simple** de las tareas descargadas, etiquetado como tal; no representa necesariamente el cálculo ponderado del ERP.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Cubren idempotencia local, conflictos, agrupación en temas, fallos ambiguos, aislamiento de identificadores y recuperación tras reinicio. No llaman al ERP o Telegram reales.

Para ejecutar sin Docker durante diagnóstico:

```powershell
$env:PORT='8787'
python server.py
```

El servidor HTTP de biblioteca estándar es una decisión del prototipo. Antes de uso productivo: servidor de aplicación endurecido, rotación de PIN administrativo, respaldo, retención de datos y contrato ERP para idempotencia/versionado.

### Vinculación del usuario con el responsable del ERP

La administración crea cada cuenta a partir del empleado y la asignación devueltos por la API ERP; esos valores se guardan en `user_profiles`. Para identidades Telegram, puedes relacionar `telegram:ID` mediante `USER_RESPONSIBLE_MAP`. Los reportes usan el responsable de la tarea del ERP como responsable operativo y conservan el usuario autenticado en el mensaje y en `externalUserId`.

Las cuentas de campo solo reciben y pueden registrar tareas cuyo `assignmentId` o `employeeNumber` coincide con su relación ERP. El administrador conserva acceso completo.

Los usuarios de campo se autentican únicamente con PIN. Los PIN nuevos se almacenan con `scrypt` y no pueden repetirse entre cuentas activas; los registros antiguos se migran al primer acceso correcto. Desactivar una cuenta invalida sus sesiones existentes. Las altas, cambios, activaciones, desactivaciones y bajas del CRUD quedan en `audit_log` y pueden consultarse mediante `/api/admin/audit`.


### Mini App dentro de Telegram

Con `PUBLIC_URL=https://...`, el menú **Reportar** del bot y `/reportar` en privado abren la misma interfaz de la PWA como Mini App. En el supergrupo, `/reportar` ofrece un enlace al chat privado del bot (Telegram limita el botón web_app a chats privados).

La Mini App no inicia sesión automáticamente con `initData`: siempre muestra el formulario de PIN. La pertenencia al grupo de Telegram protege el uso del bot conversacional, pero no concede acceso a la PWA/Mini App. Para el túnel público se configura `PASSWORD_LOGIN_ENABLED=true` y `COOKIE_SECURE=true`.

Túnel temporal Docker: `docker compose -p campo-telegram -f compose.yaml -f compose.tunnel.yaml up -d`. Obtén la URL https de `docker logs campo-telegram-tunnel-1`, actualiza PUBLIC_URL en .env y recrea campo con el mismo comando. El bot actualiza su menú al iniciar. La URL puede cambiar al reiniciar el túnel; actualiza PUBLIC_URL entonces. Para uso permanente, usa un dominio y túnel estable o el despliegue HTTPS con Caddy.

El backend y el túnel deben permanecer activos. La apertura inicial y la autenticación de la Mini App requieren internet; la PWA instalada conserva el modo offline. No se garantiza reabrir Telegram Mini Apps sin conexión. Los reportes guardados por la interfaz se sincronizan mediante el backend y el bot los publica en los temas por proyecto. ERP_MODE=demo sigue usando proyectos y tareas de ejemplo.

Validación de esta integración: 19 pruebas automáticas aprobadas, HTTPS responde 200, catálogo anónimo rechaza con 401, contraseña pública rechaza con 403 y getChatMenuButton confirma el botón web_app. La apertura con la cuenta real del operador se verifica desde Telegram.


### Conexión ERP activada (2026-09-26)

Instancia campo-telegram configurada en ERP_MODE=live con API base http://78.13.100.60/api; /tracker/ es la interfaz web. La credencial queda en .env. Este servidor requiere ERP_ALLOW_HTTP=true porque no respondió por HTTPS: el tráfico entre backend y ERP no va cifrado. Se verificaron por lectura 2 proyectos y 10 tareas. No se creó un reporte ficticio para probar escritura. Los nuevos reportes guardados usarán operation-log del ERP antes de publicarse en Telegram.

El volumen activo es campo-telegram_erp-live-data; campo-telegram_campo-data conserva el historial demo sin migrar sus reportes. Cierra y vuelve a abrir la Mini App para iniciar sesión en la nueva base y descargar el catálogo del ERP.


## Empleados y cuadrilla

En **Empleados**, registra nombre y uno o varios roles (operador, técnico, auxiliar). Puedes buscar, editar y eliminar personas con sesión y conexión. El catálogo es compartido entre los usuarios autorizados de esta instancia y se almacena en su volumen SQLite; no crea empleados en el ERP.

En **Reportar → Personal en campo**, busca y selecciona hasta 30 personas. Una persona solo puede participar una vez por reporte, en uno de sus roles. El catálogo descargado y la selección funcionan sin conexión. Los cambios al catálogo requieren conexión y se descargan con Sincronizar o Actualizar catálogo.

El reporte conserva la versión del nombre y roles elegida durante la captura. Eliminar una persona la retira del catálogo, pero conserva el historial y permite sincronizar los reportes pendientes. Las ediciones simultáneas se rechazan para evitar sobrescribir cambios de otro usuario.

La cuadrilla aparece en Mis reportes, en el mensaje de Telegram y en `metadataJson.crew` / `metadataJson.personnelCount` del registro ERP. La API externa documentada no incluye un catálogo de empleados, por eso se administra en Campo. La captura conversacional por mensajes del bot conserva su flujo anterior; utiliza la Mini App para seleccionar personal.


## Reporte de campo con fotografías

El formulario registra nombre/cargo del autor, cantidad de la jornada y unidad (ha, m, m², m³, km, unidades), porcentaje acumulado, cuadrilla y hasta cinco máquinas con horas y litros. El nombre/cargo se recuerda por usuario y dispositivo; es declarado por el operador. La cuenta autenticada también queda en el mensaje. La hora, zona horaria y estado de conexión se toman del dispositivo al guardar; se conservan al corregir un pendiente.

Se admiten hasta seis fotografías JPG/PNG/WebP de hasta 20 MB de entrada. El navegador las convierte a JPEG, con lado máximo de 1600 píxeles y hasta 1.5 MB por foto. Las fotos quedan en IndexedDB junto con el pendiente, y se incluyen al exportarlo. No se envían al ERP: solo se registra su conteo junto con los datos de campo en metadataJson.

Al sincronizar, las fotografías se cargan primero al servidor local, dentro del volumen SQLite persistente. Cada carga es idempotente y pertenece al usuario/reporte. Luego se registra el reporte en el ERP y, tras su confirmación, el worker publica el mensaje y cada foto como respuesta al mensaje, en el mismo tema de Telegram. El registro pasa a Publicado únicamente después de confirmar todas las fotos. Se conserva una copia local tras sincronizar y otra en el servidor; cerrar sesión borra la copia del navegador, no la del servidor.

Los reintentos de fallos definitivos omiten texto/fotos previamente confirmados. Un resultado ambiguo o un reinicio durante el envío requiere verificar Telegram y no reenvía automáticamente. Las imágenes del servidor requieren sesión y solo las consulta su autor. No hay servicio de almacenamiento externo ni limpieza automática del archivo local; respaldar el volumen incluye las fotografías.

El envío usa multipart/form-data y sendPhoto según la [documentación oficial de Telegram](https://core.telegram.org/bots/api#sendphoto). Las nuevas capturas enriquecidas se hacen desde la web/Mini App; los reportes antiguos y la conversación del bot siguen siendo compatibles.


## Paro operativo

El formulario incluye Día sin actividad (Paro), con motivos Lluvia, Sin Material, Sin Cuadrilla, Sin Máquina, Descanso y Otro. Otro requiere descripción. Activarlo fija la cantidad de jornada en cero y conserva el porcentaje acumulado; desactivarlo restaura los valores capturados antes de activar el interruptor. El servidor valida ambas condiciones. El motivo se conserva sin conexión y aparece en Mis reportes, Telegram y metadataJson.fieldReport.stoppage del ERP. Se pueden adjuntar fotografías de la causa del paro.


## Reportes confirmados inmutables

Confirmar reporte guarda una captura definitiva en el dispositivo. No se reabre para edición, tampoco por conflicto o validación. El servidor conserva el contenido de la primera solicitud por ID y rechaza cualquier cambio posterior; los reintentos usan el mismo contenido y las mismas fotos. Los reportes aceptados anteriores también conservan su validación de idempotencia. Esta protección corresponde al flujo de la aplicación y al servidor; no impide que un administrador altere directamente los archivos o la base de datos.

En Proyectos, Registro confirmado muestra estados y permite registrar aclaraciones separadas, con referencia, cuenta y fecha. Las aclaraciones requieren conexión y que el original haya llegado al servidor, incluso si fue rechazado. Son notas inmutables dentro de Campo; no modifican el ERP ni se publican automáticamente en Telegram. Los reportes nuevos no sustituyen a los anteriores.

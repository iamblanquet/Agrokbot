# Despliegue en Render

## Requisitos

1. Subir este proyecto a un repositorio privado de GitHub/GitLab.
2. En Render, elegir **New > Blueprint** y conectar el repositorio.
3. Render detectará `render.yaml` y creará el Web Service `campo-agrookool`.
4. El servicio usa el Dockerfile existente, `/api/health` como health check y un Persistent Disk montado en `/data`.

El disco persistente es necesario porque SQLite, la cola de reportes y las fotografías viven en `/data`. El plan `starter` se usa porque los Persistent Disks requieren un servicio de pago en Render.

## Variables que deben configurarse en Render

Configura los valores `sync: false` en el Dashboard, nunca en el repositorio:

- `APP_PASSWORD`: PIN administrativo fuerte.
- `ERP_API_URL`: URL HTTPS del ERP, con `/api`.
- `ERP_API_KEY`: clave exclusiva para esta instalación.
- `TELEGRAM_BOT_TOKEN`: token rotado del bot.
- `TELEGRAM_CHAT_ID`: supergrupo de reportes.
- `TELEGRAM_ALLOWED_USERS`: opcional; IDs separados por coma.
- `PUBLIC_URL`: URL HTTPS final de Render, por ejemplo `https://campo-agrookool.onrender.com`.

## Condición de seguridad del ERP

La configuración de Blueprint deja `ERP_ALLOW_HTTP=false`. Antes de enviar reportes reales, `ERP_API_URL` debe usar HTTPS. No se recomienda desplegar la clave del ERP por HTTP.

## Después del primer despliegue

1. Esperar a que `/api/health` responda `200`.
2. Configurar `PUBLIC_URL` con la URL definitiva del servicio y desplegar de nuevo.
3. Configurar el menú del bot/Mini App para esa URL.
4. Probar login, descarga de catálogo, creación de reporte y publicación en Telegram.
5. Revisar los logs y confirmar que no existan estados `erp_review` o `telegram_review`.

## Limitación del bot

El bot usa long polling dentro del mismo Web Service. Render debe mantener una sola instancia del servicio; no escalar horizontalmente sin separar el bot en un Background Worker, porque dos instancias podrían consumir el mismo token simultáneamente.

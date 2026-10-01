# Validación del prototipo — 26 de septiembre de 2026

- Docker: imagen construida y contenedor `campo-app-campo-1` ejecutándose, healthcheck correcto, puerto local 8787.
- Servidor: 10 pruebas automáticas aprobadas. Autenticación por cookie, cierre de sesión, rechazo de origen externo, firma/antigüedad/lista autorizada de Telegram, deduplicación, conflictos de avance, agrupación por proyecto, estados inciertos y recuperación después de reinicio.
- Navegador: acceso con cuenta demo, catálogo de 2 proyectos / 6 tareas y captura con simulación offline.
- Persistencia offline: servidor detenido, recarga completa de la página y reporte pendiente conservado en IndexedDB.
- Recuperación: al conectar el contenedor, renovar sesión preservó el pendiente; se sincronizó a 65 % y apareció en el tema simulado de Santa Teresita.
- Persistencia Docker: la reconstrucción/recreación del contenedor conservó la sesión, el reporte y su tema en el volumen.
- Móvil: revisión a 390 × 844, sin desbordamiento horizontal de la página; formulario de reporte visible y navegable. Evidencia en `mobile.png`.
- Evidencia de publicación simulada: `prototipo.png`.

No se enviaron datos al ERP real ni mensajes a Telegram. Los adaptadores reales requieren sus credenciales y verificación contra los servicios. La instalación en un teléfono físico, el acceso desde Telegram y el proxy HTTPS no se probaron; necesitan dominio/configuración del usuario.

## Ampliación: captura por bot real

- Se implementó `telegram_bot.py` con recepción por long polling y comandos `/reportar`, `/continuar`, `/estado` y `/cancelar`.
- 17 pruebas automáticas aprobadas: se añadieron conversación completa, doble confirmación, miembros no autorizados, botones de otro usuario, respuestas en grupos, porcentajes inválidos, conflicto y recuperación de borradores.
- Se reconstruyó `campo-telegram-campo-1` y se verificó saludable en el puerto 8788.
- Telegram confirmó los cuatro comandos publicados para `@testblanquetbot`; sin webhook activo. El log confirmó que el receptor está activo.
- Las pruebas automáticas de conversación simulan Telegram; no se fabricó un reporte real en nombre del usuario. Falta la prueba de aceptación del operador enviando `/reportar` al bot.
- Telegram está en modo real y el ERP continúa en demo. La Mini App con HTTPS sigue siendo una vía separada de la conversación por comandos.

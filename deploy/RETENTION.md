# Retención de versiones en producción

Política: usar únicamente `/home/mblanquet/Agrokbot` como checkout y despliegue
de Campo. No crear nuevas worktrees por versión. Actualizar este checkout al
commit deseado antes de ejecutar el comando de activación.

Scripts instalados en el servidor:

- `/usr/local/sbin/campo-cleanup-releases.py`: simulación por defecto;
  `sudo python3 /usr/local/sbin/campo-cleanup-releases.py --apply` aplica la limpieza.
- `/usr/local/sbin/campo-activate-release`: ejecutar con sudo desde la nueva
  versión preparada con su `.env`. Debe actualizarse desde `deploy/activate-release.sh`
  antes de usar las nuevas protecciones. También puede ejecutarse directamente
  `sudo sh deploy/activate-release.sh` desde el checkout.

La activación requiere Node.js, Docker Compose y flock. Primero ejecuta las pruebas
JavaScript y las pruebas Python en un contenedor aislado sin red externa ni volumen
de producción. Después conserva una imagen de reversión y crea un respaldo SQLite
consistente, configuración y clave VAPID (si existe) en
`/home/mblanquet/campo-backups/<fecha-UTC>`, con acceso restringido.

Si falla la salud del nuevo contenedor, intenta volver a la imagen anterior.
No restaura automáticamente SQLite: hacerlo podría perder reportes recibidos
durante el intento. Las migraciones de esta actualización son compatibles con
las tablas anteriores; los reportes `evidence_review` deben conservarse para
conciliación, incluso si se revierte la imagen.

El activador ya no ejecuta limpieza destructiva. Conserva respaldos e imágenes
de reversión; la retención de estos debe revisarse de forma separada. El respaldo
local no sustituye una copia fuera del servidor ni una prueba de restauración.

La limpieza protege todas las rutas y las imágenes referenciadas por contenedores,
incluidos los detenidos. Omite worktrees con cambios o datos locales inesperados.
Solo elimina worktrees registradas `Agrokbot-release-<hash>` y etiquetas
`agrokbot-campo:rollback-<hash>` sin uso. No ejecuta prune global ni elimina volúmenes.
Las copias .env de releases retiradas se eliminan; la configuración activa se conserva.
Para volver a una versión retirada hay que reconstruir su commit de Git.

# Retención de versiones en producción

Política: usar únicamente `/home/mblanquet/Agrokbot` como checkout y despliegue
de Campo. No crear nuevas worktrees por versión. Actualizar este checkout al
commit deseado antes de ejecutar el comando de activación.

Scripts instalados en el servidor:

- `/usr/local/sbin/campo-cleanup-releases.py`: simulación por defecto;
  `sudo python3 /usr/local/sbin/campo-cleanup-releases.py --apply` aplica la limpieza.
- `/usr/local/sbin/campo-activate-release`: ejecutar con sudo desde la nueva
  release preparada con su `.env`. Construye, activa, espera salud y limpia
  automáticamente las releases anteriores después del éxito.

La limpieza protege todas las rutas y las imágenes referenciadas por contenedores,
incluidos los detenidos. Omite worktrees con cambios o datos locales inesperados.
Solo elimina worktrees registradas `Agrokbot-release-<hash>` y etiquetas
`agrokbot-campo:rollback-<hash>` sin uso. No ejecuta prune global ni elimina volúmenes.
Las copias .env de releases retiradas se eliminan; la configuración activa se conserva.
Para volver a una versión retirada hay que reconstruir su commit de Git.

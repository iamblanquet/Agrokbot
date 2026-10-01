# Frontend

La PWA existente sigue sirviéndose desde `public/` para mantener compatibilidad con el service worker. Los módulos nuevos se sirven desde esta carpeta mediante rutas controladas por el servidor:

- `api.js`: cliente HTTP JSON y normalización de errores.
- `admin.js`: CRUD administrativo de usuarios, selección de empleados ERP, activación/desactivación y auditoría visual.
- `storage.js`: IndexedDB, cola de reportes, snapshots y limpieza de catálogos antiguos.
- `sync.js`: descarga de catálogo, envío de fotos/reportes pendientes y tratamiento de conflictos.
- `auth.js`: login por PIN, sesión, Mini App Telegram y arranque de la PWA.

`public/app.js` conserva el estado de la interfaz, la sincronización y coordina las vistas; no debe duplicar la lógica de estos módulos.

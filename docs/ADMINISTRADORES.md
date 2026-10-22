# Administradores adicionales

La cuenta principal configurada con APP_USER se conserva. Las cuentas adicionales
inician sesión con PIN como cualquier usuario, con privilegios persistidos en la
tabla administrators. El rol se comprueba en servidor y exige cuenta activa;
no se confía en campos enviados por el navegador.

Solo la cuenta principal puede utilizar POST /api/admin/administrators con
username (3-32 caracteres alfanuméricos minúsculos) y pin (6-8 dígitos).
La operación crea una cuenta nueva, sin asignación ERP, y rechaza nombres o PIN
ya utilizados. No sobrescribe cuentas existentes ni almacena el PIN en auditoría.
Los PIN se guardan con scrypt. No guardar credenciales en Git.

La cuenta adicional accede al catálogo completo, Administración, Monitoreo e
Incidencias. Puede desactivarse desde el listado de usuarios; la desactivación
invalida las sesiones. No se permite convertirla en empleado mediante la edición
de asignación ERP. La creación de administradores tiene por ahora API, no un
formulario nuevo. El acceso a reportes personales mantiene su propietario.

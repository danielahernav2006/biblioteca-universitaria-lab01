# Mejoras integrante 5

## Instalación
1. Guarda copia de tu carpeta actual y de la base de datos.
2. Conserva tu MySQL `biblioteca_db`. NO ejecutes de nuevo `Lab1.sql` (borra la base).
3. En Workbench ejecuta `SHOW CREATE TABLE ejemplar;` y confirma que el CHECK de estado se llama `ejemplar_chk_1`.
4. Ejecuta UNA VEZ `migracion_integrante5.sql`. Si el CHECK tiene otro nombre, reemplaza `ejemplar_chk_1` en la primera sentencia ALTER.
5. Abre esta carpeta en VS Code, crea/activa el entorno e instala requirements.txt si es necesario.
6. Define DB_PASSWORD en la terminal, luego `python app.py`.

## Comprobaciones
- El servidor `prestamos.py` valida estado ACTIVO, rol, duplicados, límite, disponibilidad y autorizaciones aun cuando se realicen peticiones directas. Se usan transacciones y FOR UPDATE.
- La fecha usada para registro de préstamo/devolución es la de America/Bogota y la conexión SQL usa zona horaria -05:00.
- Devolución BUENO => DISPONIBLE. DAÑADO o PÁGINAS FALTANTES => EN_REVISION.
- Para habilitar ejemplar inspeccionado, bibliotecario: Catálogo > detalle libro > Editar ejemplar > DISPONIBLE.
- Las aprobaciones muestran código de barras y vencimiento en el mensaje superior.

## Consideraciones
- Las fechas de registros históricos no se modifican.
- Los ejemplares dañados en devoluciones anteriores no cambian automáticamente: revisar uno por uno.
- Antes de colaborar, acuerden con el integrante del catálogo y reportes los cambios menores a sus archivos.
- Código pensado para MySQL 8.x. No se comprobó contra el servidor local de la usuaria.

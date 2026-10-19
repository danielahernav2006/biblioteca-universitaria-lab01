-- Ejecutar después de Lab1.sql sobre la base existente, sin borrar registros.
USE biblioteca_db;
-- MySQL 8 asigna ejemplar_chk_1 al CHECK anónimo de ejemplar.
-- Verifica primero con SHOW CREATE TABLE ejemplar si tu servidor usa otro nombre.
ALTER TABLE ejemplar DROP CHECK ejemplar_chk_1;
ALTER TABLE ejemplar ADD CONSTRAINT chk_ejemplar_estado
    CHECK (estado IN ('DISPONIBLE','PRESTADO','PERDIDO','EN_REVISION'));

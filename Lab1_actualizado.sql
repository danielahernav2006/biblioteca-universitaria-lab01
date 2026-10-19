CREATE DATABASE biblioteca_db_v2;
USE biblioteca_db_v2;


Tables
CREATE TABLE editorial (
    id_editorial INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE
); -- La relación es 1:N: una editorial puede tener muchos libros, mientras que cada libro puede tener, como máximo, una editorial en este modelo.

CREATE TABLE autor (
    id_autor INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE -- para evitar registrar dos veces exactamente el mismo nombre.
);

CREATE TABLE categoria (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);  -- La categoría no se guarda directamente en la tabla libro porque un libro puede pertenecer a varias categorías.

CREATE TABLE libro (
    id_libro INT AUTO_INCREMENT PRIMARY KEY,
    isbn VARCHAR(17) NOT NULL UNIQUE,
    titulo VARCHAR(200) NOT NULL,
    id_editorial INT,
    año INT CHECK (año BETWEEN 1400 AND 2100),
    descripcion VARCHAR(500),
    FOREIGN KEY (id_editorial) REFERENCES editorial(id_editorial) ON DELETE SET NULL -- Si se elimina una editorial, MySQL deja el campo id_editorial del libro en NULL, pero conserva el libro.
);


-- Un libro puede tener muchos autores y un autor puede escribir muchos libros.
-- la relación conceptual es N:M
CREATE TABLE libro_autor (
    id_libro INT NOT NULL,
    id_autor INT NOT NULL,
    PRIMARY KEY (id_libro, id_autor),
    FOREIGN KEY (id_libro) REFERENCES libro(id_libro) ON DELETE CASCADE, -- Si eliminamos un libro, automáticamente se eliminan las asociaciones de ese libro en libro_autor.
    FOREIGN KEY (id_autor) REFERENCES autor(id_autor)
);


-- Un libro puede tener muchas categorías y una categoría puede contener muchos libros.
CREATE TABLE libro_categoria (
    id_libro INT NOT NULL,
    id_categoria INT NOT NULL,
    PRIMARY KEY (id_libro, id_categoria),
    FOREIGN KEY (id_libro) REFERENCES libro(id_libro) ON DELETE CASCADE,
    FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria)
);

CREATE TABLE ubicacion (
    id_ubicacion INT AUTO_INCREMENT PRIMARY KEY,
    sala VARCHAR(50) NOT NULL,
    estante VARCHAR(20) NOT NULL,
    UNIQUE (sala, estante)
);


-- Libro (1) → (N) Ejemplares
-- Cada ejemplar pertenece a un solo libro, pero un libro puede tener varios ejemplares.
CREATE TABLE ejemplar (
    id_ejemplar INT AUTO_INCREMENT PRIMARY KEY,
    codigo_barras VARCHAR(30) NOT NULL UNIQUE,
    id_libro INT NOT NULL,
    id_ubicacion INT,
    estado VARCHAR(20) NOT NULL DEFAULT 'DISPONIBLE' CHECK (estado IN ('DISPONIBLE', 'PRESTADO', 'PERDIDO', 'EN_REVISION')),
    UNIQUE (id_ejemplar, id_libro), -- para poder referenciarla desde la tabla prestamo. Porque necesitamos asegurarnos de que el ejemplar asignado realmente pertenezca al libro que se está prestando.
    FOREIGN KEY (id_libro) REFERENCES libro(id_libro),
    FOREIGN KEY (id_ubicacion) REFERENCES ubicacion(id_ubicacion) ON DELETE SET NULL
);

CREATE TABLE carrera (
    id_carrera INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE
);  -- Separar las carreras en otra tabla evita repetir sus nombres en todos los registros de estudiantes.


-- almacena las personas que interactúan con el sistema.
CREATE TABLE usuario (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    identificacion VARCHAR(20) NOT NULL UNIQUE,
    nombres VARCHAR(150) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE CHECK (correo LIKE '%@%'),
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('ESTUDIANTE', 'DOCENTE', 'BIBLIOTECARIO')), Porque los permisos y plazos dependen del tipo de usuario.
    id_carrera INT,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'BLOQUEADO')),
    contraseña VARCHAR(255) NOT NULL,
    FOREIGN KEY (id_carrera) REFERENCES carrera(id_carrera) ON DELETE SET NULL
);

CREATE TABLE parametro (
    clave VARCHAR(50) PRIMARY KEY,
    valor DECIMAL(10,2) NOT NULL,
    descripcion VARCHAR(200) NOT NULL
); -- Porque permite almacenar reglas de negocio modificables sin tener que cambiar necesariamente los valores escritos en el código Python.
-- La tabla solo almacena la configuración. Para aplicar el límite de tres préstamos o calcular multas, la aplicación debe consultar y utilizar estos parámetros.



CREATE TABLE prestamo (
    id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    id_libro INT NOT NULL,
    id_ejemplar INT, -- El ejemplar se asigna cuando el bibliotecario aprueba el préstamo. Así distinguimos entre solicitar una obra y recibir efectivamente una copia física.
    fecha_solicitud DATE NOT NULL,
    fecha_prestamo DATE,
    fecha_vencimiento DATE,
    id_bibliotecario INT,
    estado VARCHAR(20) NOT NULL DEFAULT 'SOLICITADO' CHECK (estado IN ('SOLICITADO', 'ACTIVO', 'RECHAZADO', 'DEVUELTO')),
    motivo_rechazo VARCHAR(200),
    CHECK (fecha_vencimiento >= fecha_prestamo),
    CHECK (estado NOT IN ('ACTIVO', 'DEVUELTO') OR (id_ejemplar IS NOT NULL AND fecha_prestamo IS NOT NULL AND fecha_vencimiento IS NOT NULL AND id_bibliotecario IS NOT NULL)),  -- Si el préstamo está ACTIVO o DEVUELTO, obligatoriamente debe tener ejemplar asignado, fecha de inicio, fecha de vencimiento y bibliotecario responsable.
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario),
    FOREIGN KEY (id_libro) REFERENCES libro(id_libro),
    FOREIGN KEY (id_ejemplar, id_libro) REFERENCES ejemplar(id_ejemplar, id_libro), -- De esta manera, el préstamo no puede asociar un ejemplar con un título incorrecto.
    FOREIGN KEY (id_bibliotecario) REFERENCES usuario(id_usuario)
);


-- registra la entrega física de un ejemplar que estaba prestado.
CREATE TABLE devolucion (
    id_devolucion INT AUTO_INCREMENT PRIMARY KEY,
    id_prestamo INT NOT NULL UNIQUE, -- una sola devolución por préstamo. Eso genera una relación entre prestamo y devolucion de uno a cero o uno: un préstamo puede no tener devolución todavía, pero puede tener como máximo una.
    fecha_devolucion DATE NOT NULL,
    id_bibliotecario INT NOT NULL,
    condicion VARCHAR(20) NOT NULL DEFAULT 'BUENO' CHECK (condicion IN ('BUENO', 'DAÑADO', 'PÁGINAS FALTANTES')), -- En nuestra versión mejorada, cuando la condición es DAÑADO o PÁGINAS FALTANTES, Python actualiza el estado del ejemplar a EN_REVISION.
    observaciones VARCHAR(300),
    FOREIGN KEY (id_prestamo) REFERENCES prestamo(id_prestamo),
    FOREIGN KEY (id_bibliotecario) REFERENCES usuario(id_usuario)
);

CREATE TABLE multa (
    id_multa INT AUTO_INCREMENT PRIMARY KEY,
    id_devolucion INT NOT NULL UNIQUE, -- Porque cada devolución puede tener, como máximo, una multa asociada en este diseño.
    dias_retraso INT NOT NULL CHECK (dias_retraso > 0), -- Una devolución sin retraso no necesita un registro de multa.
    valor_dia DECIMAL(10,2) NOT NULL CHECK (valor_dia >= 0), -- Porque la tarifa puede cambiar en el futuro. Guardar la tarifa aplicada permite conservar el valor histórico utilizado para calcular una multa concreta.
    monto DECIMAL(12,2) NOT NULL CHECK (monto >= 0),
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE', 'PAGADA')),
    fecha_pago DATE,
    CHECK (monto = dias_retraso * valor_dia),
    FOREIGN KEY (id_devolucion) REFERENCES devolucion(id_devolucion)
);


-- El orden de las inserciones importa
INSERT INTO parametro (clave, valor, descripcion) VALUES
('TARIFA_MULTA_DIA', 1000, 'Valor de la multa por cada día de retraso (COP)'),
('DIAS_PRESTAMO_ESTUDIANTE', 8, 'Días de préstamo para estudiantes'),
('DIAS_PRESTAMO_DOCENTE', 15, 'Días de préstamo para docentes'),
('MAX_PRESTAMOS_ACTIVOS', 3, 'Máximo de préstamos activos por usuario');

INSERT INTO editorial (nombre) VALUES
('Pearson'), ('McGraw-Hill'), ('O''Reilly Media'), ('Alfaguara'),
('Penguin Random House'), ('Cengage Learning'), ('MIT Press');

INSERT INTO autor (nombre) VALUES
('Abraham Silberschatz'), ('Henry F. Korth'), ('S. Sudarshan'),
('Ramez Elmasri'), ('Shamkant B. Navathe'),
('Gabriel García Márquez'),
('Aurélien Géron'),
('Thomas H. Cormen'), ('Charles E. Leiserson'), ('Ronald L. Rivest'), ('Clifford Stein'),
('Robert C. Martin'),
('James Stewart'),
('Neil A. Campbell'), ('Jane B. Reece'),
('Yuval Noah Harari'),
('Wes McKinney');

INSERT INTO categoria (nombre) VALUES
('Bases de Datos'), ('Ingeniería de Software'), ('Literatura'), ('Inteligencia Artificial'),
('Algoritmos'), ('Matemáticas'), ('Biología'), ('Historia'), ('Ciencia de Datos');

INSERT INTO libro (isbn, titulo, id_editorial, año, descripcion) VALUES
('978-0078022159', 'Database System Concepts', 2, 2019, 'Texto clásico de fundamentos de bases de datos.'),
('978-0133970777', 'Fundamentals of Database Systems', 1, 2015, 'Modelado ER, modelo relacional, SQL y normalización.'),
('978-8439728367', 'Cien años de soledad', 4, 2017, 'Novela emblemática del realismo mágico.'),
('978-1098125974', 'Hands-On Machine Learning with Scikit-Learn, Keras and TensorFlow', 3, 2022, 'Aprendizaje automático práctico en Python.'),
('978-0262046305', 'Introduction to Algorithms', 7, 2022, 'Referencia de algoritmos y estructuras de datos.'),
('978-0132350884', 'Clean Code', 1, 2008, 'Buenas prácticas para escribir código limpio.'),
('978-1285741550', 'Calculus: Early Transcendentals', 6, 2015, 'Cálculo diferencial e integral.'),
('978-0134093413', 'Campbell Biology', 1, 2016, 'Texto de biología general.'),
('978-0062316097', 'Sapiens: A Brief History of Humankind', 5, 2015, 'Historia de la humanidad.'),
('978-1098104030', 'Python for Data Analysis', 3, 2022, 'Análisis de datos con pandas y NumPy.'),
('978-8497592208', 'El amor en los tiempos del cólera', 4, 2003, 'Novela de Gabriel García Márquez.'),
('978-0134494166', 'Clean Architecture', 1, 2017, 'Arquitectura de software.');

INSERT INTO libro_autor (id_libro, id_autor) VALUES
(1,1), (1,2), (1,3), (2,4), (2,5), (3,6), (4,7), (5,8), (5,9), (5,10), (5,11),
(6,12), (7,13), (8,14), (8,15), (9,16), (10,17), (11,6), (12,12);

INSERT INTO libro_categoria (id_libro, id_categoria) VALUES
(1,1), (2,1), (2,2), (3,3), (4,4), (4,9), (5,5), (6,2), (7,6), (8,7), (9,8), (10,9), (11,3), (12,2);

INSERT INTO ubicacion (sala, estante) VALUES
('Sala General', 'A-01'), ('Sala General', 'A-02'), ('Sala Ingeniería', 'B-01'),
('Sala Ingeniería', 'B-02'), ('Sala Ciencias', 'C-01'), ('Hemeroteca', 'H-01');

INSERT INTO ejemplar (codigo_barras, id_libro, id_ubicacion, estado) VALUES
('1001', 1, 3, 'PRESTADO'),
('1002', 1, 3, 'DISPONIBLE'),
('1003', 1, 3, 'DISPONIBLE'),
('1004', 2, 3, 'PRESTADO'),
('1005', 2, 3, 'DISPONIBLE'),
('1006', 3, 1, 'DISPONIBLE'),
('1007', 3, 1, 'PERDIDO'),
('1008', 4, 4, 'PRESTADO'),
('1009', 4, 4, 'DISPONIBLE'),
('1010', 5, 4, 'DISPONIBLE'),
('1011', 5, 4, 'DISPONIBLE'),
('1012', 6, 4, 'DISPONIBLE'),
('1013', 7, 5, 'DISPONIBLE'),
('1014', 7, 5, 'DISPONIBLE'),
('1015', 8, 5, 'DISPONIBLE'),
('1016', 9, 2, 'DISPONIBLE'),
('1017', 10, 4, 'PRESTADO'),
('1018', 10, 4, 'DISPONIBLE'),
('1019', 11, 1, 'DISPONIBLE'),
('1020', 12, 4, 'DISPONIBLE');

INSERT INTO carrera (nombre) VALUES
('Ingeniería de Sistemas'), ('Ciencia de Datos'), ('Biología'),
('Ingeniería Industrial'), ('Derecho'), ('Medicina');

INSERT INTO usuario (codigo, identificacion, nombres, correo, rol, id_carrera, estado, contraseña) VALUES
('admin', '1000000001', 'Administrador Biblioteca', 'admin@biblioteca.edu.co', 'BIBLIOTECARIO', NULL, 'ACTIVO', 'admin123'),
('biblio01', '1000000002', 'Marta Lucía Herrera', 'mherrera@biblioteca.edu.co', 'BIBLIOTECARIO', NULL, 'ACTIVO', 'biblio123'),
('200150001', '1043000001', 'Ana María Pérez', 'aperez@uni.edu.co', 'ESTUDIANTE', 1, 'ACTIVO', '123456'),
('200150002', '1043000002', 'Carlos Andrés Gómez', 'cgomez@uni.edu.co', 'ESTUDIANTE', 2, 'ACTIVO', '123456'),
('200150003', '1043000003', 'Laura Valentina Ruiz', 'lruiz@uni.edu.co', 'ESTUDIANTE', 3, 'ACTIVO', '123456'),
('200150004', '1043000004', 'Jorge Iván Castro', 'jcastro@uni.edu.co', 'ESTUDIANTE', 4, 'BLOQUEADO', '123456'),
('DOC0001', '72000001', 'Dr. Ricardo Molina', 'rmolina@uni.edu.co', 'DOCENTE', NULL, 'ACTIVO', '123456'),
('DOC0002', '72000002', 'Dra. Patricia Rojas', 'projas@uni.edu.co', 'DOCENTE', NULL, 'ACTIVO', '123456');

INSERT INTO prestamo (id_usuario, id_libro, id_ejemplar, fecha_solicitud, fecha_prestamo, fecha_vencimiento, id_bibliotecario, estado) VALUES
(3, 1, 2, '2026-08-17', '2026-08-17', '2026-08-25', 1, 'DEVUELTO'),
(4, 4, 9, '2026-09-01', '2026-09-01', '2026-09-09', 1, 'DEVUELTO'),
(7, 5, 10, '2026-09-07', '2026-09-07', '2026-09-22', 2, 'DEVUELTO'),
(3, 3, 6, '2026-09-17', '2026-09-17', '2026-09-25', 1, 'DEVUELTO'),
(5, 1, 3, '2026-09-19', '2026-09-19', '2026-09-27', 2, 'DEVUELTO'),
(3, 1, 1, '2026-10-12', '2026-10-12', '2026-10-20', 1, 'ACTIVO'),
(4, 2, 4, '2026-10-05', '2026-10-05', '2026-10-13', 1, 'ACTIVO'),
(7, 4, 8, '2026-10-14', '2026-10-14', '2026-10-29', 2, 'ACTIVO'),
(5, 10, 17, '2026-10-01', '2026-10-01', '2026-10-09', 2, 'ACTIVO');

INSERT INTO prestamo (id_usuario, id_libro, fecha_solicitud, estado) VALUES
(8, 5, '2026-10-16', 'SOLICITADO'),
(4, 6, '2026-10-17', 'SOLICITADO');

INSERT INTO prestamo (id_usuario, id_libro, fecha_solicitud, id_bibliotecario, estado, motivo_rechazo) VALUES
(6, 3, '2026-10-07', 1, 'RECHAZADO', 'Usuario bloqueado');

INSERT INTO devolucion (id_prestamo, fecha_devolucion, id_bibliotecario, condicion, observaciones) VALUES
(1, '2026-08-24', 1, 'BUENO', NULL),
(2, '2026-09-13', 1, 'BUENO', NULL),
(3, '2026-09-21', 2, 'BUENO', NULL),
(4, '2026-09-24', 1, 'DAÑADO', 'Portada desprendida'),
(5, '2026-10-03', 2, 'PÁGINAS FALTANTES', 'Faltan páginas 120-124');

INSERT INTO multa (id_devolucion, dias_retraso, valor_dia, monto, estado, fecha_pago) VALUES
(2, 4, 1000, 4000, 'PAGADA', '2026-09-15'),
(5, 6, 1000, 6000, 'PENDIENTE', NULL);




-- CONSULTAS PARA VALIDACIONES

-- SELECT * FROM prestamo;

-- SELECT * FROM ejemplar;


-- SELECT
 --    p.id_prestamo,
 --    p.estado,
 --    e.codigo_barras,
 --    e.estado AS estado_ejemplar,
  --   p.fecha_prestamo,
 --    p.fecha_vencimiento
-- FROM biblioteca_db_v2.prestamo p
-- JOIN biblioteca_db_v2.ejemplar e
 --    ON p.id_ejemplar = e.id_ejemplar
-- WHERE p.id_prestamo = 10;


-- SELECT
 --    NOW() AS fecha_hora_mysql,
 --    CURDATE() AS fecha_mysql,
 --    @@session.time_zone AS zona_horaria_sesion,
 --    @@global.time_zone AS zona_horaria_global;

-- SELECT
 --    fecha_prestamo,
 --    fecha_vencimiento,
 --    DATEDIFF(fecha_vencimiento, fecha_prestamo) AS dias_prestamo
-- FROM biblioteca_db_v2.prestamo
-- WHERE id_prestamo = 10;


-- SELECT
  --   DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s') AS fecha_hora_mysql,
  --   DATE_FORMAT(CURDATE(), '%Y-%m-%d') AS fecha_mysql,
  --   @@session.time_zone AS zona_sesion,
  --   @@system_time_zone AS zona_sistema;


-- SELECT
--     id_prestamo,
 --    DATE_FORMAT(fecha_prestamo, '%Y-%m-%d') AS fecha_prestamo,
 --    DATE_FORMAT(fecha_vencimiento, '%Y-%m-%d') AS fecha_vencimiento,
 --    DATEDIFF(fecha_vencimiento, fecha_prestamo) AS dias_prestamo
-- FROM biblioteca_db_v2.prestamo
-- WHERE id_prestamo = 10;


-- SELECT
--     p.id_prestamo,
 --    p.estado AS estado_prestamo,
 --    d.condicion,
 --    d.observaciones,
 --    e.codigo_barras,
 --    e.estado AS estado_ejemplar
-- FROM biblioteca_db_v2.prestamo p
-- JOIN biblioteca_db_v2.devolucion d
 --    ON p.id_prestamo = d.id_prestamo
-- JOIN biblioteca_db_v2.ejemplar e
--     ON p.id_ejemplar = e.id_ejemplar
-- WHERE p.id_prestamo = 7;


-- SELECT
--     codigo_barras,
 --    estado
-- FROM biblioteca_db_v2.ejemplar
-- WHERE id_libro = 2
-- ORDER BY codigo_barras;

-- SELECT
 --    codigo_barras,
 --    estado
-- FROM biblioteca_db_v2.ejemplar
-- WHERE codigo_barras = '1004';
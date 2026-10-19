"""Pruebas locales de seguridad; ejecutar dentro de la carpeta del proyecto."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
if os.getenv('DB_NAME') != 'biblioteca_db_v2':
    raise SystemExit('Configura DB_NAME=biblioteca_db_v2 antes de probar.')

from app import app
from db import conn


def consultar(sql, args=()):
    c = conn()
    try:
        cur = c.cursor(dictionary=True)
        cur.execute(sql, args)
        return cur.fetchone()
    finally:
        c.close()


client = app.test_client()

# PRUEBA 1: petición POST directa simulando la sesión de un usuario BLOQUEADO.
bloqueado = consultar("SELECT id_usuario, estado FROM usuario WHERE codigo=%s", ('200150004',))
assert bloqueado and bloqueado['estado'] == 'BLOQUEADO', 'El usuario de prueba no está bloqueado.'
libro = consultar('SELECT id_libro FROM libro WHERE isbn=%s', ('978-0078022159',))
assert libro, 'No se encontró el título para la prueba.'
sql_contar = 'SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND id_libro=%s'
antes = consultar(sql_contar, (bloqueado['id_usuario'], libro['id_libro']))['n']
with client.session_transaction() as sesion:
    sesion['id_usuario'] = bloqueado['id_usuario']
    sesion['csrf'] = 'token-local-prueba'
respuesta = client.post(f"/libros/{libro['id_libro']}/solicitar", data={'csrf': 'token-local-prueba'})
despues = consultar(sql_contar, (bloqueado['id_usuario'], libro['id_libro']))['n']
assert respuesta.status_code in (302, 303) and antes == despues, 'FALLO: se aceptó la solicitud del usuario bloqueado.'
with client.session_transaction() as sesion:
    mensajes = [str(m) for _, m in sesion.get('_flashes', [])]
assert any('activos' in m.lower() for m in mensajes), f'No se encontró el rechazo esperado: {mensajes}'
print('OK 1: POST de usuario bloqueado rechazado; no hubo nuevos préstamos.')

# PRUEBA 2: intentar alterar mediante POST el estado de un ejemplar PRESTADO.
ejemplar = consultar('SELECT id_ejemplar, codigo_barras, id_ubicacion, estado FROM ejemplar WHERE codigo_barras=%s', ('1005',))
assert ejemplar and ejemplar['estado'] == 'PRESTADO', 'El ejemplar 1005 debe estar PRESTADO para esta prueba.'
admin = consultar('SELECT id_usuario, rol, estado FROM usuario WHERE codigo=%s', ('admin',))
assert admin and admin['rol'] == 'BIBLIOTECARIO' and admin['estado'] == 'ACTIVO'
with client.session_transaction() as sesion:
    sesion['id_usuario'] = admin['id_usuario']
    sesion['csrf'] = 'token-local-prueba'
respuesta = client.post(f"/ejemplares/{ejemplar['id_ejemplar']}/editar", data={
    'codigo_barras': ejemplar['codigo_barras'],
    'id_ubicacion': str(ejemplar['id_ubicacion'] or ''),
    'estado': 'DISPONIBLE',
})
actual = consultar('SELECT estado FROM ejemplar WHERE id_ejemplar=%s', (ejemplar['id_ejemplar'],))
assert respuesta.status_code in (302, 303) and actual['estado'] == 'PRESTADO', 'FALLO: se logró liberar un ejemplar prestado.'
print('OK 2: el servidor conservó PRESTADO pese al POST de modificación.')
print('Las dos pruebas controladas terminaron correctamente.')

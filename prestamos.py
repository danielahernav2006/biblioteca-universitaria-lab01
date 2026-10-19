"""Integrante 5: solicitudes, aprobaciones, rechazos y devoluciones."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONA_BIBLIOTECA = ZoneInfo("America/Bogota")

def fecha_local():
    """Fecha civil de la biblioteca (Colombia), independiente de la zona del Mac."""
    return datetime.now(ZONA_BIBLIOTECA).date()
from decimal import Decimal
import hmac

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from mysql.connector import Error
from auth import login_requerido, rol_requerido
from db import conn, fetch

bp = Blueprint('prestamos', __name__, template_folder='templates')


def comprobar_csrf():
    if not hmac.compare_digest(request.form.get('csrf', ''), session.get('csrf', '')):
        abort(400)


def parametro(cursor, clave):
    cursor.execute('SELECT valor FROM parametro WHERE clave=%s', (clave,))
    dato = cursor.fetchone()
    if not dato:
        raise ValueError(f'Falta configurar el parámetro {clave}.')
    return dato['valor']


def ejecutar_transaccion(accion):
    conexion = conn()
    try:
        conexion.start_transaction()
        cursor = conexion.cursor(dictionary=True)
        mensaje = accion(cursor)
        conexion.commit()
        flash(mensaje, 'ok')
        return True
    except (ValueError, Error) as error:
        conexion.rollback()
        flash(str(error), 'error')
        return False
    finally:
        conexion.close()


@bp.get('/mis-prestamos')
@login_requerido
def mis_prestamos():
    filas = fetch('''SELECT p.*, l.titulo, e.codigo_barras, d.fecha_devolucion,
           m.monto, m.estado AS estado_multa
           FROM prestamo p JOIN libro l ON l.id_libro=p.id_libro
           LEFT JOIN ejemplar e ON e.id_ejemplar=p.id_ejemplar
           LEFT JOIN devolucion d ON d.id_prestamo=p.id_prestamo
           LEFT JOIN multa m ON m.id_devolucion=d.id_devolucion
           WHERE p.id_usuario=%s ORDER BY p.id_prestamo DESC''', (g.usuario['id_usuario'],))
    return render_template('mis_prestamos.html', prestamos=filas)


@bp.post('/libros/<int:id_libro>/solicitar')
@login_requerido
def solicitar(id_libro):
    comprobar_csrf()
    def accion(cur):
        cur.execute('SELECT id_usuario, rol, estado FROM usuario WHERE id_usuario=%s FOR UPDATE',
                    (g.usuario['id_usuario'],))
        usuario = cur.fetchone()
        if not usuario or usuario['estado'] != 'ACTIVO' or usuario['rol'] not in ('ESTUDIANTE', 'DOCENTE'):
            raise ValueError('Solo los estudiantes y docentes activos pueden solicitar préstamos.')
        cur.execute('SELECT id_libro FROM libro WHERE id_libro=%s', (id_libro,))
        if not cur.fetchone():
            raise ValueError('El libro no existe.')
        cur.execute("SELECT id_ejemplar FROM ejemplar WHERE id_libro=%s AND estado='DISPONIBLE' LIMIT 1", (id_libro,))
        if not cur.fetchone():
            raise ValueError('Este libro no tiene ejemplares disponibles.')
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND estado='ACTIVO'", (usuario['id_usuario'],))
        if cur.fetchone()['n'] >= int(parametro(cur, 'MAX_PRESTAMOS_ACTIVOS')):
            raise ValueError('Alcanzaste el máximo de préstamos activos.')
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND id_libro=%s AND estado IN ('SOLICITADO','ACTIVO')", (usuario['id_usuario'], id_libro))
        if cur.fetchone()['n']:
            raise ValueError('Ya tienes una solicitud o préstamo vigente de este título.')
        cur.execute("INSERT INTO prestamo (id_usuario,id_libro,fecha_solicitud,estado) VALUES (%s,%s,%s,'SOLICITADO')",
                    (usuario['id_usuario'], id_libro, fecha_local()))
        return 'Solicitud registrada. Debe aprobarla un bibliotecario.'
    ejecutar_transaccion(accion)
    return redirect(url_for('prestamos.mis_prestamos'))


@bp.get('/gestion-prestamos')
@rol_requerido('BIBLIOTECARIO')
def gestion():
    solicitudes = fetch('''SELECT p.id_prestamo,p.fecha_solicitud,u.nombres,l.titulo,l.id_libro,
         (SELECT COUNT(*) FROM ejemplar e WHERE e.id_libro=p.id_libro AND e.estado='DISPONIBLE') AS disponibles
         FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
         JOIN libro l ON l.id_libro=p.id_libro WHERE p.estado='SOLICITADO' ORDER BY p.fecha_solicitud,p.id_prestamo''')
    activos = fetch('''SELECT p.id_prestamo,p.fecha_prestamo,p.fecha_vencimiento,u.nombres,l.titulo,e.codigo_barras
         FROM prestamo p JOIN usuario u ON u.id_usuario=p.id_usuario
         JOIN libro l ON l.id_libro=p.id_libro JOIN ejemplar e ON e.id_ejemplar=p.id_ejemplar
         WHERE p.estado='ACTIVO' ORDER BY p.fecha_vencimiento''')
    return render_template('gestion_prestamos.html', solicitudes=solicitudes, activos=activos, hoy=fecha_local())


@bp.post('/prestamos/<int:id_prestamo>/aprobar')
@rol_requerido('BIBLIOTECARIO')
def aprobar(id_prestamo):
    comprobar_csrf()
    def accion(cur):
        cur.execute('SELECT * FROM prestamo WHERE id_prestamo=%s FOR UPDATE', (id_prestamo,))
        p = cur.fetchone()
        if not p or p['estado'] != 'SOLICITADO':
            raise ValueError('La solicitud no existe o ya fue procesada.')
        cur.execute('SELECT rol,estado FROM usuario WHERE id_usuario=%s FOR UPDATE', (p['id_usuario'],))
        u = cur.fetchone()
        if not u or u['estado'] != 'ACTIVO' or u['rol'] not in ('ESTUDIANTE','DOCENTE'):
            raise ValueError('El solicitante no está habilitado.')
        cur.execute("SELECT COUNT(*) AS n FROM prestamo WHERE id_usuario=%s AND estado='ACTIVO'", (p['id_usuario'],))
        if cur.fetchone()['n'] >= int(parametro(cur, 'MAX_PRESTAMOS_ACTIVOS')):
            raise ValueError('El usuario alcanzó su límite de préstamos activos.')
        # Se bloquean los ejemplares para evitar dos aprobaciones simultáneas del mismo ejemplar.
        cur.execute('SELECT id_ejemplar,codigo_barras,estado FROM ejemplar WHERE id_libro=%s ORDER BY id_ejemplar FOR UPDATE', (p['id_libro'],))
        disponible = next((x for x in cur.fetchall() if x['estado']=='DISPONIBLE'), None)
        if disponible is None:
            raise ValueError('No quedan ejemplares disponibles.')
        plazo = int(parametro(cur, 'DIAS_PRESTAMO_ESTUDIANTE' if u['rol']=='ESTUDIANTE' else 'DIAS_PRESTAMO_DOCENTE'))
        hoy = fecha_local()
        cur.execute("UPDATE ejemplar SET estado='PRESTADO' WHERE id_ejemplar=%s", (disponible['id_ejemplar'],))
        cur.execute("""UPDATE prestamo SET estado='ACTIVO',id_ejemplar=%s,fecha_prestamo=%s,
                    fecha_vencimiento=%s,id_bibliotecario=%s WHERE id_prestamo=%s""",
                    (disponible['id_ejemplar'],hoy,hoy+timedelta(days=plazo),g.usuario['id_usuario'],id_prestamo))
        return (f'Préstamo aprobado correctamente. Ejemplar asignado: {disponible["codigo_barras"]}. '
                f'Fecha de vencimiento: {(hoy + timedelta(days=plazo)).strftime("%d/%m/%Y")}.')
    ejecutar_transaccion(accion)
    return redirect(url_for('prestamos.gestion'))


@bp.post('/prestamos/<int:id_prestamo>/rechazar')
@rol_requerido('BIBLIOTECARIO')
def rechazar(id_prestamo):
    comprobar_csrf()
    motivo = request.form.get('motivo','').strip()[:200] or 'Solicitud rechazada por bibliotecario'
    def accion(cur):
        cur.execute('SELECT estado FROM prestamo WHERE id_prestamo=%s FOR UPDATE', (id_prestamo,))
        p = cur.fetchone()
        if not p or p['estado']!='SOLICITADO':
            raise ValueError('La solicitud ya fue procesada.')
        cur.execute("UPDATE prestamo SET estado='RECHAZADO',motivo_rechazo=%s,id_bibliotecario=%s WHERE id_prestamo=%s",
                    (motivo,g.usuario['id_usuario'],id_prestamo))
        return 'Solicitud rechazada.'
    ejecutar_transaccion(accion)
    return redirect(url_for('prestamos.gestion'))


@bp.post('/prestamos/<int:id_prestamo>/devolver')
@rol_requerido('BIBLIOTECARIO')
def devolver(id_prestamo):
    comprobar_csrf()
    condicion = request.form.get('condicion','BUENO')
    observaciones = request.form.get('observaciones','').strip()[:300]
    if condicion not in ('BUENO','DAÑADO','PÁGINAS FALTANTES'):
        abort(400)
    def accion(cur):
        cur.execute('SELECT * FROM prestamo WHERE id_prestamo=%s FOR UPDATE', (id_prestamo,))
        p = cur.fetchone()
        if not p or p['estado']!='ACTIVO' or not p['id_ejemplar']:
            raise ValueError('Este préstamo no está activo.')
        cur.execute('SELECT estado FROM ejemplar WHERE id_ejemplar=%s FOR UPDATE', (p['id_ejemplar'],))
        ejemplar = cur.fetchone()
        if not ejemplar or ejemplar['estado']!='PRESTADO':
            raise ValueError('El estado del ejemplar no coincide con el préstamo.')
        hoy = fecha_local()
        retraso = max((hoy-p['fecha_vencimiento']).days,0)
        tarifa = Decimal(parametro(cur,'TARIFA_MULTA_DIA'))
        cur.execute('''INSERT INTO devolucion (id_prestamo,fecha_devolucion,id_bibliotecario,condicion,observaciones)
                       VALUES (%s,%s,%s,%s,%s)''', (id_prestamo,hoy,g.usuario['id_usuario'],condicion,observaciones or None))
        devolucion_id = cur.lastrowid
        if retraso:
            cur.execute('''INSERT INTO multa (id_devolucion,dias_retraso,valor_dia,monto,estado)
                           VALUES (%s,%s,%s,%s,'PENDIENTE')''', (devolucion_id,retraso,tarifa,tarifa*retraso))
        cur.execute("UPDATE prestamo SET estado='DEVUELTO' WHERE id_prestamo=%s", (id_prestamo,))
        nuevo_estado = 'DISPONIBLE' if condicion == 'BUENO' else 'EN_REVISION'
        cur.execute('UPDATE ejemplar SET estado=%s WHERE id_ejemplar=%s', (nuevo_estado, p['id_ejemplar']))
        return (f'Devolución registrada. Retraso: {retraso} día(s). Multa: ${tarifa*retraso:,.0f} COP. '
                + ('Ejemplar EN REVISIÓN hasta que el bibliotecario lo habilite.' if nuevo_estado == 'EN_REVISION'
                   else 'Ejemplar nuevamente DISPONIBLE.'))
    ejecutar_transaccion(accion)
    return redirect(url_for('prestamos.gestion'))

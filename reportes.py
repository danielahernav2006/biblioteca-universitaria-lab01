from datetime import date, datetime

from flask import Blueprint, render_template, request
from auth import rol_requerido
from db import fetch

bp = Blueprint("reportes", __name__, template_folder="templates")


def fecha(texto, defecto):
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defecto


@bp.route("/reportes")
@rol_requerido("BIBLIOTECARIO")
def ver_reportes():
    hoy = date.today()
    desde = fecha(request.args.get("desde"), hoy.replace(month=1, day=1))
    hasta = fecha(request.args.get("hasta"), hoy)

    # ---------- Préstamos activos y vencidos ----------
    activos = fetch("""
        SELECT u.codigo, u.nombres, l.titulo, e.codigo_barras, p.fecha_prestamo, p.fecha_vencimiento,
               DATEDIFF(CURDATE(), p.fecha_vencimiento) AS dias_retraso
        FROM prestamo p
        JOIN usuario u ON u.id_usuario = p.id_usuario
        JOIN libro l ON l.id_libro = p.id_libro
        JOIN ejemplar e ON e.id_ejemplar = p.id_ejemplar
        WHERE p.estado = 'ACTIVO'
        ORDER BY p.fecha_vencimiento""")
    vencidos = [p for p in activos if p["dias_retraso"] > 0]

    # ---------- Libros más prestados en el periodo ----------
    libros = fetch("""
        SELECT l.titulo, l.isbn, COUNT(*) AS veces
        FROM prestamo p JOIN libro l ON l.id_libro = p.id_libro
        WHERE p.estado IN ('ACTIVO', 'DEVUELTO') AND p.fecha_prestamo BETWEEN %s AND %s
        GROUP BY l.id_libro, l.titulo, l.isbn
        ORDER BY veces DESC
        LIMIT 10""", (desde, hasta))

    # ---------- Usuarios con más préstamos en el periodo ----------
    usuarios = fetch("""
        SELECT u.codigo, u.nombres, u.rol, COUNT(*) AS prestamos
        FROM prestamo p JOIN usuario u ON u.id_usuario = p.id_usuario
        WHERE p.estado IN ('ACTIVO', 'DEVUELTO') AND p.fecha_prestamo BETWEEN %s AND %s
        GROUP BY u.id_usuario, u.codigo, u.nombres, u.rol
        ORDER BY prestamos DESC
        LIMIT 10""", (desde, hasta))

    # ---------- Inventario por estado ----------
    inventario = {"DISPONIBLE": 0, "PRESTADO": 0, "PERDIDO": 0, "EN_REVISION": 0}
    for r in fetch("SELECT estado, COUNT(*) AS cantidad FROM ejemplar GROUP BY estado"):
        inventario[r["estado"]] = r["cantidad"]

    return render_template("reportes.html", activos=activos, vencidos=vencidos, libros=libros,
                           usuarios=usuarios, inventario=inventario, desde=desde, hasta=hasta)

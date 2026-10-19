"""Página de inicio pública. Solo lee datos existentes: reutiliza la búsqueda del catálogo
y la tabla parametro."""
from flask import render_template
from catalogo import buscar
from db import fetch


def pagina_inicio():
    disponibles = buscar(solo_disp=True)
    cifras = fetch("""SELECT (SELECT COUNT(*) FROM libro) AS libros,
                             (SELECT COUNT(*) FROM ejemplar) AS ejemplares,
                             (SELECT COUNT(*) FROM ejemplar WHERE estado='DISPONIBLE') AS disponibles""",
                   one=True)
    parametros = {p["clave"]: p for p in fetch("SELECT * FROM parametro")}
    servicio = [parametros[k] for k in ("DIAS_PRESTAMO_ESTUDIANTE", "DIAS_PRESTAMO_DOCENTE",
                                        "MAX_PRESTAMOS_ACTIVOS") if k in parametros]
    return render_template("inicio.html", libros=disponibles[:6], cifras=cifras,
                           servicio=servicio)

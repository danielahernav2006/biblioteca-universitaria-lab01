"""Módulo de gestión de usuarios (Integrante 4). Solo para bibliotecarios.
Se registra como Blueprint, igual que el catálogo."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from mysql.connector import Error
from db import fetch
from catalogo import ejecutar
from auth import (rol_requerido, ROLES, traducir, validar_datos, validar_clave,
                  insertar_usuario, historial, carreras)

bp = Blueprint("usuarios", __name__, template_folder="templates")
solo_bibliotecario = rol_requerido("BIBLIOTECARIO")

CAMPOS = {
    "nombres": "u.nombres LIKE %s",
    "codigo": "u.codigo LIKE %s",
    "identificacion": "u.identificacion LIKE %s",
    "correo": "u.correo LIKE %s",
}


def buscar_usuario(id_usuario):
    return fetch("SELECT u.id_usuario, u.codigo, u.identificacion, u.nombres, u.correo, u.rol, "
                 "u.id_carrera, u.estado, c.nombre AS carrera FROM usuario u "
                 "LEFT JOIN carrera c ON c.id_carrera=u.id_carrera WHERE u.id_usuario=%s",
                 (id_usuario,), one=True) or abort(404)


def referencias(id_usuario):
    """Registros que dependen del usuario: impiden eliminarlo sin perder historial."""
    return fetch("""SELECT
        (SELECT COUNT(*) FROM prestamo WHERE id_usuario=%s) AS prestamos,
        (SELECT COUNT(*) FROM prestamo WHERE id_bibliotecario=%s) AS gestionados,
        (SELECT COUNT(*) FROM devolucion WHERE id_bibliotecario=%s) AS devoluciones""",
                 (id_usuario,) * 3, one=True)


@bp.route("/usuarios")
@solo_bibliotecario
def listar_usuarios():
    q = request.args.get("q", "").strip()
    campo = request.args.get("campo", "nombres")
    rol = request.args.get("rol", "")
    estado = request.args.get("estado", "")
    carrera = request.args.get("carrera", "")
    where, params = ["1=1"], []
    if q:
        where.append(CAMPOS.get(campo, CAMPOS["nombres"]))
        params.append(f"%{q}%")
    if rol in ROLES:
        where.append("u.rol=%s")
        params.append(rol)
    if estado in ("ACTIVO", "BLOQUEADO"):
        where.append("u.estado=%s")
        params.append(estado)
    if carrera.isdigit():
        where.append("u.id_carrera=%s")
        params.append(carrera)
    filas = fetch(f"""
        SELECT u.id_usuario, u.codigo, u.nombres, u.correo, u.rol, u.estado,
               c.nombre AS carrera,
               (SELECT COUNT(*) FROM prestamo p WHERE p.id_usuario=u.id_usuario
                  AND p.estado='ACTIVO') AS activos
        FROM usuario u LEFT JOIN carrera c ON c.id_carrera=u.id_carrera
        WHERE {' AND '.join(where)}
        ORDER BY u.nombres""", params)
    return render_template("usuarios.html", usuarios=filas, q=q, campo=campo, rol=rol,
                           estado=estado, carrera=carrera, carreras=carreras(), roles=ROLES)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@bp.route("/usuarios/<int:id_usuario>/editar", methods=["GET", "POST"])
@solo_bibliotecario
def form_usuario(id_usuario=None):
    actual = buscar_usuario(id_usuario) if id_usuario else None
    # el rol de un bibliotecario existente (incluido uno mismo) no se cambia desde aquí
    rol_fijo = actual["rol"] if actual and actual["rol"] == "BIBLIOTECARIO" else None
    u = actual or {}
    if request.method == "POST":
        f = request.form.to_dict()
        if rol_fijo:
            f["rol"] = rol_fijo
        datos, error = validar_datos(f, ROLES)
        clave = None
        if not error and not id_usuario:
            clave, error = validar_clave(f)
        if not error:
            try:
                if id_usuario:
                    ejecutar("UPDATE usuario SET codigo=%s, identificacion=%s, nombres=%s, "
                             "correo=%s, rol=%s, id_carrera=%s WHERE id_usuario=%s",
                             (datos["codigo"], datos["identificacion"], datos["nombres"],
                              datos["correo"], datos["rol"], datos["id_carrera"], id_usuario))
                else:
                    id_usuario = insertar_usuario(datos, clave)
                flash("Usuario guardado.", "ok")
                return redirect(url_for("usuarios.detalle_usuario", id_usuario=id_usuario))
            except Error as e:
                error = traducir(e)
        flash(error, "error")
        u = {**u, **datos}
    return render_template("usuario_form.html", u=u, editando=bool(actual), rol_fijo=rol_fijo,
                           roles=ROLES, carreras=carreras())


@bp.route("/usuarios/<int:id_usuario>")
@solo_bibliotecario
def detalle_usuario(id_usuario):
    u = buscar_usuario(id_usuario)
    refs = referencias(id_usuario)
    return render_template("usuario_detalle.html", u=u, prestamos=historial(id_usuario),
                           puede_eliminar=not any(refs.values()) and id_usuario != g.usuario["id_usuario"],
                           es_uno_mismo=id_usuario == g.usuario["id_usuario"])


@bp.post("/usuarios/<int:id_usuario>/estado")
@solo_bibliotecario
def cambiar_estado(id_usuario):
    u = buscar_usuario(id_usuario)
    if id_usuario == g.usuario["id_usuario"]:
        flash("No puedes bloquear tu propia cuenta.", "error")
    else:
        nuevo = "BLOQUEADO" if u["estado"] == "ACTIVO" else "ACTIVO"
        try:
            ejecutar("UPDATE usuario SET estado=%s WHERE id_usuario=%s", (nuevo, id_usuario))
            flash(f"Usuario {'bloqueado' if nuevo == 'BLOQUEADO' else 'activado'}.", "ok")
        except Error as e:
            flash(traducir(e), "error")
    return redirect(url_for("usuarios.detalle_usuario", id_usuario=id_usuario))


@bp.post("/usuarios/<int:id_usuario>/eliminar")
@solo_bibliotecario
def eliminar_usuario(id_usuario):
    buscar_usuario(id_usuario)
    refs = referencias(id_usuario)
    if id_usuario == g.usuario["id_usuario"]:
        flash("No puedes eliminar tu propia cuenta.", "error")
    elif any(refs.values()):
        flash("No se puede eliminar: el usuario tiene historial de préstamos o devoluciones. "
              "Bloquéalo en su lugar.", "error")
    else:
        try:
            ejecutar("DELETE FROM usuario WHERE id_usuario=%s", (id_usuario,))
            flash("Usuario eliminado.", "ok")
            return redirect(url_for("usuarios.listar_usuarios"))
        except Error as e:
            flash(traducir(e), "error")
    return redirect(url_for("usuarios.detalle_usuario", id_usuario=id_usuario))

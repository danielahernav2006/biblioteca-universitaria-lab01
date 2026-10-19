"""Módulo de acceso: inicio de sesión, registro público y permisos (Integrante 4).
Se registra como Blueprint, igual que el catálogo."""
import base64
import hashlib
import hmac
import os
import re
import secrets
from functools import wraps

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   session, g, abort)
from mysql.connector import Error
from db import conn, fetch

bp = Blueprint("auth", __name__, template_folder="templates")

ROLES = ("ESTUDIANTE", "DOCENTE", "BIBLIOTECARIO")
ROLES_REGISTRO = ("ESTUDIANTE", "DOCENTE")  # el registro público nunca crea bibliotecarios
CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.record_once
def configurar(state):
    app = state.app
    if os.getenv("SECRET_KEY"):
        app.secret_key = os.environ["SECRET_KEY"]
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")


# ---------- Contraseñas ----------
# La columna usuario.contraseña es VARCHAR(50) y los hashes de Werkzeug miden más de 100
# caracteres, así que no caben sin cambiar el esquema. Se usa PBKDF2-SHA256 de la biblioteca
# estándar con un formato compacto de 49 caracteres: "$p1$" + sal (16) + "$" + hash (28).
# Las cuentas existentes no se tocan: su contraseña sigue guardada tal como está.
PREFIJO = "$p1$"
ITERACIONES = 600_000


def _b64(datos):
    return base64.urlsafe_b64encode(datos).decode().rstrip("=")


def _derivar(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), sal.encode(), ITERACIONES, dklen=21)


def generar_hash(clave):
    sal = _b64(secrets.token_bytes(12))
    return f"{PREFIJO}{sal}${_b64(_derivar(clave, sal))}"


def verificar_clave(guardada, clave):
    if guardada.startswith(PREFIJO):
        sal, _, esperado = guardada[len(PREFIJO):].partition("$")
        return hmac.compare_digest(_b64(_derivar(clave, sal)), esperado)
    # cuentas creadas antes de este módulo (Lab1.sql): se comparan tal como están guardadas
    return hmac.compare_digest(guardada.encode(), clave.encode())


# ---------- Sesión y permisos ----------
@bp.before_app_request
def cargar_usuario():
    g.usuario = None
    if "id_usuario" in session:
        g.usuario = fetch("SELECT id_usuario, codigo, nombres, correo, rol, estado "
                          "FROM usuario WHERE id_usuario=%s", (session["id_usuario"],), one=True)
        if g.usuario is None:
            session.clear()


# Permisos del catálogo, aplicados desde aquí para no modificar catalogo.py.
# El listado (/libros) y la API JSON siguen siendo públicos.
CATALOGO_CON_SESION = {"catalogo.detalle_libro"}
CATALOGO_BIBLIOTECARIO = {"catalogo.form_libro", "catalogo.eliminar_libro",
                          "catalogo.form_ejemplar", "catalogo.eliminar_ejemplar"}


@bp.before_app_request
def proteger_catalogo():
    endpoint = request.endpoint
    if endpoint not in CATALOGO_CON_SESION | CATALOGO_BIBLIOTECARIO:
        return None
    if g.usuario is None:
        flash("Inicia sesión para continuar.", "error")
        siguiente = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=siguiente))
    if endpoint in CATALOGO_BIBLIOTECARIO and not (
            g.usuario["rol"] == "BIBLIOTECARIO" and g.usuario["estado"] == "ACTIVO"):
        abort(403)
    return None


@bp.app_errorhandler(403)
def prohibido(e):
    return render_template("prohibido.html"), 403


@bp.before_app_request
def revisar_csrf():
    # solo protege los formularios de los módulos nuevos; el catálogo queda igual
    if request.method == "POST" and request.blueprint in ("auth", "usuarios"):
        enviado = request.form.get("csrf", "")
        if not hmac.compare_digest(enviado, session.get("csrf", "")):
            abort(400)


@bp.app_context_processor
def contexto():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return {"usuario_actual": g.get("usuario"), "csrf_token": session["csrf"]}


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.usuario is None:
            flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return vista(*args, **kwargs)
    return envoltura


def rol_requerido(*roles):
    def decorador(vista):
        @wraps(vista)
        @login_requerido
        def envoltura(*args, **kwargs):
            if g.usuario["rol"] not in roles or g.usuario["estado"] != "ACTIVO":
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def destino_seguro(url):
    return url if url and url.startswith("/") and not url.startswith("//") else None


def inicio_por_rol(usuario):
    if usuario["rol"] == "BIBLIOTECARIO" and usuario["estado"] == "ACTIVO":
        return url_for("usuarios.listar_usuarios")
    return url_for("auth.mi_cuenta")


# ---------- Utilidades compartidas con usuarios.py ----------
def traducir(e):
    texto = str(e)
    if e.errno == 1062:
        for campo, nombre in (("codigo", "código"), ("identificacion", "identificación"),
                              ("correo", "correo")):
            if f"usuario.{campo}" in texto or f"'{campo}'" in texto:
                return f"Ya existe un usuario con ese {nombre}."
        return "Ya existe un usuario con esos datos."
    return {
        3819: "Un valor no cumple las restricciones (correo, rol o estado inválido).",
        4025: "Un valor no cumple las restricciones (correo, rol o estado inválido).",
        1451: "No se puede eliminar: hay registros relacionados.",
        1452: "La carrera seleccionada no existe.",
    }.get(e.errno, f"Error de base de datos: {e}")


def validar_datos(f, roles_permitidos):
    """Valida los campos comunes de usuario. Devuelve (datos, error)."""
    datos = {
        "codigo": f.get("codigo", "").strip(),
        "identificacion": f.get("identificacion", "").strip(),
        "nombres": " ".join(f.get("nombres", "").split()),
        "correo": f.get("correo", "").strip().lower(),
        "rol": f.get("rol", ""),
        "id_carrera": f.get("id_carrera") or None,
    }
    if not all((datos["codigo"], datos["identificacion"], datos["nombres"], datos["correo"])):
        return datos, "Código, identificación, nombres y correo son obligatorios."
    if len(datos["codigo"]) > 20 or len(datos["identificacion"]) > 20:
        return datos, "El código y la identificación admiten máximo 20 caracteres."
    if len(datos["nombres"]) > 150 or len(datos["correo"]) > 150:
        return datos, "Los nombres y el correo admiten máximo 150 caracteres."
    if not CORREO.match(datos["correo"]):
        return datos, "Ingresa un correo válido."
    if datos["rol"] not in roles_permitidos:
        return datos, "Selecciona un rol válido."
    if datos["id_carrera"] and not str(datos["id_carrera"]).isdigit():
        return datos, "La carrera seleccionada no existe."
    if datos["rol"] == "ESTUDIANTE" and not datos["id_carrera"]:
        return datos, "Los estudiantes deben tener una carrera."
    if datos["rol"] == "BIBLIOTECARIO":
        datos["id_carrera"] = None
    return datos, None


def validar_clave(f):
    clave = f.get("contrasena", "")
    if len(clave) < 8:
        return None, "La contraseña debe tener al menos 8 caracteres."
    if clave != f.get("confirmacion", ""):
        return None, "Las contraseñas no coinciden."
    return clave, None


def insertar_usuario(datos, clave):
    c = conn()
    try:
        cur = c.cursor()
        cur.execute("INSERT INTO usuario (codigo, identificacion, nombres, correo, rol, "
                    "id_carrera, contraseña) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (datos["codigo"], datos["identificacion"], datos["nombres"], datos["correo"],
                     datos["rol"], datos["id_carrera"], generar_hash(clave)))
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def historial(id_usuario):
    filas = fetch("""
        SELECT p.id_prestamo, p.fecha_solicitud, p.fecha_prestamo, p.fecha_vencimiento,
               p.estado, p.motivo_rechazo, l.id_libro, l.titulo, e.codigo_barras,
               d.fecha_devolucion, d.condicion, m.monto, m.estado AS estado_multa,
               (p.estado = 'ACTIVO' AND p.fecha_vencimiento < CURDATE()) AS vencido
        FROM prestamo p
        JOIN libro l ON l.id_libro = p.id_libro
        LEFT JOIN ejemplar e ON e.id_ejemplar = p.id_ejemplar
        LEFT JOIN devolucion d ON d.id_prestamo = p.id_prestamo
        LEFT JOIN multa m ON m.id_devolucion = d.id_devolucion
        WHERE p.id_usuario = %s
        ORDER BY p.fecha_solicitud DESC, p.id_prestamo DESC""", (id_usuario,))
    return filas


def carreras():
    return fetch("SELECT * FROM carrera ORDER BY nombre")


# ---------- Rutas ----------
@bp.route("/ingresar", methods=["GET", "POST"])
def login():
    if g.usuario:
        return redirect(inicio_por_rol(g.usuario))
    identificador = ""
    if request.method == "POST":
        identificador = request.form.get("identificador", "").strip()
        clave = request.form.get("contrasena", "")
        u = fetch("SELECT id_usuario, rol, estado, contraseña AS clave FROM usuario "
                  "WHERE codigo=%s OR correo=%s LIMIT 1",
                  (identificador, identificador.lower()), one=True) if identificador else None
        if u and clave and verificar_clave(u["clave"], clave):
            session.clear()
            session["id_usuario"] = u["id_usuario"]
            if u["estado"] == "BLOQUEADO":
                flash("Tu cuenta está bloqueada. Puedes consultar tu historial, "
                      "pero acércate a la biblioteca para resolverlo.", "error")
            destino = destino_seguro(request.args.get("next"))
            return redirect(destino or inicio_por_rol(u))
        flash("Código, correo o contraseña incorrectos.", "error")
    return render_template("login.html", identificador=identificador)


@bp.post("/salir")
def logout():
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("index"))


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if g.usuario:
        return redirect(inicio_por_rol(g.usuario))
    datos = {}
    if request.method == "POST":
        datos, error = validar_datos(request.form, ROLES_REGISTRO)
        clave = None
        if not error:
            clave, error = validar_clave(request.form)
        if not error:
            try:
                insertar_usuario(datos, clave)
                flash("Cuenta creada. Ya puedes iniciar sesión.", "ok")
                return redirect(url_for("auth.login"))
            except Error as e:
                error = traducir(e)
        flash(error, "error")
    return render_template("registro.html", u=datos, carreras=carreras())


@bp.route("/mi-cuenta")
@login_requerido
def mi_cuenta():
    u = fetch("SELECT u.id_usuario, u.codigo, u.identificacion, u.nombres, u.correo, u.rol, "
              "u.estado, c.nombre AS carrera FROM usuario u "
              "LEFT JOIN carrera c ON c.id_carrera=u.id_carrera WHERE u.id_usuario=%s",
              (g.usuario["id_usuario"],), one=True)
    return render_template("mi_cuenta.html", u=u, prestamos=historial(u["id_usuario"]))

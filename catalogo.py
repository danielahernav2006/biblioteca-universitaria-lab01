"""Módulo de catálogo: libros y ejemplares (Integrante 3).
Se registra como Blueprint para integrarlo con los módulos del resto del grupo."""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, abort)
from mysql.connector import Error
from db import conn, fetch

bp = Blueprint("catalogo", __name__, template_folder="templates")

# ---------- Búsqueda ----------
CAMPOS = {
    "titulo": "l.titulo LIKE %s",
    "isbn": "l.isbn LIKE %s",
    "autor": ("EXISTS (SELECT 1 FROM libro_autor la JOIN autor a ON a.id_autor=la.id_autor "
              "WHERE la.id_libro=l.id_libro AND a.nombre LIKE %s)"),
    "categoria": ("EXISTS (SELECT 1 FROM libro_categoria lc JOIN categoria c "
                  "ON c.id_categoria=lc.id_categoria "
                  "WHERE lc.id_libro=l.id_libro AND c.nombre LIKE %s)"),
}


def buscar(q="", campo="titulo", solo_disp=False):
    where, params = ["1=1"], []
    if q:
        where.append(CAMPOS.get(campo, CAMPOS["titulo"]))
        params.append(f"%{q}%")
    if solo_disp:
        where.append("EXISTS (SELECT 1 FROM ejemplar x WHERE x.id_libro=l.id_libro "
                     "AND x.estado='DISPONIBLE')")
    sql = f"""
        SELECT l.id_libro, l.isbn, l.titulo, l.`año` AS anio, e.nombre AS editorial,
          (SELECT GROUP_CONCAT(a.nombre SEPARATOR ', ') FROM libro_autor la
             JOIN autor a ON a.id_autor=la.id_autor WHERE la.id_libro=l.id_libro) AS autores,
          (SELECT GROUP_CONCAT(c.nombre SEPARATOR ', ') FROM libro_categoria lc
             JOIN categoria c ON c.id_categoria=lc.id_categoria WHERE lc.id_libro=l.id_libro) AS categorias,
          (SELECT COUNT(*) FROM ejemplar x WHERE x.id_libro=l.id_libro) AS total,
          (SELECT COUNT(*) FROM ejemplar x WHERE x.id_libro=l.id_libro
             AND x.estado='DISPONIBLE') AS disponibles
        FROM libro l LEFT JOIN editorial e ON e.id_editorial=l.id_editorial
        WHERE {' AND '.join(where)}
        ORDER BY l.titulo"""
    return fetch(sql, params)


@bp.route("/libros")
def listar_libros():
    q = request.args.get("q", "").strip()
    campo = request.args.get("campo", "titulo")
    solo = bool(request.args.get("solo_disp"))
    return render_template("libros.html", libros=buscar(q, campo, solo),
                           q=q, campo=campo, solo=solo)


# ---------- Utilidades ----------
def traducir(e):
    return {
        1062: "Ya existe un registro con ese valor único (ISBN o código de barras).",
        3819: "Un valor no cumple las restricciones (año entre 1400 y 2100, estado válido).",
        4025: "Un valor no cumple las restricciones (año entre 1400 y 2100, estado válido).",
        1451: "No se puede eliminar: hay registros relacionados.",
        1452: "Referencia inválida (editorial o ubicación inexistente).",
    }.get(e.errno, f"Error de base de datos: {e}")


def validar_libro(f):
    if not f.get("isbn", "").strip() or not f.get("titulo", "").strip():
        return "ISBN y título son obligatorios."
    anio = f.get("anio", "").strip()
    if anio and (not anio.isdigit() or not 1400 <= int(anio) <= 2100):
        return "El año debe estar entre 1400 y 2100."
    return None


def guardar_libro(id_libro, f):
    """Inserta o actualiza libro + autores + categorías en una sola transacción."""
    c = conn()
    try:
        cur = c.cursor()
        datos = (f["isbn"].strip(), f["titulo"].strip(), f.get("id_editorial") or None,
                 f.get("anio", "").strip() or None, f.get("descripcion", "").strip() or None)
        if id_libro is None:
            cur.execute("INSERT INTO libro (isbn, titulo, id_editorial, `año`, descripcion) "
                        "VALUES (%s,%s,%s,%s,%s)", datos)
            id_libro = cur.lastrowid
        else:
            cur.execute("UPDATE libro SET isbn=%s, titulo=%s, id_editorial=%s, `año`=%s, "
                        "descripcion=%s WHERE id_libro=%s", datos + (id_libro,))
            cur.execute("DELETE FROM libro_autor WHERE id_libro=%s", (id_libro,))
            cur.execute("DELETE FROM libro_categoria WHERE id_libro=%s", (id_libro,))
        for nombre in {n.strip() for n in f.get("autores", "").split(",") if n.strip()}:
            # busca el autor o lo crea; LAST_INSERT_ID devuelve su id en ambos casos
            cur.execute("INSERT INTO autor (nombre) VALUES (%s) "
                        "ON DUPLICATE KEY UPDATE id_autor=LAST_INSERT_ID(id_autor)", (nombre,))
            cur.execute("INSERT INTO libro_autor (id_libro, id_autor) VALUES (%s,%s)",
                        (id_libro, cur.lastrowid))
        for id_cat in set(f.getlist("categorias")):
            cur.execute("INSERT INTO libro_categoria (id_libro, id_categoria) VALUES (%s,%s)",
                        (id_libro, id_cat))
        c.commit()
        return id_libro
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def ejecutar(sql, params=()):
    c = conn()
    try:
        cur = c.cursor()
        cur.execute(sql, params)
        c.commit()
    finally:
        c.close()


# ---------- Libros: CRUD ----------
@bp.route("/libros/nuevo", methods=["GET", "POST"])
@bp.route("/libros/<int:id_libro>/editar", methods=["GET", "POST"])
def form_libro(id_libro=None):
    libro, autores, sel = None, "", []
    if id_libro:
        libro = fetch("SELECT id_libro, isbn, titulo, id_editorial, `año` AS anio, descripcion "
                      "FROM libro WHERE id_libro=%s", (id_libro,), one=True) or abort(404)
        autores = ", ".join(r["nombre"] for r in fetch(
            "SELECT a.nombre FROM libro_autor la JOIN autor a ON a.id_autor=la.id_autor "
            "WHERE la.id_libro=%s", (id_libro,)))
        sel = [r["id_categoria"] for r in fetch(
            "SELECT id_categoria FROM libro_categoria WHERE id_libro=%s", (id_libro,))]
    if request.method == "POST":
        f = request.form
        error = validar_libro(f)
        if not error:
            try:
                nuevo = guardar_libro(id_libro, f)
                flash("Libro guardado.")
                return redirect(url_for("catalogo.detalle_libro", id_libro=nuevo))
            except Error as e:
                error = traducir(e)
        flash(error)
        libro = {"id_libro": id_libro, "isbn": f["isbn"], "titulo": f["titulo"],
                 "id_editorial": int(f["id_editorial"]) if f.get("id_editorial") else None,
                 "anio": f.get("anio", ""), "descripcion": f.get("descripcion", "")}
        autores, sel = f.get("autores", ""), [int(x) for x in f.getlist("categorias")]
    return render_template("libro_form.html", libro=libro, autores=autores, sel=sel,
                           editoriales=fetch("SELECT * FROM editorial ORDER BY nombre"),
                           categorias=fetch("SELECT * FROM categoria ORDER BY nombre"))


@bp.route("/libros/<int:id_libro>")
def detalle_libro(id_libro):
    libro = buscar_uno(id_libro)
    ejemplares = fetch("SELECT e.*, u.sala, u.estante FROM ejemplar e "
                       "LEFT JOIN ubicacion u ON u.id_ubicacion=e.id_ubicacion "
                       "WHERE e.id_libro=%s ORDER BY e.codigo_barras", (id_libro,))
    return render_template("libro_detalle.html", l=libro, ejemplares=ejemplares)


def buscar_uno(id_libro):
    c = conn()
    try:
        filas = [r for r in buscar() if r["id_libro"] == id_libro]
    finally:
        c.close()
    if not filas:
        abort(404)
    row = filas[0]
    row["descripcion"] = fetch("SELECT descripcion FROM libro WHERE id_libro=%s",
                               (id_libro,), one=True)["descripcion"]
    return row


@bp.post("/libros/<int:id_libro>/eliminar")
def eliminar_libro(id_libro):
    n_ej = fetch("SELECT COUNT(*) n FROM ejemplar WHERE id_libro=%s", (id_libro,), one=True)["n"]
    n_pr = fetch("SELECT COUNT(*) n FROM prestamo WHERE id_libro=%s", (id_libro,), one=True)["n"]
    if n_ej or n_pr:
        flash(f"No se puede eliminar: tiene {n_ej} ejemplar(es) y {n_pr} préstamo(s) asociados. "
              "Elimine primero los ejemplares (si no tienen historial).")
        return redirect(url_for("catalogo.detalle_libro", id_libro=id_libro))
    try:
        ejecutar("DELETE FROM libro WHERE id_libro=%s", (id_libro,))  # autores/categorías: CASCADE
        flash("Libro eliminado.")
    except Error as e:
        flash(traducir(e))
        return redirect(url_for("catalogo.detalle_libro", id_libro=id_libro))
    return redirect(url_for("catalogo.listar_libros"))


# ---------- Ejemplares: CRUD ----------
@bp.route("/libros/<int:id_libro>/ejemplares/nuevo", methods=["GET", "POST"])
@bp.route("/ejemplares/<int:id_ejemplar>/editar", methods=["GET", "POST"])
def form_ejemplar(id_libro=None, id_ejemplar=None):
    ej = None
    if id_ejemplar:
        ej = fetch("SELECT * FROM ejemplar WHERE id_ejemplar=%s", (id_ejemplar,), one=True) or abort(404)
        id_libro = ej["id_libro"]
    libro = fetch("SELECT id_libro, titulo FROM libro WHERE id_libro=%s",
                  (id_libro,), one=True) or abort(404)
    bloqueado = bool(ej and ej["estado"] == "PRESTADO")  # el estado PRESTADO lo controla el módulo de préstamos
    if request.method == "POST":
        f = request.form
        cb = f.get("codigo_barras", "").strip()
        ubic = f.get("id_ubicacion") or None
        estado = f.get("estado", "DISPONIBLE")
        if bloqueado:
            estado = "PRESTADO"
        elif estado not in ("DISPONIBLE", "PERDIDO", "EN_REVISION"):
            estado = "DISPONIBLE"
        if not cb:
            flash("El código de barras es obligatorio.")
        else:
            try:
                if id_ejemplar:
                    ejecutar("UPDATE ejemplar SET codigo_barras=%s, id_ubicacion=%s, estado=%s "
                             "WHERE id_ejemplar=%s", (cb, ubic, estado, id_ejemplar))
                else:
                    ejecutar("INSERT INTO ejemplar (codigo_barras, id_libro, id_ubicacion, estado) "
                             "VALUES (%s,%s,%s,%s)", (cb, id_libro, ubic, estado))
                flash("Ejemplar guardado.")
                return redirect(url_for("catalogo.detalle_libro", id_libro=id_libro))
            except Error as e:
                flash(traducir(e))
        ej = {"codigo_barras": cb, "id_ubicacion": int(ubic) if ubic else None, "estado": estado}
    return render_template("ejemplar_form.html", ej=ej, libro=libro, bloqueado=bloqueado,
                           editando=bool(id_ejemplar),
                           ubicaciones=fetch("SELECT * FROM ubicacion ORDER BY sala, estante"))


@bp.post("/ejemplares/<int:id_ejemplar>/eliminar")
def eliminar_ejemplar(id_ejemplar):
    ej = fetch("SELECT * FROM ejemplar WHERE id_ejemplar=%s", (id_ejemplar,), one=True) or abort(404)
    n_pr = fetch("SELECT COUNT(*) n FROM prestamo WHERE id_ejemplar=%s", (id_ejemplar,), one=True)["n"]
    if ej["estado"] == "PRESTADO":
        flash("No se puede eliminar un ejemplar que está prestado.")
    elif n_pr:
        flash("No se puede eliminar: el ejemplar tiene historial de préstamos. Márquelo como PERDIDO.")
    else:
        try:
            ejecutar("DELETE FROM ejemplar WHERE id_ejemplar=%s", (id_ejemplar,))
            flash("Ejemplar eliminado.")
        except Error as e:
            flash(traducir(e))
    return redirect(url_for("catalogo.detalle_libro", id_libro=ej["id_libro"]))


# ---------- Endpoints JSON ----------
@bp.route("/api/libros")
def api_libros():
    filas = buscar(request.args.get("q", "").strip(), request.args.get("campo", "titulo"),
                   bool(request.args.get("solo_disp")))
    return jsonify(filas)


@bp.route("/api/libros/<int:id_libro>/disponibilidad")
def api_disponibilidad(id_libro):
    filas = fetch("SELECT estado, COUNT(*) AS cantidad FROM ejemplar WHERE id_libro=%s "
                  "GROUP BY estado", (id_libro,))
    return jsonify({"id_libro": id_libro, **{r["estado"]: r["cantidad"] for r in filas}})

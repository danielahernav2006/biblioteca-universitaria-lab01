import os
import mysql.connector


def conn():
    conexion = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "biblioteca_db_v2"),
    )
    # CURDATE() y funciones SQL usan la fecha civil de Colombia.
    conexion.time_zone = "-05:00"
    return conexion


def fetch(sql, params=(), one=False):
    c = conn()
    try:
        cur = c.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        if one:
            return rows[0] if rows else None
        return rows
    finally:
        c.close()

"""Sistema de Inventario Tecnologico — Creation Technologies.

Aplicacion Flask (servida con Gunicorn) + MySQL 8.4 + Nginx.

Correcciones frente a la version anterior (srv2-proj-main):
- Las credenciales ya no estan escritas en el codigo: se leen de
  variables de entorno (.env). Sin .env la app no arranca el login
  con contrasenas por defecto.
- Login real: valida nombre + contrasena (hash PBKDF2) y crea una
  sesion en el servidor. La ruta /empleado (que entraba solo con el
  nombre) fue eliminada.
- Roles: supervisor (CEO / Supervisor / Administrador) y empleado.
  Surtir, peticiones, altas e historial son solo de supervisor.
- Endpoint /salud (lo exigen la propuesta y la Practica 12).
- Formularios de alta de usuario y componente ahora tienen endpoint
  (POST /api/empleados y POST /api/componentes).
- Cancelar pedido: POST /api/pedidos/<id>/cancelar.
- Historial: GET /api/historial + pagina /historial.
- /inventario usa LEFT JOIN: los componentes sin fila de inventario
  ya aparecen (cantidad 0) en vez de ser invisibles.
- Los eventos NFC se guardan en la tabla eventos_nfc (antes vivian
  solo en memoria y se perdian al reiniciar).
- /api/retiro-nfc acepta una lista opcional de ids_pedidos para
  retirar solo algunos pedidos, no todos de golpe.
- La base de datos ya no se restaura desde un .sql en el arranque:
  MySQL ejecuta db/init.sql la primera vez (volumen vacio). Esta app
  no toca la BD al importar; Gunicorn puede arrancar aunque MySQL
  todavia no este listo (depends_on con healthcheck lo ordena).
- Sin debug=True en produccion: se sirve con Gunicorn.
"""
import hashlib
import json
import os
import secrets
from functools import wraps

import mysql.connector
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)

# ---------- Configuracion (variables de entorno, archivo .env) ----------
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "app_inventario")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "inventario_ct")
ORGANIZACION = os.environ.get("ORGANIZACION", "Creation Technologies")
# Clave opcional del lector NFC: si esta definida, /api/retiro-nfc exige
# la cabecera X-Lector-Clave con ese valor.
LECTOR_CLAVE = os.environ.get("LECTOR_CLAVE", "")

_clave_secreta = os.environ.get("SECRET_KEY", "")
if not _clave_secreta:
    _clave_secreta = secrets.token_hex(32)
    print("[AVISO] SECRET_KEY no definida: se genero una temporal. "
          "Las sesiones no sobreviviran a un reinicio. "
          "Define SECRET_KEY en .env.")
app.secret_key = _clave_secreta
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ---------- Contrasenas (PBKDF2-SHA256, sin dependencias extra) ----------
def hash_password(password):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260000)
    return f"pbkdf2_sha256$260000${salt.hex()}${dk.hex()}"


def verify_password(stored, password):
    """Acepta hashes PBKDF2 y, solo como migracion, texto plano.

    Si la contrasena guardada es texto plano y coincide, devuelve True
    y el llamador debe re-guardarla con hash (ver login).
    """
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iters, salt_hex, hash_hex = stored.split("$")
            dk = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"),
                bytes.fromhex(salt_hex), int(iters),
            )
            return dk.hex() == hash_hex
        except (ValueError, AttributeError):
            return False
    return stored == password


def _es_hash(stored):
    return stored.startswith("pbkdf2_sha256$")


# ---------- Base de datos ----------
def connect():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


# ---------- Sesion y roles ----------
PUESTOS_SUPERVISOR = {"ceo", "supervisor", "administrador", "admin"}


def es_supervisor(empleado):
    if not empleado:
        return False
    return (empleado.get("puesto") or "").strip().lower() in PUESTOS_SUPERVISOR


def empleado_actual():
    return session.get("empleado")


def login_requerido(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not empleado_actual():
            return jsonify({"error": "Sesión no iniciada"}), 401
        return func(*args, **kwargs)
    return wrapper


def supervisor_requerido(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        empleado = empleado_actual()
        if not empleado:
            return jsonify({"error": "Sesión no iniciada"}), 401
        if not es_supervisor(empleado):
            return jsonify({"error": "Se requiere rol de supervisor"}), 403
        return func(*args, **kwargs)
    return wrapper


def pagina_login_requerida(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not empleado_actual():
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def pagina_supervisor_requerida(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        empleado = empleado_actual()
        if not empleado:
            return redirect(url_for("login"))
        if not es_supervisor(empleado):
            return redirect(url_for("home"))
        return func(*args, **kwargs)
    return wrapper


# ---------- Eventos NFC (persistentes, tabla eventos_nfc) ----------
def registrar_evento_nfc(tipo, nfc_id=None, id_empleado=None, detalle=None):
    """Guarda el evento en BD. Nunca rompe el flujo principal."""
    try:
        conexion = connect()
        cursor = conexion.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO eventos_nfc (tipo, nfc_id, id_empleado, detalle)
                VALUES (%s, %s, %s, %s)
                """,
                (tipo, nfc_id, id_empleado,
                 json.dumps(detalle, ensure_ascii=False) if detalle else None),
            )
            conexion.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conexion.close()
    except Exception as error:  # noqa: BLE001 - el evento no debe tumbar nada
        print(f"[AVISO] No se pudo registrar evento NFC {tipo}: {error}")
        return None


# ---------- Paginas ----------
@app.route("/")
@pagina_login_requerida
def home():
    return render_template(
        "index.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
        es_supervisor=es_supervisor(empleado_actual()),
    )


@app.route("/login")
def login():
    if empleado_actual():
        return redirect(url_for("home"))
    return render_template("login.html", organizacion=ORGANIZACION)


@app.route("/pedir")
@pagina_login_requerida
def pedir():
    return render_template(
        "cliente.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
    )


@app.route("/surtir")
@pagina_supervisor_requerida
def surtir():
    return render_template(
        "surtir_comp.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
    )


@app.route("/empleados/nuevo")
@pagina_supervisor_requerida
def nuevo_empleado():
    return render_template(
        "insert-usuario.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
    )


@app.route("/componentes/nuevo")
@pagina_supervisor_requerida
def nuevo_componente():
    return render_template(
        "insert-component.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
    )


@app.route("/historial")
@pagina_supervisor_requerida
def historial_pagina():
    return render_template(
        "historial.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
    )


# ---------- Salud (Practica 12: prueba de humo) ----------
@app.route("/salud")
def salud():
    try:
        conexion = connect()
        cursor = conexion.cursor(dictionary=True)
        try:
            cursor.execute("SELECT COUNT(*) AS n FROM componentes")
            componentes = cursor.fetchone()["n"]
            cursor.execute(
                "SELECT COUNT(*) AS n FROM pedidos WHERE estado = 'pendiente'"
            )
            pendientes = cursor.fetchone()["n"]
        finally:
            cursor.close()
            conexion.close()
        return jsonify({
            "estado": "ok",
            "componentes": componentes,
            "pedidos_pendientes": pendientes,
        }), 200
    except mysql.connector.Error:
        return jsonify({"estado": "error"}), 503


# ---------- Sesion ----------
@app.route("/api/login", methods=["POST"])
def api_login():
    datos = request.get_json(silent=True) or {}
    nombre = str(datos.get("nombre", "")).strip()
    contrasena = str(datos.get("contrasena", ""))

    if not nombre or not contrasena:
        return jsonify({"error": "Nombre y contraseña son obligatorios"}), 400

    try:
        conexion = connect()
    except mysql.connector.Error:
        return jsonify({"error": "Base de datos no disponible"}), 503
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id_empleado, nombre, puesto, contrasena
            FROM empleados
            WHERE nombre = %s
            """,
            (nombre,),
        )
        empleado = cursor.fetchone()
        if not empleado or not verify_password(
            empleado["contrasena"], contrasena
        ):
            return jsonify({"error": "Nombre o contraseña incorrectos"}), 401

        # Migracion: si la contrasena estaba en texto plano, guardarla
        # con hash a partir de ahora.
        if not _es_hash(empleado["contrasena"]):
            cursor.execute(
                "UPDATE empleados SET contrasena = %s WHERE id_empleado = %s",
                (hash_password(contrasena), empleado["id_empleado"]),
            )
            conexion.commit()

        session["empleado"] = {
            "id_empleado": empleado["id_empleado"],
            "nombre": empleado["nombre"],
            "puesto": empleado["puesto"],
        }
        return jsonify({"empleado": session["empleado"]}), 200
    except mysql.connector.Error as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"mensaje": "Sesión cerrada"}), 200


@app.route("/api/me", methods=["GET"])
def api_me():
    empleado = empleado_actual()
    if not empleado:
        return jsonify({"error": "Sesión no iniciada"}), 401
    return jsonify({
        "empleado": empleado,
        "es_supervisor": es_supervisor(empleado),
    }), 200


# ---------- Inventario ----------
@app.route("/inventario", methods=["GET"])
@login_requerido
def get_components():
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                c.id_componente,
                c.nombre,
                c.categoria,
                c.descripcion,
                c.estado,
                i.id_inventario,
                COALESCE(i.cantidad, 0) AS cantidad,
                i.ubicacion,
                i.precio,
                COALESCE(i.stock_minimo, 10) AS stock_minimo,
                (COALESCE(i.cantidad, 0) < COALESCE(i.stock_minimo, 10))
                    AS bajo_stock
            FROM componentes c
            LEFT JOIN inventario i
                ON c.id_componente = i.id_componente
            ORDER BY c.nombre ASC
            """
        )
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/inventario_nombre", methods=["GET"])
@login_requerido
def get_components_nombre():
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT nombre FROM componentes ORDER BY nombre ASC")
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/surtir_componentes", methods=["POST"])
@supervisor_requerido
def surtir_componentes():
    datos = request.get_json(silent=True) or {}
    items = datos.get("componentes", [])

    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "No hay componentes para surtir"}), 400

    totales = {}
    for item in items:
        nombre = str(item.get("nombre", "")).strip()
        ubicacion = str(item.get("ubicacion", "") or "").strip().upper()
        try:
            cantidad = int(item.get("cantidad", 0))
        except (ValueError, TypeError):
            return jsonify({"error": f"Cantidad inválida para '{nombre}'"}), 400
        if not nombre or cantidad <= 0:
            return jsonify({"error": "Nombre o cantidad no válidos"}), 400
        clave = (nombre, ubicacion)
        totales[clave] = totales.get(clave, 0) + cantidad

    conexion = None
    cursor = None
    try:
        conexion = connect()
        cursor = conexion.cursor(dictionary=True)
        actualizados = []

        for (nombre, ubicacion), cantidad_a_sumar in totales.items():
            cursor.execute(
                "SELECT id_componente FROM componentes WHERE nombre = %s",
                (nombre,),
            )
            comp = cursor.fetchone()
            if not comp:
                conexion.rollback()
                return jsonify(
                    {"error": f"El componente '{nombre}' no existe"}
                ), 404
            id_componente = comp["id_componente"]

            if ubicacion:
                cursor.execute(
                    """
                    SELECT id_inventario FROM inventario
                    WHERE id_componente = %s AND ubicacion = %s
                    FOR UPDATE
                    """,
                    (id_componente, ubicacion),
                )
                fila = cursor.fetchone()
                if fila:
                    cursor.execute(
                        """
                        UPDATE inventario
                        SET cantidad = cantidad + %s
                        WHERE id_inventario = %s
                        """,
                        (cantidad_a_sumar, fila["id_inventario"]),
                    )
                    ubicacion_final = ubicacion
                else:
                    cursor.execute(
                        """
                        INSERT INTO inventario
                            (id_componente, cantidad, ubicacion, precio)
                        VALUES (%s, %s, %s, NULL)
                        """,
                        (id_componente, cantidad_a_sumar, ubicacion),
                    )
                    ubicacion_final = ubicacion
            else:
                cursor.execute(
                    """
                    SELECT id_inventario, ubicacion FROM inventario
                    WHERE id_componente = %s
                    ORDER BY id_inventario ASC
                    FOR UPDATE
                    """,
                    (id_componente,),
                )
                filas_inv = cursor.fetchall()
                if filas_inv:
                    cursor.execute(
                        """
                        UPDATE inventario
                        SET cantidad = cantidad + %s
                        WHERE id_inventario = %s
                        """,
                        (cantidad_a_sumar, filas_inv[0]["id_inventario"]),
                    )
                    ubicacion_final = filas_inv[0]["ubicacion"]
                else:
                    cursor.execute(
                        """
                        INSERT INTO inventario
                            (id_componente, cantidad, ubicacion, precio)
                        VALUES (%s, %s, 'GENERAL', NULL)
                        """,
                        (id_componente, cantidad_a_sumar),
                    )
                    ubicacion_final = "GENERAL"

            actualizados.append({
                "id_componente": id_componente,
                "nombre": nombre,
                "ubicacion": ubicacion_final,
                "cantidad_sumada": cantidad_a_sumar,
            })

        conexion.commit()
        return jsonify({
            "mensaje": "Inventario surtido correctamente",
            "actualizados": actualizados,
        }), 200
    except Exception as error:
        if conexion:
            conexion.rollback()
        return jsonify(
            {"error": "Error al surtir inventario", "detalle": str(error)}
        ), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()


# ---------- Altas (antes los formularios no tenian endpoint) ----------
@app.route("/api/empleados", methods=["POST"])
@supervisor_requerido
def crear_empleado():
    datos = request.get_json(silent=True) or {}
    nombre = str(datos.get("nombre", "")).strip()
    puesto = str(datos.get("puesto", "") or "").strip() or None
    nfc_id = str(datos.get("nfc_id", "") or "").strip().upper() or None
    contrasena = str(datos.get("contrasena", ""))

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400
    if len(contrasena) < 6:
        return jsonify(
            {"error": "La contraseña debe tener al menos 6 caracteres"}
        ), 400

    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        if nfc_id:
            cursor.execute(
                "SELECT id_empleado FROM empleados WHERE UPPER(nfc_id) = %s",
                (nfc_id,),
            )
            if cursor.fetchone():
                return jsonify(
                    {"error": f"El NFC {nfc_id} ya está registrado"}
                ), 409
        cursor.execute(
            """
            INSERT INTO empleados (nombre, puesto, nfc_id, contrasena)
            VALUES (%s, %s, %s, %s)
            """,
            (nombre, puesto, nfc_id, hash_password(contrasena)),
        )
        conexion.commit()
        return jsonify({
            "mensaje": "Empleado creado correctamente",
            "id_empleado": cursor.lastrowid,
        }), 201
    except mysql.connector.Error as error:
        conexion.rollback()
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/api/componentes", methods=["POST"])
@supervisor_requerido
def crear_componente():
    datos = request.get_json(silent=True) or {}
    nombre = str(datos.get("nombre", "")).strip()
    categoria = str(datos.get("categoria", "") or "").strip() or None
    descripcion = str(datos.get("descripcion", "") or "").strip() or None
    ubicacion = str(datos.get("ubicacion", "") or "").strip().upper() or None
    try:
        cantidad = datos.get("cantidad")
        cantidad = None if cantidad in (None, "") else int(cantidad)
        precio = datos.get("precio")
        precio = None if precio in (None, "") else float(precio)
        stock_minimo = datos.get("stock_minimo")
        stock_minimo = (
            None if stock_minimo in (None, "") else int(stock_minimo)
        )
    except (ValueError, TypeError):
        return jsonify({"error": "Cantidad, precio o stock mínimo no válidos"}), 400

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400
    if cantidad is not None and cantidad < 0:
        return jsonify({"error": "La cantidad no puede ser negativa"}), 400

    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_componente FROM componentes WHERE nombre = %s",
            (nombre,),
        )
        if cursor.fetchone():
            return jsonify(
                {"error": f"El componente '{nombre}' ya existe"}
            ), 409
        cursor.execute(
            """
            INSERT INTO componentes (nombre, categoria, descripcion)
            VALUES (%s, %s, %s)
            """,
            (nombre, categoria, descripcion),
        )
        id_componente = cursor.lastrowid
        id_inventario = None
        if ubicacion is not None or cantidad is not None:
            cursor.execute(
                """
                INSERT INTO inventario
                    (id_componente, cantidad, ubicacion, precio, stock_minimo)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    id_componente,
                    cantidad or 0,
                    ubicacion or "GENERAL",
                    precio,
                    stock_minimo if stock_minimo is not None else 10,
                ),
            )
            id_inventario = cursor.lastrowid
        conexion.commit()
        return jsonify({
            "mensaje": "Componente creado correctamente",
            "id_componente": id_componente,
            "id_inventario": id_inventario,
        }), 201
    except mysql.connector.Error as error:
        conexion.rollback()
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


# ---------- Solicitudes y pedidos ----------
@app.route("/api/solicitudes", methods=["POST"])
@login_requerido
def crear_solicitud():
    datos = request.get_json(silent=True)
    if not datos:
        return jsonify({"error": "No se recibieron datos"}), 400

    empleado = empleado_actual()
    componentes = datos.get("componentes", [])
    comentarios = datos.get("comentarios", "")

    if not isinstance(componentes, list) or len(componentes) == 0:
        return jsonify({"error": "La solicitud no contiene componentes"}), 400

    try:
        ids_inventario = set()
        for item in componentes:
            id_inventario = int(item["id_inventario"])
            cantidad = int(item["cantidad"])
            if id_inventario <= 0 or cantidad <= 0:
                return jsonify({
                    "error": "Los componentes y cantidades deben ser válidos"
                }), 400
            if id_inventario in ids_inventario:
                return jsonify({
                    "error": "Hay componentes repetidos en la solicitud"
                }), 400
            ids_inventario.add(id_inventario)
    except (ValueError, TypeError, KeyError):
        return jsonify({"error": "Los datos de los componentes no son válidos"}), 400

    id_empleado = empleado["id_empleado"]
    conexion = None
    cursor = None
    try:
        conexion = connect()
        cursor = conexion.cursor(dictionary=True)

        for item in componentes:
            id_inventario = int(item["id_inventario"])
            cantidad = int(item["cantidad"])
            cursor.execute(
                """
                SELECT id_componente, cantidad FROM inventario
                WHERE id_inventario = %s
                """,
                (id_inventario,),
            )
            inventario = cursor.fetchone()
            if not inventario:
                return jsonify({
                    "error": f"No existe el elemento de inventario {id_inventario}"
                }), 404
            if cantidad > inventario["cantidad"]:
                return jsonify({
                    "error": f"No hay suficientes existencias para el inventario {id_inventario}"
                }), 400

        cursor.execute(
            "INSERT INTO pedidos (id_empleado, comentarios) VALUES (%s, %s)",
            (id_empleado, comentarios),
        )
        id_pedido = cursor.lastrowid

        for item in componentes:
            id_inventario = int(item["id_inventario"])
            cantidad = int(item["cantidad"])
            cursor.execute(
                "SELECT id_componente FROM inventario WHERE id_inventario = %s",
                (id_inventario,),
            )
            id_componente = cursor.fetchone()["id_componente"]
            cursor.execute(
                """
                INSERT INTO historial_pedidos
                    (id_componente, id_empleado, cantidad, recibido, id_pedido)
                VALUES (%s, %s, %s, 0, %s)
                """,
                (id_componente, id_empleado, cantidad, id_pedido),
            )

        conexion.commit()
        return jsonify({
            "mensaje": "Solicitud enviada correctamente",
            "id_pedido": id_pedido,
        }), 201
    except Exception as error:
        if conexion:
            conexion.rollback()
        print("ERROR AL GUARDAR SOLICITUD:", repr(error))
        return jsonify({
            "error": "Error al guardar la solicitud",
            "detalle": str(error),
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


@app.route("/api/peticiones", methods=["GET"])
@supervisor_requerido
def obtener_peticiones():
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                p.id_pedido,
                e.nombre AS empleado,
                p.fecha_hora,
                p.estado,
                p.comentarios,
                c.nombre AS componente,
                h.cantidad
            FROM pedidos p
            INNER JOIN empleados e ON p.id_empleado = e.id_empleado
            INNER JOIN historial_pedidos h ON p.id_pedido = h.id_pedido
            INNER JOIN componentes c ON h.id_componente = c.id_componente
            WHERE p.estado = 'pendiente'
            ORDER BY p.fecha_hora ASC, p.id_pedido ASC
            """
        )
        filas = cursor.fetchall()
        peticiones = {}
        for fila in filas:
            id_pedido = fila["id_pedido"]
            if id_pedido not in peticiones:
                peticiones[id_pedido] = {
                    "id_pedido": id_pedido,
                    "empleado": fila["empleado"],
                    "fecha_hora": fila["fecha_hora"].strftime("%d/%m/%Y %H:%M"),
                    "estado": fila["estado"],
                    "comentarios": fila["comentarios"] or "",
                    "componentes": [],
                }
            if fila["componente"]:
                peticiones[id_pedido]["componentes"].append({
                    "nombre": fila["componente"],
                    "cantidad": fila["cantidad"],
                })
        return jsonify(list(peticiones.values())), 200
    except mysql.connector.Error as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/api/pedidos/<int:id_pedido>/cancelar", methods=["POST"])
@login_requerido
def cancelar_pedido(id_pedido):
    empleado = empleado_actual()
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        if es_supervisor(empleado):
            cursor.execute(
                """
                UPDATE pedidos SET estado = 'cancelado'
                WHERE id_pedido = %s AND estado = 'pendiente'
                """,
                (id_pedido,),
            )
        else:
            cursor.execute(
                """
                UPDATE pedidos SET estado = 'cancelado'
                WHERE id_pedido = %s AND estado = 'pendiente'
                  AND id_empleado = %s
                """,
                (id_pedido, empleado["id_empleado"]),
            )
        if cursor.rowcount == 0:
            conexion.rollback()
            return jsonify({
                "error": "El pedido no existe, no es tuyo o ya no está pendiente"
            }), 404
        conexion.commit()
        return jsonify({"mensaje": "Pedido cancelado"}), 200
    except mysql.connector.Error as error:
        conexion.rollback()
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/api/historial", methods=["GET"])
@supervisor_requerido
def obtener_historial():
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                h.id_historial,
                c.nombre AS componente,
                e.nombre AS empleado,
                h.cantidad,
                h.fecha_hora,
                h.recibido,
                h.id_pedido
            FROM historial_pedidos h
            INNER JOIN componentes c ON h.id_componente = c.id_componente
            INNER JOIN empleados e ON h.id_empleado = e.id_empleado
            ORDER BY h.fecha_hora DESC, h.id_historial DESC
            LIMIT 100
            """
        )
        filas = cursor.fetchall()
        for fila in filas:
            fila["fecha_hora"] = fila["fecha_hora"].strftime("%d/%m/%Y %H:%M")
            fila["recibido"] = bool(fila["recibido"])
        return jsonify(filas), 200
    except mysql.connector.Error as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


# ---------- NFC ----------
@app.route("/api/nfc-eventos", methods=["GET"])
@login_requerido
def obtener_eventos_nfc():
    desde = request.args.get("desde", type=int)
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COALESCE(MAX(id), 0) AS ultimo FROM eventos_nfc")
        ultimo = cursor.fetchone()["ultimo"]
        if desde is None:
            return jsonify({"ultimo_id": ultimo, "eventos": []}), 200
        cursor.execute(
            """
            SELECT e.id, e.tipo, e.nfc_id, e.detalle,
                   emp.nombre AS empleado
            FROM eventos_nfc e
            LEFT JOIN empleados emp ON e.id_empleado = emp.id_empleado
            WHERE e.id > %s
            ORDER BY e.id ASC
            LIMIT 50
            """,
            (desde,),
        )
        eventos = []
        for fila in cursor.fetchall():
            evento = {
                "id": fila["id"],
                "tipo": fila["tipo"],
                "nfc_id": fila["nfc_id"],
                "empleado": fila["empleado"],
            }
            if fila["detalle"]:
                try:
                    evento.update(json.loads(fila["detalle"]))
                except (ValueError, TypeError):
                    pass
            eventos.append(evento)
        return jsonify({"ultimo_id": ultimo, "eventos": eventos}), 200
    except mysql.connector.Error as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


@app.route("/api/retiro-nfc", methods=["POST"])
def retiro_nfc():
    # El lector no tiene sesion: si se definio LECTOR_CLAVE en .env,
    # debe enviarla como cabecera X-Lector-Clave.
    if LECTOR_CLAVE:
        if request.headers.get("X-Lector-Clave", "") != LECTOR_CLAVE:
            return jsonify({"error": "Lector no autorizado"}), 401

    data = request.get_json(silent=True) or {}
    nfc_id = str(data.get("nfc_id", "")).strip().upper()
    ids_pedidos = data.get("ids_pedidos")

    if not nfc_id:
        return jsonify({"error": "No se recibió un NFC ID"}), 400
    if ids_pedidos is not None:
        try:
            ids_pedidos = [int(i) for i in ids_pedidos]
            if not ids_pedidos:
                return jsonify({"error": "ids_pedidos vacío"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "ids_pedidos no válidos"}), 400

    conexion = None
    cursor = None
    try:
        conexion = connect()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id_empleado, nombre FROM empleados
            WHERE UPPER(nfc_id) = %s
            """,
            (nfc_id,),
        )
        empleado = cursor.fetchone()
        if not empleado:
            registrar_evento_nfc("nfc_no_registrado", nfc_id=nfc_id)
            return jsonify({"error": "NFC no registrado"}), 404

        id_empleado = empleado["id_empleado"]
        if ids_pedidos:
            marcadores = ",".join(["%s"] * len(ids_pedidos))
            cursor.execute(
                f"""
                SELECT id_pedido FROM pedidos
                WHERE id_empleado = %s AND estado = 'pendiente'
                  AND id_pedido IN ({marcadores})
                FOR UPDATE
                """,
                (id_empleado, *ids_pedidos),
            )
            pedidos = cursor.fetchall()
            if len(pedidos) != len(set(ids_pedidos)):
                conexion.rollback()
                return jsonify({
                    "error": "Alguno de los pedidos no existe, no es del "
                             "empleado o ya no está pendiente"
                }), 404
        else:
            cursor.execute(
                """
                SELECT id_pedido FROM pedidos
                WHERE id_empleado = %s AND estado = 'pendiente'
                FOR UPDATE
                """,
                (id_empleado,),
            )
            pedidos = cursor.fetchall()

        if not pedidos:
            registrar_evento_nfc(
                "sin_pedidos", nfc_id=nfc_id,
                id_empleado=id_empleado, detalle={"empleado": empleado["nombre"]},
            )
            return jsonify({
                "error": "El empleado no tiene pedidos pendientes",
                "empleado": empleado["nombre"],
            }), 404

        ids = [p["id_pedido"] for p in pedidos]
        marcadores = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"""
            SELECT c.id_componente, c.nombre, SUM(h.cantidad) AS cantidad
            FROM historial_pedidos h
            INNER JOIN componentes c ON h.id_componente = c.id_componente
            WHERE h.id_pedido IN ({marcadores})
            GROUP BY c.id_componente, c.nombre
            ORDER BY c.nombre
            """,
            tuple(ids),
        )
        componentes = [
            {
                "id_componente": fila["id_componente"],
                "nombre": fila["nombre"],
                "cantidad": int(fila["cantidad"]),
            }
            for fila in cursor.fetchall()
        ]

        faltantes = []
        for componente in componentes:
            restante = componente["cantidad"]
            cursor.execute(
                """
                SELECT id_inventario, cantidad FROM inventario
                WHERE id_componente = %s AND cantidad > 0
                ORDER BY id_inventario
                FOR UPDATE
                """,
                (componente["id_componente"],),
            )
            for fila in cursor.fetchall():
                if restante <= 0:
                    break
                a_descontar = min(restante, fila["cantidad"])
                cursor.execute(
                    """
                    UPDATE inventario
                    SET cantidad = cantidad - %s
                    WHERE id_inventario = %s
                    """,
                    (a_descontar, fila["id_inventario"]),
                )
                restante -= a_descontar
            if restante > 0:
                faltantes.append({
                    "nombre": componente["nombre"],
                    "faltan": restante,
                })

        if faltantes:
            conexion.rollback()
            registrar_evento_nfc(
                "sin_existencias", nfc_id=nfc_id, id_empleado=id_empleado,
                detalle={
                    "empleado": empleado["nombre"],
                    "faltantes": faltantes,
                },
            )
            return jsonify({
                "error": "No hay existencias suficientes",
                "empleado": empleado["nombre"],
                "faltantes": faltantes,
            }), 409

        cursor.execute(
            f"""
            UPDATE pedidos SET estado = 'retirado'
            WHERE id_pedido IN ({marcadores})
            """,
            tuple(ids),
        )
        cursor.execute(
            f"""
            UPDATE historial_pedidos SET recibido = 1
            WHERE id_pedido IN ({marcadores})
            """,
            tuple(ids),
        )
        conexion.commit()

        registrar_evento_nfc(
            "retiro_exitoso", nfc_id=nfc_id, id_empleado=id_empleado,
            detalle={
                "empleado": empleado["nombre"],
                "pedidos_retirados": len(ids),
                "componentes": componentes,
            },
        )
        return jsonify({
            "mensaje": "Retiro realizado correctamente",
            "empleado": empleado["nombre"],
            "pedidos_retirados": len(ids),
            "ids_pedidos": ids,
            "componentes": componentes,
        }), 200
    except Exception as error:
        if conexion:
            conexion.rollback()
        print("ERROR EN RETIRO NFC:", repr(error))
        registrar_evento_nfc("error", nfc_id=nfc_id)
        return jsonify({"error": str(error)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


# ---------- Errores JSON para la API ----------
@app.errorhandler(404)
def no_encontrado(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Ruta no encontrada"}), 404
    return redirect(url_for("login"))


@app.errorhandler(405)
def metodo_no_permitido(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Método no permitido"}), 405
    return redirect(url_for("login"))




@app.route("/cambiar-contrasena")
@pagina_login_requerida
def cambiar_contrasena_pagina():
    return render_template(
        "cambiar-contrasena.html",
        organizacion=ORGANIZACION,
        empleado=empleado_actual(),
    )


@app.route("/api/cambiar-contrasena", methods=["POST"])
@login_requerido
def api_cambiar_contrasena():
    datos = request.get_json(silent=True) or {}
    actual = str(datos.get("actual", ""))
    nueva = str(datos.get("nueva", ""))
    if len(nueva) < 6:
        return jsonify(
            {"error": "La contraseña nueva debe tener al menos 6 caracteres"}
        ), 400
    empleado = empleado_actual()
    conexion = connect()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT contrasena FROM empleados WHERE id_empleado = %s",
            (empleado["id_empleado"],),
        )
        fila = cursor.fetchone()
        if not fila or not verify_password(fila["contrasena"], actual):
            return jsonify({"error": "La contraseña actual no es correcta"}), 401
        cursor.execute(
            "UPDATE empleados SET contrasena = %s WHERE id_empleado = %s",
            (hash_password(nueva), empleado["id_empleado"]),
        )
        conexion.commit()
        return jsonify({"mensaje": "Contraseña actualizada"}), 200
    except mysql.connector.Error as error:
        conexion.rollback()
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conexion.close()


if __name__ == "__main__":
    # Solo para pruebas locales. En el servidor se usa Gunicorn.
    app.run(host="0.0.0.0", port=5000,
            debug=os.environ.get("FLASK_DEBUG", "0") == "1")

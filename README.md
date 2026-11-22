# Sistema de Inventario Tecnológico — Creation Technologies

Sistema de inventario de componentes electrónicos para el taller de la
maquiladora **Creation Technologies** (Hermosillo, Sonora). Los
empleados solicitan componentes desde la página web y los retiran
pasando su tarjeta NFC por el lector; el sistema registra quién se
llevó cada cosa, cuándo y en qué cantidad.

Proyecto final de **Servidores II** (Universidad de Sonora, Ingeniería
en Sistemas de Información). Equipo: Axel Córdova Montiel
(coordinador y automatización), Kevin Yovanni Fajardo Sepulveda
(infraestructura / frontend), Julio César Ju Salido (datos) y Jimmy
Silva Luna (detección NFC).

## Arquitectura

| Servicio | Imagen | Puerto |
|---|---|---|
| `nginx` (proxy inverso) | `nginx:1.28-alpine` | **80** (único expuesto) |
| `app` (Flask + Gunicorn) | imagen propia `inventario-app` | 5000 (interno) |
| `db` (MySQL) | `mysql:8.4` | 3306 (interno) |

Red interna `red_interna`, volumen persistente `datos_mysql` y
`db/init.sql` (se ejecuta solo la primera vez, con el volumen vacío).
El lector NFC corre como servicio aparte (`compose.lector.yaml`).

## Inicio rápido

```bash
cp .env.ejemplo .env        # y cambia las contraseñas dentro de .env
docker compose up -d --build
curl http://localhost/salud    # {"estado": "ok", ...}
```

Usuario inicial: **Jimmy** (CEO, supervisor), contraseña temporal
**Temporal123** (cambiarla al entrar). Tarjeta NFC registrada:
`698A00F4`.

La guía completa paso a paso (Prácticas 11, 12 y 13, despliegue,
respaldo y cierre) está en el documento que acompaña a este ZIP.

## Estructura

```text
inventario/
├── compose.yaml            # nginx, app, db
├── compose.lector.yaml     # servicio opcional del lector NFC
├── Jenkinsfile             # validación automática (Práctica 12)
├── .env.ejemplo            # plantilla de credenciales (copiar a .env)
├── app/
│   ├── app.py              # Flask: inventario, pedidos, NFC, /salud
│   ├── main.py             # lector NFC por puerto serial
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── templates/          # páginas HTML
│   └── static/             # css y js
├── db/
│   └── init.sql            # esquema + catálogo real (195 componentes)
├── nginx/
│   └── default.conf        # proxy inverso a app:5000
└── scripts/
    ├── respaldo.sh         # mysqldump a ~/respaldos (Práctica 13)
    └── restaurar.sh        # restaura un respaldo .sql.gz
```

## Endpoints principales

| Ruta | Qué hace | Rol |
|---|---|---|
| `GET /salud` | Estado del sistema y contadores | público |
| `POST /api/login` | Inicia sesión (nombre + contraseña) | público |
| `GET /inventario` | Catálogo completo con stock | logueado |
| `GET /pedir` | Solicitar componentes | logueado |
| `POST /api/solicitudes` | Crear solicitud | logueado |
| `POST /api/pedidos/<id>/cancelar` | Cancelar un pedido pendiente | dueño o supervisor |
| `GET /api/peticiones` | Pedidos pendientes | supervisor |
| `GET /surtir` y `POST /surtir_componentes` | Agregar stock | supervisor |
| `GET /historial` y `GET /api/historial` | Quién se llevó qué | supervisor |
| `POST /api/retiro-nfc` | Retiro con tarjeta NFC | lector |
| `GET /api/nfc-eventos` | Eventos del lector (persistentes) | logueado |

## Qué se corrigió frente a srv2-proj-main

- Servicios renombrados a `nginx` / `app` / `db` y `db/init.sql` con el
  catálogo real (antes se restauraba un `respaldo.sql` viejo al
  arrancar y los nombres no coincidían con las prácticas).
- `/salud`, `Jenkinsfile`, `.env.ejemplo` y Gunicorn (antes Flask en
  modo desarrollo con `debug=True`).
- Login real con contraseña y sesiones; eliminada la ruta `/empleado`
  que entraba solo con el nombre. Roles supervisor / empleado.
- Los formularios de alta de usuario y componente ya funcionan
  (`/api/empleados`, `/api/componentes`); antes mandaban a vacío.
- Cancelar pedido, vista de historial y alertas de stock mínimo
  (`stock_minimo` en inventario, columna `bajo_stock` en la API).
- `/inventario` con `LEFT JOIN`: los 141 componentes sin fila de
  inventario ya aparecen (cantidad 0) en vez de ser invisibles.
- Componente duplicado eliminado: se conserva `PC817 optoacoplador`
  (id 126, 40 unidades en F2); se eliminó `Optoacoplador PC817`
  (id 195, sin inventario ni historial).
- El lector NFC reintenta la conexión si el puerto falla, acepta UID
  en texto plano o JSON, y corre como servicio aparte; sus eventos se
  guardan en la tabla `eventos_nfc` (antes solo en memoria).
- El retiro NFC puede ser parcial (`ids_pedidos` opcional).
- Contraseñas fuera del código (`.env`) y con hash PBKDF2 en la BD.
- Respaldo corregido: lee credenciales de `.env` y guarda en
  `~/respaldos` fuera del repo (antes fallaba en cron y guardaba
  dentro del proyecto).

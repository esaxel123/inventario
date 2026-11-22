#!/bin/bash
# Respaldo de la base de datos (Practica 13).
# Genera ~/respaldos/inventario_YYYY-MM-DD_HHMM.sql.gz y borra los
# respaldos con mas de 30 dias. Uso:
#   ./scripts/respaldo.sh
# Correccion frente a cmd_respaldo.sh anterior:
# - Lee las credenciales de .env (antes usaba $MYSQL_ROOT_PASSWORD,
#   que en cron normalmente no existe y el respaldo fallaba).
# - Guarda en ~/respaldos (fuera de la carpeta del proyecto) y no
#   dentro del repo.
# - Registra cada ejecucion en ~/respaldos/ejecuciones.log.
set -Eeuo pipefail

# Ir a la raiz del proyecto (donde estan compose.yaml y .env).
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "ERROR: no existe .env (copia .env.ejemplo a .env primero)."
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

CONTENEDOR="inventario_db"
BASE_DATOS="${MYSQL_DATABASE:-inventario_ct}"
CARPETA="$HOME/respaldos"
FECHA=$(date +%Y-%m-%d_%H%M)

mkdir -p "$CARPETA"
exec >> "$CARPETA/ejecuciones.log" 2>&1

echo "-----------------------------------"
echo "Iniciando respaldo: $(date)"

TEMP="$CARPETA/inventario_${FECHA}.sql.gz.tmp"
DESTINO="$CARPETA/inventario_${FECHA}.sql.gz"

trap 'rm -f "$TEMP"' EXIT

if docker exec "$CONTENEDOR" sh -c \
    'exec mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --events --databases "$1"' \
    sh "$BASE_DATOS" | gzip > "$TEMP"; then

    if [ -s "$TEMP" ] && gzip -t "$TEMP"; then
        mv "$TEMP" "$DESTINO"
        echo "Respaldo generado correctamente: $DESTINO"
    else
        echo "ERROR: el respaldo está vacío o dañado."
        exit 1
    fi
else
    echo "ERROR: no se pudo generar el respaldo."
    exit 1
fi

find "$CARPETA" -type f -name 'inventario_*.sql.gz' -mtime +30 -delete

echo "Proceso finalizado: $(date)"

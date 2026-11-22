#!/bin/bash
# Restaura la base de datos desde un respaldo .sql.gz (Practica 13).
# Uso:
#   ./scripts/restaurar.sh ~/respaldos/inventario_2026-11-21_0930.sql.gz
# La base de datos se restaura al momento exacto del respaldo.
set -Eeuo pipefail

cd "$(dirname "$0")/.."

if [ $# -ne 1 ]; then
    echo "Uso: $0 <respaldo.sql.gz>"
    exit 1
fi

RESPALDO="$1"

if [ ! -f .env ]; then
    echo "ERROR: no existe .env."
    exit 1
fi
if [ ! -f "$RESPALDO" ]; then
    echo "ERROR: no existe el respaldo: $RESPALDO"
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

CONTENEDOR="inventario_db"

echo "Restaurando $RESPALDO en la base ${MYSQL_DATABASE:-inventario_ct}..."
gzip -dc "$RESPALDO" | docker exec -i "$CONTENEDOR" sh -c \
    'exec mysql -u root -p"$MYSQL_ROOT_PASSWORD"'
echo "Restauración terminada. Verifica en el navegador."

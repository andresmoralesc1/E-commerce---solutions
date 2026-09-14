#!/usr/bin/env bash
# Disaster Recovery — restaurar Postgres desde un backup
#
# Uso:
#   bash deploy/restore-postgres.sh backups/postgres/brain-20260101-030000.sql.gz
#
# ⚠️  ESTE SCRIPT SOBREESCRIBE LA BASE DE DATOS. Confirmación requerida.

set -euo pipefail

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
    echo "Uso: $0 <archivo-backup.sql.gz>"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "❌ No existe: $BACKUP_FILE"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
POSTGRES_USER=$(grep ^POSTGRES_USER "$ENV_FILE" | cut -d= -f2)
POSTGRES_DB=$(grep ^POSTGRES_DB "$ENV_FILE" | cut -d= -f2)

echo "⚠️  RESTAURAR $BACKUP_FILE EN $POSTGRES_DB"
echo "   Esto BORRARÁ todos los datos actuales y los reemplazará con el backup."
read -p "Escribe 'RESTAURAR' para confirmar: " confirm
if [[ "$confirm" != "RESTAURAR" ]]; then
    echo "Cancelado."
    exit 0
fi

# Hacer dump del estado actual por si acaso
SAFETY_DUMP="pre-restore-$(date +%Y%m%d-%H%M%S).sql.gz"
echo "💾 Backup de seguridad del estado actual: $SAFETY_DUMP"
docker exec ecommerce-brain-postgres-1 pg_dump \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges -Fc | \
    gzip > "$BACKUP_FILE.safety.sql.gz" || true

# Drop schema y recrear
echo "🗑️  Eliminando schema public…"
docker exec ecommerce-brain-postgres-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO $POSTGRES_USER;
"

# Restaurar
echo "📥 Restaurando desde $BACKUP_FILE…"
gunzip -c "$BACKUP_FILE" | docker exec -i ecommerce-brain-postgres-1 pg_restore \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges

# Refresh vista materializada
echo "🔄 Refrescando vista materializada…"
docker exec ecommerce-brain-postgres-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "REFRESH MATERIALIZED VIEW profitability_mv;"

echo "✅ Restauración completa. Verifica con: docker compose logs backend"
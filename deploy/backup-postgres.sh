#!/usr/bin/env bash
# Backup diario de Postgres (Ecommerce Brain) + uploads a S3-compatible (opcional).
#
# Cron sugerido (todos los días a las 3am):
#   0 3 * * * /home/telchar/projects/ecommerce-brain/deploy/backup-postgres.sh >> /var/log/brain-backup.log 2>&1
#
# Configuración via .env o vars:
#   BACKUP_DIR    — donde guardar dumps (default: ./backups/postgres)
#   BACKUP_KEEP   — cuántos backups mantener (default: 14)
#   BACKUP_S3_BUCKET, BACKUP_S3_ENDPOINT, BACKUP_S3_ACCESS_KEY, BACKUP_S3_SECRET_KEY
#                   — si están definidos, sube a S3-compatible (rclone o aws-cli)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$HOME/ecommerce-brain/backups/postgres}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Postgres connection — leer de .env del proyecto
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    POSTGRES_USER=$(grep ^POSTGRES_USER "$ENV_FILE" | cut -d= -f2)
    POSTGRES_DB=$(grep ^POSTGRES_DB "$ENV_FILE" | cut -d= -f2)
    # POSTGRES_PASSWORD no es necesario porque el contenedor postgres acepta
    # conexiones locales sin password (auth trust) desde host
    BACKUP_HOST="${BACKUP_HOST:-localhost}"
    BACKUP_PORT="${BACKUP_PORT:-5435}"
fi

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/brain-${TIMESTAMP}.sql.gz"

echo "[$(date +%Y-%m-%dT%H:%M:%S)] Backup a $BACKUP_FILE…"

# pg_dump con custom format (-Fc) comprimido
docker exec ecommerce-brain-postgres-1 pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-owner \
    --no-privileges \
    -Fc | gzip > "$BACKUP_FILE"

size=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup OK: $BACKUP_FILE ($size)"

# Rotation: borrar backups más viejos que $BACKUP_KEEP
echo "[$(date)] Rotando backups (mantener últimos $BACKUP_KEEP)…"
ls -1t "$BACKUP_DIR"/brain-*.sql.gz | tail -n +$((BACKUP_KEEP + 1)) | xargs -r rm -f

# Subir a S3 si está configurado
if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
    echo "[$(date)] Subiendo a S3: s3://$BACKUP_S3_BUCKET/brain-backups/$TIMESTAMP.sql.gz"
    if command -v aws >/dev/null 2>&1; then
        AWS_ACCESS_KEY_ID="$BACKUP_S3_ACCESS_KEY" \
        AWS_SECRET_ACCESS_KEY="$BACKUP_S3_SECRET_KEY" \
        aws s3 cp "$BACKUP_FILE" \
            "s3://$BACKUP_S3_BUCKET/brain-backups/" \
            --endpoint-url "${BACKUP_S3_ENDPOINT:-}" \
            --storage-class STANDARD_IA
    elif command -v rclone >/dev/null 2>&1; then
        rclone copy "$BACKUP_FILE" "remote:brain-backups/" 2>/dev/null || true
    else
        echo "⚠️  aws o rclone no instalado; no se sube a S3"
    fi
fi

echo "[$(date)] ✅ Backup completo."
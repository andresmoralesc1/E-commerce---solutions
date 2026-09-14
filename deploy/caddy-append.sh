#!/usr/bin/env bash
# Añade vhosts de Ecommerce Brain al Caddyfile existente sin pisar nada.
#
# ESTRATEGIA:
# 1. Backup automático del Caddyfile actual
# 2. Append de un bloque marcado
# 3. caddy validate
# 4. systemctl reload caddy (solo si validate ok)
#
# NO TOCAR si el subdominio ya existe en Caddyfile.

set -euo pipefail

CADDY_FILE="/etc/caddy/Caddyfile"
SNIPPET_FILE="$(dirname "$0")/Caddyfile.snippet"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}Debes correr con sudo.${NC}"
  exit 1
fi

if [[ ! -f $SNIPPET_FILE ]]; then
  echo -e "${RED}No existe $SNIPPET_FILE${NC}"
  exit 1
fi

echo -e "${YELLOW}🔍 Verificando subdominios no duplicados…${NC}"

DUPLICATES=0
for HOST in dashboard.ecommerce.andresmorales.com.co api.ecommerce.andresmorales.com.co flows.ecommerce.andresmorales.com.co wa.ecommerce.andresmorales.com.co; do
  if grep -q "^${HOST//./\\.}\b\|^${HOST}\b" "$CADDY_FILE"; then
    echo -e "  ${RED}✗${NC} $HOST ya existe en Caddyfile"
    DUPLICATES=$((DUPLICATES + 1))
  else
    echo -e "  ${GREEN}✓${NC} $HOST libre"
  fi
done

if [[ $DUPLICATES -gt 0 ]]; then
  echo -e "${RED}Hay $DUPLICATES duplicados. Aborta.${NC}"
  exit 1
fi

BACKUP="${CADDY_FILE}.bak.pre-ecommerce-brain.$(date +%s)"
cp "$CADDY_FILE" "$BACKUP"
echo -e "${GREEN}💾 Backup: $BACKUP${NC}"

{
  echo ""
  echo "# ─── Ecommerce Brain (added $(date +%Y-%m-%d)) ───"
  cat "$SNIPPET_FILE"
} >> "$CADDY_FILE"

echo -e "${YELLOW}🔍 Validando…${NC}"
if caddy validate --config "$CADDY_FILE"; then
  echo -e "${GREEN}✓ Valid OK${NC}"
  systemctl reload caddy
  echo -e "${GREEN}✓ Caddy recargado${NC}"
else
  echo -e "${RED}✗ Valid falló. Revirtiendo…${NC}"
  cp "$BACKUP" "$CADDY_FILE"
  exit 1
fi

echo -e "${GREEN}✅ Listo.${NC}"
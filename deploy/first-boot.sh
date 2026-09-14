#!/usr/bin/env bash
# First-boot install: clona repo + levanta servicios
# Uso:  curl -sSL <url>/first-boot.sh | bash
set -euo pipefail

REPO_URL="https://github.com/andresmoralesc1/E-commerce---solutions.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/ecommerce-brain}"

echo "📦 Clonando repo en $INSTALL_DIR…"
if [[ -d $INSTALL_DIR ]]; then
  cd "$INSTALL_DIR"
  git pull --rebase
else
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

echo "📝 Creando .env desde .env.example…"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "⚠️  Edita .env y rellena MINIMAX_API_KEY + passwords antes de continuar"
  exit 0
fi

echo "🐳 Levantando servicios…"
docker compose up -d --build

echo "⏳ Esperando healthchecks…"
sleep 10
docker compose ps

echo "✅ Listo. Crea tu primer admin:"
echo "  curl -X POST http://localhost:8040/api/auth/bootstrap \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"email\":\"tu@correo.com\",\"password\":\"minimo-12-chars\"}'"
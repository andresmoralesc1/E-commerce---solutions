# 🔥 Disaster Recovery Runbook

## Escenarios y respuestas

### 1. Backend no responde

**Síntomas**: `curl http://localhost:8040/health` falla o timeout.

```bash
# Estado
docker compose ps
docker compose logs --tail 50 backend

# Reiniciar limpio
docker compose restart backend
sleep 10
curl http://localhost:8040/health

# Si persiste, ver stack trace
docker compose logs backend | grep -A 20 "Traceback"

# Si DB no responde
docker compose logs postgres | tail -20
docker compose restart postgres
sleep 5
docker compose restart backend
```

### 2. Postgres caído (data corrupta o caída de hardware)

```bash
# ¿Cuál es el problema?
docker compose logs postgres --tail 30

# Si el disco está lleno
docker system df
docker volume ls
docker system prune -a          # ⚠️ borra imágenes/volúmenes huérfanos

# Restaurar desde backup
ls -lt backups/postgres/
bash deploy/restore-postgres.sh backups/postgres/brain-20260101-030000.sql.gz

# Verificar
curl http://localhost:8040/api/dashboard/kpis
```

### 3. Disco lleno

```bash
# ¿Quién come espacio?
df -h
du -sh /var/lib/docker/*
docker system df

# Limpiar (con cuidado)
docker system prune          # seguro
docker system prune -a       # ⚠️ borra imágenes no usadas

# Si los logs son el problema:
truncate -s 0 $(docker inspect --format='{{.LogPath}}' $(docker ps -q))
```

### 4. Caddy no emite certificados TLS

```bash
# Estado
systemctl status caddy
journalctl -u caddy --since "10 min ago"

# Si dice "lock error" → esperar 30s
# Si dice "rate limit" → usar Caddy staging
sudo caddy stop
sudo caddy start --config /etc/caddy/Caddyfile

# Force renewal
sudo caddy reload --force
```

### 5. Evolution API desconectado de WhatsApp

```bash
# Estado
curl -s http://localhost:8088/instance/connectionState/brain \
  -H "apikey: $(grep ^EVOLUTION_API_KEY .env | cut -d= -f2)" | jq .

# Reconectar (borrar + crear)
curl -X DELETE http://localhost:8088/instance/delete/brain \
  -H "apikey: $(grep ^EVOLUTION_API_KEY .env | cut -d= -f2)"

curl -X POST http://localhost:8088/instance/create \
  -H "apikey: $(grep ^EVOLUTION_API_KEY .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"instanceName":"brain","qrcode":true,"integration":"WHATSAPP-BAILEYS"}'
```

Escanear el nuevo QR con WhatsApp.

### 6. n8n existente dejó de ejecutar workflows

```bash
# Verificar
docker ps | grep telchar-n8n
docker logs telchar-n8n-1 --tail 30

# Reiniciar (NO destruye workflows)
docker restart telchar-n8n-1
sleep 30

# Reimportar nuestros workflows
# (subir manualmente en la UI de n8n los 7 .json de /n8n-workflows/)
```

### 7. DNS de subdominios dejó de funcionar

```bash
# Verificar
dig dashboard.ecommerce.andresmorales.com.co +short
dig @8.8.8.8 dashboard.ecommerce.andresmorales.com.co

# Si no resuelve → revisar Namecheap
# ¿Sigues con Namecheap nameservers?
dig andresmorales.com.co NS

# Si migraste fuera, los subdominios no se pueden gestionar vía API.
# Plan B: crear registros en el nuevo provider manualmente apuntando a:
#   dashboard.ecommerce  A  38.242.194.196
#   api.ecommerce        A  38.242.194.196
#   flows.ecommerce      A  38.242.194.196
#   wa.ecommerce         A  38.242.194.196
```

### 8. Pérdida de credenciales Meta/Google OAuth

Re-correr OAuth:
- Meta:    https://api.ecommerce.andresmorales.com.co/api/auth/meta/start?tenant_id=X
- Google:  https://api.ecommerce.andresmorales.com.co/api/auth/google/start?tenant_id=X

(O via `localhost:8040` en dev).

### 9. Migrar de un VPS a otro

```bash
# En el VPS viejo
bash deploy/backup-postgres.sh
ls -lt backups/postgres/

# Transferir
scp -r backups/postgres/ user@nuevo-vps:/tmp/

# En el VPS nuevo
cd /home/telchar/projects/ecommerce-brain
docker compose up -d postgres
sleep 10
bash deploy/restore-postgres.sh /tmp/brain-XXXXXX.sql.gz

# Verificar
docker compose up -d backend frontend
curl http://localhost:8040/health
```

### 10. Actualización del sistema (deploy nuevo)

```bash
cd /home/telchar/projects/ecommerce-brain
git pull

# Backup siempre antes
bash deploy/backup-postgres.sh

# Pull nuevas imágenes + restart
docker compose pull
docker compose up -d --build

# Si falla, rollback
git checkout HEAD~1
docker compose up -d --build
```

## 🛡️ Prevención

| Acción | Frecuencia | Comando |
|---|---|---|
| Backup Postgres | Diario 3am | cron con `backup-postgres.sh` |
| Rotación de backups | Auto | 14 días (default) |
| Restart servicios | Mensual | `docker compose restart` |
| Verificar TLS certs | Mensual | `caddy list-certs` |
| Refrescar materialized view | Cada 30min | cron en n8n workflow 05 |
| Limpiar Docker | Mensual | `docker system prune` |
| Auditar credenciales | Trimestral | `lastpass`, etc |
| Test restore | Trimestral | `bash deploy/restore-postgres.sh` en staging |

## 📞 Contactos y claves

Guarda esta info FUERA del repo:
- ANTHROPIC / MiniMax / OpenAI API keys
- Meta App ID + Secret + Ad Account ID
- Google OAuth client_id/secret + Developer Token
- WhatsApp number + PIN WhatsApp Business
- Namecheap API key + IP whitelist
- Shopify Partner API token
- Evolution API key
- PostgreSQL password
- JWT_SECRET

## 🚨 Contactos emergencia

- Namecheap support: https://www.namecheap.com/support/
- Meta Business Help: https://business.facebook.com/business/help
- Google Ads Support: https://support.google.com/google-ads
- WhatsApp Business API: https://business.whatsapp.com/
- Evolution API GitHub: https://github.com/EvolutionAPI/evolution-api
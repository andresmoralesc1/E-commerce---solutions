# Evolution API (WhatsApp)

## 1. Levantar el contenedor

```bash
# Asegúrate de que .env tenga EVOLUTION_API_KEY
EVOLUTION_KEY=$(grep ^EVOLUTION_API_KEY /home/telchar/projects/ecommerce-brain/.env | cut -d= -f2)

docker compose --profile phase4 up -d evolution evolution-db
sleep 10

# Verificar
curl http://localhost:8088/ | head -3
```

## 2. Crear instancia + escanear QR

```bash
# Crear instancia "brain" y obtener QR
curl -s -X POST http://localhost:8088/instance/create \
  -H "apikey: $EVOLUTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "brain",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
  }'
```

La respuesta trae un `qrcode.base64` con un PNG del QR. Mostrarlo al usuario
para que lo escanee con WhatsApp Business (o el WhatsApp personal).

```bash
# Decodificar el QR y guardarlo como PNG
curl -s -X POST http://localhost:8088/instance/create \
  -H "apikey: $EVOLUTION_KEY" -H "Content-Type: application/json" \
  -d '{"instanceName":"brain","qrcode":true,"integration":"WHATSAPP-BAILEYS"}' \
  | python3 -c "import json, sys, base64; d = json.load(sys.stdin); \
    open('qr.png','wb').write(base64.b64decode(d['qrcode']['base64'].split(',')[1]))"

# Ver QR como imagen
xdg-open qr.png   # o cualquier visor
```

## 3. Configurar manager_phone del tenant

Evolution necesita saber a qué número enviar. Esto se guarda en el tenant:

```bash
docker exec ecommerce-brain-postgres-1 psql -U brain -d brain -c "
UPDATE tenants SET settings = settings ||
  '{\"manager_phone\":\"+573001234567\",\"evolution_instance\":\"brain\"}'::jsonb
WHERE id = '9a6f1db5-cb0a-408d-807c-4157a4f10255';
"
```

> ⚠️ El formato es E.164: `+[código país][número]`. Ej: +573001234567 (Colombia).

## 4. Verificar conexión

```bash
curl http://localhost:8040/api/whatsapp/evolution/status
```

Debe decir `"evolution": "up"`. Si dice "down", Evolution no responde — revisa:
- `docker compose logs evolution`
- `EVOLUTION_API_KEY` en .env del backend coincide con el del container

```bash
# Estado de la instancia (conectada sí/no)
curl -s -H "apikey: $EVOLUTION_KEY" \
  http://localhost:8088/instance/connectionState/brain | python3 -m json.tool
```

## 5. Webhook Evolution → backend

Cuando llega un mensaje WhatsApp, Evolution hace POST a:

```
http://host.docker.internal:8040/api/webhooks/evolution
```

(dentro de docker-compose usamos `host.docker.internal:8040` para hablar al backend
desde Evolution).

**IMPORTANTE**: Evolution está dentro del docker network, así que `host.docker.internal`
solo funciona si el flag `extra_hosts: host.docker.internal:host-gateway` está puesto
en el backend (ya está). Si el envío falla, revisa logs de Evolution.

## 6. Probar el loop end-to-end

Una vez WhatsApp escaneado:

```bash
TOKEN=$(curl -s -X POST http://localhost:8040/api/auth/login \
  -d "username=admin@andresmorales.com.co&password=admin12345xyz" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# a) Ver el reporte sin enviar (dry-run)
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8040/api/reports/morning/dry-run | python3 -m json.tool

# b) Generar pending + enviar WhatsApp real
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8040/api/reports/morning
```

Vas a recibir un WhatsApp como:
```
🚨 GOR-BAS-01 lleva 3 días a pérdida (-56.6%) con $64529 en ads.
¿Pauso la campaña? Responde SI para ejecutar.
```

Responder `SI` desde el teléfono. El backend:
1. Recibe webhook Evolution
2. Encuentra pending_action del tenant
3. Ejecuta Meta/Google SDK real
4. Registra en audit con `actor=whatsapp:+573001234567`

## 7. Trigger automático 8am (cron)

Workflow n8n: `n8n-workflows/06-morning-whatsapp-8am.json`

Importar en n8n existente (`telchar-n8n-1:5678`) y activar. Cron `0 8 * * *`.

## 8. Troubleshooting

| Problema | Solución |
|---|---|
| Evolution dice "Unauthorized" | EVOLUTION_API_KEY del backend ≠ container. Reiniciar: `docker compose --profile phase4 up -d --force-recreate evolution` |
| QR no aparece | Borrar instancia: `curl -X DELETE -H "apikey: $EVOLUTION_KEY" http://localhost:8088/instance/delete/brain` y crear de nuevo |
| Mensaje llega pero backend no procesa | Ver `docker compose logs backend \| grep evolution` |
| WhatsApp no se desconecta | WhatsApp tiene límite de 1 conexión Baileys por número. Si conectas desde otro lugar, se cae aquí |

## ⚠️ Importante
- WhatsApp **no permite** envío masivo no solicitado. Solo enviar a números
- que han iniciado la conversación o son clientes reales.
- Para producción considera WhatsApp Cloud API (Meta) en lugar de Baileys
- (que es unofficial y Meta puede banear).
- Evolution API es un wrapper que soporta ambos backends.
# Evolution API (WhatsApp)

## 1. Levantar el contenedor

```bash
docker compose --profile phase4 up -d evolution
```

Queda expuesto en `http://localhost:8088`.

## 2. Crear instancia

```bash
curl -X POST http://localhost:8088/instance/create \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "brain",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
  }'
```

Responde con un QR. Escanéalo con tu WhatsApp Business.

## 3. Configurar webhook

Apunta el webhook global al endpoint del backend:
```
EVOLUTION_WEBHOOK_URL=https://tu-dominio/api/webhooks/evolution
```

El backend procesa los mensajes entrantes y, cuando recibe `SI`/`NO`
en respuesta a una acción pendiente, llama a `/api/agent/confirm/{action_id}`.

## 4. Enviar reporte diario (Fase 4)

El workflow `06-morning-report.json` (en `/n8n-workflows/`) corre a las 8am
y postea al backend:
```
POST /api/reports/morning
  { "tenant_id": "...", "phone": "+57..." }
```

El backend:
1. Recolecta SKUs en `A_PERDIDA` con `ad_spend_3d > 20`
2. Llama `/agent/decide` para cada uno
3. Inserta en `pending_actions`
4. Envía cada `whatsapp_message` por Evolution

## 5. Multi-tenant

Cada tenant tiene `settings.whatsapp_phone` y `settings.manager_phone` en la
tabla `tenants`. Los reportes se enrutan al manager configurado.

## ⚠️ Importante
- WhatsApp **no permite** envío masivo no solicitado. Solo enviar a números
  que han iniciado la conversación o son clientes reales.
- Para producción considera WhatsApp Cloud API (Meta) en lugar de Baileys
  (que es unofficial y Meta puede banear).
- Evolution API es un wrapper que soporta ambos backends.
# Shopify — guía de conexión

## 1. Crear app privada (Custom App)

1. Tu tienda Shopify → **Settings → Apps and sales channels → Develop apps**
2. **Create an app** → nombre "Ecommerce Brain"
3. **Configure Admin API scopes**:
   - `read_orders`
   - `read_products`
   - `read_inventory`
   - `read_fulfillments`
   - `read_returns`
   - `read_shipping`
   - `read_analytics`
4. **Install app** → copiar **Admin API access token** (empieza por `shpat_`)

## 2. Registrar el tenant

Vía API:
```bash
TOKEN=$(curl -s -X POST http://localhost:8040/api/auth/login \
  -d "username=tu@correo.com&password=tu-password" | jq -r .access_token)

curl -X POST http://localhost:8040/api/tenants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mi Tienda",
    "source": "shopify",
    "credentials": {
      "shop_domain": "mi-tienda.myshopify.com",
      "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    },
    "settings": {"currency": "COP"}
  }'
```

## 3. Sync manual (Fase 1)
```bash
curl -X POST http://localhost:8040/api/sync/shopify/{tenant_id}/now \
  -H "Authorization: Bearer $TOKEN"
```

## 4. Webhook (Fase 2)

Shopify → Settings → Notifications → Webhooks:
- Event: **Order creation**
- URL: `https://tu-dominio/api/webhooks/shopify/orders`
- Format: JSON

## 5. Costes de producto (COGS)

Si tu tienda no tiene COGS en los productos, puedes cargarlos manualmente:
```bash
curl -X POST http://localhost:8040/api/products/{sku}/cost \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"cost": 12500.00}'
```

O importar vía CSV desde el dashboard (próxima iteración).

## Troubleshooting
- **401 al sync**: el access token expiró (rotación 24h en algunas apps).
- **429 rate limit**: Shopify limita ~2 req/s. El conector ya pagina con cursor.
- **Productos sin SKU**: el sistema crea `SHOPIFY-{line_item_id}` como fallback. Configura SKUs reales en Shopify.
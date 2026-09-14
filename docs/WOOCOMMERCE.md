# WooCommerce — guía de conexión

## 1. Generar REST API credentials

1. WP Admin → **WooCommerce → Settings → Advanced → REST API**
2. **Add key**:
   - Description: "Ecommerce Brain"
   - User: tu usuario admin
   - Permissions: **Read**
3. Copia **Consumer Key** (`ck_xxxxx`) y **Consumer Secret** (`cs_xxxxx`)

## 2. Registrar el tenant

```bash
curl -X POST http://localhost:8040/api/tenants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mi Tienda WC",
    "source": "woocommerce",
    "credentials": {
      "site_url": "https://mitienda.com",
      "consumer_key": "ck_xxxxx",
      "consumer_secret": "cs_xxxxx"
    }
  }'
```

## 3. Sync manual

```bash
curl -X POST http://localhost:8040/api/sync/woocommerce/{tenant_id}/now \
  -H "Authorization: Bearer $TOKEN"
```

## 4. Webhook (Fase 2)

WP Admin → WooCommerce → Settings → Advanced → Webhooks:
- Topic: **Order created**
- Delivery URL: `https://tu-dominio/api/webhooks/woocommerce/orders`

## Troubleshooting
- **401 Unauthorized**: el sitio debe tener **pretty permalinks** activos.
- **SSL issues en localhost**: el conector usa HTTPS. Para dev local necesitas un tunnel o desactivar verificación SSL (no recomendado en prod).
- **Productos sin SKU**: fallback `WOO-{product_id}`. Configura SKUs en cada producto.
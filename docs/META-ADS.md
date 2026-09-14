# Meta Marketing API (Facebook + Instagram Ads)

## 1. Crear Meta App

1. https://developers.facebook.com/apps → **Create App** → tipo **Business**
2. Add product: **Marketing API**
3. Settings → Basic → copiar **App ID** y **App Secret**

## 2. Configurar OAuth

En `app/.env`:
```
META_APP_ID=...
META_APP_SECRET=...
META_REDIRECT_URI=https://tu-dominio/api/auth/meta/callback
```

## 3. Autorizar cuenta de anuncios

Necesitas los scopes:
- `ads_read`
- `ads_management`
- `business_management`

Flujo OAuth (Fase 3):
```
GET https://www.facebook.com/v21.0/dialog/oauth?client_id=...&redirect_uri=...&scope=ads_read,ads_management,business_management
```

## 4. Atribución por SKU

Para que el sistema atribuya el gasto al SKU correcto, los anuncios deben
tener en su URL final el parámetro:
```
?utm_source=meta&utm_medium=cpc&utm_campaign=fall_2026&utm_content=SKU-12345
```

`utm_content` = tu SKU. Si no hay UTMs, el sistema distribuye el gasto
proporcionalmente al revenue por SKU en el periodo.

## 5. Account ID

Lo encuentras en **Ads Manager → Account Settings → Account ID**
(tiene formato `act_1234567890`).

## Fase 3 — implementación pendiente
El endpoint `meta_ads.fetch_ad_spend` está como stub. La implementación real:
- Llama `/act_{id}/insights` con breakdowns por UTM content
- Paginación con `paging.next`
- Guarda cada fila en `ad_spend` con `attribution_method='utm'`

Refs:
- https://developers.facebook.com/docs/marketing-apis
- https://developers.facebook.com/docs/marketing-api/insights
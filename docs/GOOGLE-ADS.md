# Google Ads API

## 1. Crear proyecto en Google Cloud

1. https://console.cloud.google.com → nuevo proyecto
2. Habilita **Google Ads API** (Marketplace)
3. Crea OAuth 2.0 credentials (Web application):
   - Authorized redirect URI: `https://tu-dominio/api/auth/google/callback`

## 2. Solicitar Developer Token

1. https://ads.google.com/aw/apicenter → **Apply for production access**
2. Empieza con **test account** si solo quieres probar
3. Copia el **Developer Token**

## 3. Configurar `.env`

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_DEVELOPER_TOKEN=...
GOOGLE_REDIRECT_URI=https://tu-dominio/api/auth/google/callback
```

## 4. Atribución por SKU

Google Ads tiene **custom parameters** que llegan como UTMs en el sitio:
```
https://mitienda.com/producto?utm_source=google&utm_medium=cpc&utm_content=SKU-12345
```

Para configurar custom params:
- Google Ads → Ads & extensions → Ads → [tu anuncio] → "Final URL" → **Ad parameters**
- O usa ValueTrack: `{_sku}` en la URL final

## Fase 3 — implementación pendiente

El endpoint `google_ads.fetch_ad_spend` está como stub. La implementación real:
- Llama `GoogleAdsService.search` con query GAQL filtrando por segments.date
- Atribución por `segments.creative_id → utm_content` (vía join con URLs)
- Guarda en `ad_spend` con `attribution_method='utm'`

Refs:
- https://developers.google.com/google-ads/api/docs/start
- https://developers.google.com/google-ads/api/docs/query/overview
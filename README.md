# 🧠 Ecommerce Brain

Brain de IA para ecommerces: calcula el **margen neto real por SKU** y toma
decisiones automáticas de pricing/ads con aprobación humana por WhatsApp.

- Multi-tenant (Shopify + WooCommerce desde día 1)
- LLM agnóstico (MiniMax, Anthropic, OpenAI)
- FastAPI + Postgres + Next.js 15 + n8n (existente) + Evolution API (fase 4)
- Bilingüe es/en
- 100% self-hosted en VPS con Docker

---

## ⚡ Setup en 10 minutos

### Prerrequisitos
- VPS con Ubuntu 24.04
- Docker + Compose v2
- Puertos libres: 3040 (frontend), 5433 (postgres), 8040 (backend), 8088 (evolution-fase4)

### 1. Clonar y configurar
```bash
git clone https://github.com/andresmoralesc1/E-commerce---solutions.git ecommerce-brain
cd ecommerce-brain
cp .env.example .env
```

Edita `.env` y rellena al menos:
```
POSTGRES_PASSWORD=<algo fuerte>
JWT_SECRET=<openssl rand -hex 32>
MINIMAX_API_KEY=<tu-api-key>
```

### 2. Levantar todo
```bash
docker compose up -d --build
```

Verifica:
```bash
docker compose ps              # todos healthy
curl http://localhost:8040/health
curl http://localhost:3040/api/health
```

### 3. Crear el primer admin (bootstrap)
```bash
curl -X POST http://localhost:8040/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@correo.com","password":"minimo-12-caracteres","full_name":"Andres"}'
```

Solo funciona si la tabla `users` está vacía.

### 4. Login en el dashboard
Abre `http://localhost:3040/es/login` y entra.

### 5. (Opcional) Compartir con URL pública temporal
```bash
docker compose --profile share up -d cloudflared
docker compose logs cloudflared | grep -oE "https://[a-z0-9-]+\.trycloudflare\.com"
```
Tendrás una URL tipo `https://xxxx.trycloudflare.com` que apunta al frontend.

---

## 📁 Estructura
```
ecommerce-brain/
├── docker-compose.yml       5 servicios (sin n8n — usa el existente)
├── Caddyfile.snippet        bloque a añadir a /etc/caddy/Caddyfile cuando vayas a producción
├── .env.example             todas las variables documentadas
├── db/init.sql              schema multi-tenant + vista materializada
├── backend/                 FastAPI 0.115 + asyncpg + structlog
│   └── app/
│       ├── core/            config, db, security, llm_providers
│       ├── routers/         auth, tenants, dashboard, agent
│       ├── services/        profitability, classifier, agent_decision, attribution, ads_executor
│       └── connectors/      shopify, woocommerce, meta_ads, google_ads
├── frontend/                Next.js 15 App Router + next-intl + SWR + Tailwind
│   ├── app/[locale]/        páginas bilingües es/en
│   ├── components/          KPICards, ProfitabilityTable, SemaphoreBadge, ApproveButton, NavBar
│   ├── lib/                 api, auth, types
│   └── messages/{es,en}.json
├── n8n-workflows/           workflows exportables JSON (sync orders, refresh, report 8am, whatsapp)
├── docs/                    SHOPIFY.md, WOOCOMMERCE.md, META-ADS.md, GOOGLE-ADS.md, EVOLUTION.md
└── deploy/
    ├── first-boot.sh        instalación automatizada
    ├── caddy-append.sh      añade vhosts a /etc/caddy/Caddyfile sin pisar nada
    └── namecheap-dns-sync.py ⚠️ script SEGURO para DNS (whitelist de hosts críticos)
```

---

## 🔌 Conectores

| Plataforma | Estado | Doc |
|---|---|---|
| Shopify Admin API (GraphQL) | ✅ Scaffold | `docs/SHOPIFY.md` |
| WooCommerce REST v3 | ✅ Scaffold | `docs/WOOCOMMERCE.md` |
| Meta Marketing API | 🟡 Stub (Fase 3) | `docs/META-ADS.md` |
| Google Ads API | 🟡 Stub (Fase 3) | `docs/GOOGLE-ADS.md` |
| Evolution API (WhatsApp) | 🟡 Compose ready (Fase 4) | `docs/EVOLUTION.md` |
| n8n existente | ✅ Vía REST API | Workflows en `/n8n-workflows/` |

---

## 🚦 Fases

- **Fase 1 (este repo)**: cimientos. Auth JWT, schema, vista, dashboard vacío.
- **Fase 2**: sync real Shopify/Wo, datos sintéticos, ads stub.
- **Fase 3**: Meta/Google SDK + agente ejecutando acciones reales (con confirmación).
- **Fase 4**: Evolution API + WhatsApp + reporte diario 8am.
- **DNS Prod**: ejecutar `deploy/namecheap-dns-sync.py` cuando esté estable.

---

## ⚠️ Importante — DNS Namecheap

**NO** ejecutes `deploy/namecheap-dns-sync.py` hasta que el sistema esté probado.
El script usa estrategia "GET → Mutate → SET atómico" con whitelist de hosts
críticos para no pisar MX/SPF/DKIM del mailcow ni los 14 vhosts existentes.

Dry-run disponible:
```bash
python deploy/namecheap-dns-sync.py --dry-run
```

---

## 📚 Más
- `docs/` — guías paso-a-paso por integración
- `n8n-workflows/` — workflows exportables para importar en n8n
- `deploy/` — scripts de instalación + DNS seguro

Hecho con ☕ en Colombia.
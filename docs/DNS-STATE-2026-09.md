# Estado DNS — 14 Sep 2026

## Resumen

- **Dominio**: `andresmorales.com.co`
- **Nameservers**: `dns1.registrar-servers.com` / `dns2.registrar-servers.com` (FreeDNS default, **sin cambios**)
- **Records totales**: 24 vía API Namecheap

## Records actuales (24)

### A records (18)
```
www                  → 38.242.194.196
mail                 → 38.242.194.196
shop                 → 38.242.194.196
dash                 → 38.242.194.196
crm                  → 38.242.194.196
opencode             → 38.242.194.196
code                 → 38.242.194.196
rin                  → 38.242.194.196
temptum              → 38.242.194.196
producto             → 38.242.194.196
gato                 → 38.242.194.196
products             → 38.242.194.196
hermes               → 38.242.194.196
dgaraje              → 38.242.194.196
ecommerce.dashboard  → 38.242.194.196   ← NUEVO
ecommerce.api        → 38.242.194.196   ← NUEVO
ecommerce.flows      → 38.242.194.196   ← NUEVO
ecommerce.wa         → 38.242.194.196   ← NUEVO
```

### CNAMEs (3) — mailcow
```
autodiscover  → mail.andresmorales.com.co.
autoconfig    → mail.andresmorales.com.co.
mta-sts       → mail.andresmorales.com.co.
```

### MX (1)
```
@ → mail.andresmorales.com.co.  (priority 10)
```

### TXT (2) — root
```
@ → "v=spf1 ip4:38.242.194.196 include:spf.brevo.com -all"
@ → "brevo-code:7788264cb0cef0291f7c71794ca03cc8"
```

## Caddy vhosts añadidos

En `/etc/caddy/Caddyfile` se añadió un vhost wildcard con cert autofirmado:
```
*.ecommerce.andresmorales.com.co {
    tls /etc/caddy/certs/ecommerce/cert.pem /etc/caddy/certs/ecommerce/key.pem
    @dashboard → reverse_proxy 127.0.0.1:3040
    @api       → reverse_proxy 127.0.0.1:8040
    @flows     → reverse_proxy 127.0.0.1:5678
    @wa        → reverse_proxy 127.0.0.1:8088
}
```

## Estado TLS

⚠️ **Cert autofirmado** (no Let's Encrypt).

**Razón**: Let's Encrypt consulta los nameservers del TLD `.co` (`registrydns.co`) para validar el dominio, y estos nameservers **NO ESTÁN RESPONDIENDO** en el momento del deploy. Let's Encrypt recibe `NXDOMAIN` desde sus validadores, así que no puede emitir certs via HTTP-01.

**Workaround actual**: cert autofirmado wildcard generado con openssl. El browser mostrará warning TLS hasta que se cambie.

### Generar cert autofirmado (si se borra)
```bash
sudo mkdir -p /etc/caddy/certs/ecommerce
cd /etc/caddy/certs/ecommerce
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout key.pem -out cert.pem \
  -subj "/CN=*.ecommerce.andresmorales.com.co" \
  -addext "subjectAltName=DNS:*.ecommerce.andresmorales.com.co,DNS:dashboard.ecommerce.andresmorales.com.co,DNS:api.ecommerce.andresmorales.com.co,DNS:flows.ecommerce.andresmorales.com.co,DNS:wa.ecommerce.andresmorales.com.co"
chmod 644 key.pem cert.pem
```

## Migrar a Let's Encrypt (cuando TLD .co responda)

1. Verificar resolución:
   ```bash
   dig NS andresmorales.com.co @a.registrydns.co +time=10
   dig A ecommerce.dashboard.andresmorales.com.co @a.registrydns.co +time=10
   ```
2. Si responde OK, regenerar el bloque ecommerce en Caddyfile SIN cert autofirmado:
   ```caddyfile
   dashboard.ecommerce.andresmorales.com.co,
   api.ecommerce.andresmorales.com.co,
   flows.ecommerce.andresmorales.com.co,
   wa.ecommerce.andresmorales.com.co {
       # sin tls — Caddy emite certs automáticos
       @dashboard host dashboard.ecommerce.andresmorales.com.co
       handle @dashboard { reverse_proxy 127.0.0.1:3040 }
       @api       host api.ecommerce.andresmorales.com.co
       handle @api       { reverse_proxy 127.0.0.1:8040 }
       @flows     host flows.ecommerce.andresmorales.com.co
       handle @flows     { reverse_proxy 127.0.0.1:5678 }
       @wa        host wa.ecommerce.andresmorales.com.co
       handle @wa        { reverse_proxy 127.0.0.1:8088 }
   }
   ```
3. `sudo caddy validate && sudo systemctl restart caddy`

## Backups

En `/home/telchar/projects/ecommerce-brain/backups/dns/`:
- `pre-migration/dig-baseline-*.txt` — dig ANTES de cualquier intervención
- `pre-migration/dns-backup-*.json` — JSON de getHosts (solo A records visibles)
- `pre-restoration/pre-restore-*.json` — JSON pre-setHosts

## Restaurar EXACTAMENTE como estaba antes del deploy

1. Backup actual: este doc + `backups/dns/pre-migration/dig-baseline-*.txt`
2. Replicar vía Namecheap API con setHosts (sin los 4 nuevos):
   ```python
   records = [
       ('www', 'A', '38.242.194.196'),
       ('mail', 'A', '38.242.194.196'),
       ('shop', 'A', '38.242.194.196'),
       # ... los 14 originales + MX + 2 TXT root (sin CNAMEs mailcow
       # porque mi backup dig inicial no los detectó)
       '@', 'MX', 'mail.andresmorales.com.co.',
       '@', 'TXT', 'v=spf1 ip4:38.242.194.196 include:spf.brevo.com -all',
       '@', 'TXT', 'brevo-code:7788264cb0cef0291f7c71794ca03cc8',
   ]
   ```
3. Restaurar Caddyfile desde backup: `cp /etc/caddy/Caddyfile.bak.pre-ecommerce-brain.* /etc/caddy/Caddyfile`

## Contactos
- Namecheap API dashboard: https://ap.www.namecheap.com/Domains/dns
- Soporte Namecheap: https://www.namecheap.com/support/
FROM node:22-alpine AS base
WORKDIR /app

# ─── deps ────────────────────────────────────────────────────────────────
FROM base AS deps
COPY package.json ./
RUN npm install --no-audit --no-fund --legacy-peer-deps

# ─── build ───────────────────────────────────────────────────────────────
FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ─── run ─────────────────────────────────────────────────────────────────
FROM base AS run
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD wget -q -O- http://localhost:3000/api/health || exit 1
CMD ["node", "server.js"]
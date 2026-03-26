# AB Logistics OS — Next.js (multi-stage, standalone, usuario no-root)
# Contexto de build: carpeta frontend/

# ─── Dependencias npm (capa cacheable) ─────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json ./
RUN npm ci

# ─── Build de producción ───────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Variables públicas inlinadas en el bundle (definir en docker-compose build.args)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ARG NEXT_PUBLIC_MAPS_API_KEY
ARG NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ENV NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=${NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}
ENV NEXT_PUBLIC_MAPS_API_KEY=${NEXT_PUBLIC_MAPS_API_KEY}
ENV NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN}

RUN npm run build

# ─── Runtime mínimo (solo standalone + estáticos) ─────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]

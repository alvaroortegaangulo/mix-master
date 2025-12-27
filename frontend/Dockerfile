# syntax=docker/dockerfile:1.6

# ============================
# 1) Imagen base
# ============================
FROM node:20-alpine AS base

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

# ============================
# 2) Etapa: dependencias (deps)
# ============================
FROM base AS deps

# Copiamos definición de dependencias (solo esto para cache fino)
COPY package*.json ./

# Instalamos deps con caché de npm (BuildKit)
RUN --mount=type=cache,target=/root/.npm npm ci --prefer-offline --no-audit

# ============================
# 3) Etapa: build de Next
# ============================
FROM base AS builder

# Reutilizamos node_modules ya instalados
COPY --from=deps /app/node_modules ./node_modules

# Copiamos TODO el código del frontend
COPY . .

ENV NODE_ENV=production

# Build arg para GA que llega desde docker-compose
ARG NEXT_PUBLIC_GA_MEASUREMENT_ID
ENV NEXT_PUBLIC_GA_MEASUREMENT_ID=$NEXT_PUBLIC_GA_MEASUREMENT_ID

# Build arg para acelerar builds (omite lint/typecheck/CSS optimization)
ARG FAST_BUILD=1
ENV FAST_BUILD=$FAST_BUILD

# Construimos la app (cachea .next para builds repetidos)
RUN --mount=type=cache,target=/app/.next/cache npm run build

# ============================
# 4) Etapa: runtime endurecida
# ============================
FROM base AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Usuario NO root
RUN addgroup -g 1001 nodejs \
    && adduser -D -u 1001 nextjs -G nodejs

# Copiamos solo lo necesario para producción
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package*.json ./

# Copiamos node_modules ya instalados
COPY --from=deps /app/node_modules ./node_modules

# Permisos correctos
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-p", "3000"]

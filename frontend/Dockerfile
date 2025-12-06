# ============================
# 1) Etapa: dependencias (build)
# ============================
FROM node:20-alpine AS deps

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Copiamos definición de dependencias
COPY package*.json ./

# Instalamos deps de forma determinista
# (npm ci requiere package-lock.json o npm-shrinkwrap.json)
RUN npm ci

# ============================
# 2) Etapa: build de Next
# ============================
FROM node:20-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Reutilizamos node_modules ya instalados
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Construimos la app (Next usará NODE_ENV=production internamente)
RUN npm run build

# ============================
# 3) Etapa: runtime endurecida
# ============================
FROM node:20-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Usuario NO root
RUN addgroup -g 1001 nodejs \
    && adduser -D -u 1001 nextjs -G nodejs

# Solo copiamos lo necesario para producción
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY package*.json ./

# Solo dependencias de producción
RUN npm ci --omit=dev && npm cache clean --force

# Permisos correctos
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-p", "3000"]

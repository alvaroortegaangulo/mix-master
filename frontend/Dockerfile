# ============================
# 1) Etapa: dependencias (build)
# ============================
FROM node:20-alpine AS deps

# Mejor práctica: no interactivo
ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Copiamos solo definición de deps para cachear mejor
COPY package*.json ./

# Instalamos TODAS las dependencias (incluyendo dev) para poder hacer npm run build
RUN npm ci

# ============================
# 2) Etapa: build de Next
# ============================
FROM node:20-alpine AS builder

ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# Reutilizamos node_modules de la etapa deps
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Construimos la app
RUN npm run build

# ============================
# 3) Etapa: runtime endurecida
# ============================
FROM node:20-alpine AS runner

# Entorno de producción
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

# --- Crear usuario NO root ---
RUN addgroup -g 1001 nodejs \
    && adduser -D -u 1001 nextjs -G nodejs

# Solo copiamos lo que hace falta en producción
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY package*.json ./

# Instalamos SOLO dependencias de producción
# (sin devDependencies)
RUN npm ci --omit=dev && npm cache clean --force

# Cambiamos propietario de los ficheros al usuario no root
RUN chown -R nextjs:nodejs /app

# A partir de aquí, todo corre como usuario sin privilegios
USER nextjs

# Puerto de Next en producción
EXPOSE 3000

# Arranque en modo producción
CMD ["npm", "run", "start", "--", "-p", "3000"]

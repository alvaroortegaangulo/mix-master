# Imagen base Node para producción
FROM node:20-alpine

# Desactivar telemetría de Next
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Directorio de trabajo
WORKDIR /app

# Copiamos solo package*.json para cachear dependencias
COPY package*.json ./

# Instalamos dependencias
RUN npm install --omit=dev

# Copiamos el resto del código
COPY . .

# IMPORTANTE: aquí metemos la URL pública del backend
# Sustituye TU_IP por la IP pública del VPS
ENV NEXT_PUBLIC_BACKEND_URL=http://161.97.131.133

# Construimos la app Next
RUN npm run build

# Comando de arranque: Next en modo producción
CMD ["npm", "run", "start", "--", "-p", "3000"]

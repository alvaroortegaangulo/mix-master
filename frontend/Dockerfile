# Imagen base Node para producción
FROM node:20-alpine

# Desactivar telemetría de Next
ENV NEXT_TELEMETRY_DISABLED=1

# Directorio de trabajo
WORKDIR /app

# Copiamos solo package*.json para cachear dependencias
COPY package*.json ./

# Instalamos dependencias
RUN npm install

# Copiamos el resto del código
COPY . .

# Construimos la app Next
RUN npm run build

# Comando de arranque: Next en modo producción
CMD ["npm", "run", "start", "--", "-p", "3000"]

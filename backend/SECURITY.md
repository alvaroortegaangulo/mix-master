# 🔐 Guía de Seguridad y Configuración

## Resumen

Este documento describe cómo configurar y mantener las credenciales de forma segura en el proyecto Mix Master.

## ⚠️ IMPORTANTE

**NUNCA** commitear archivos con credenciales reales:
- `.env`
- `.env.local`
- `.env.production`
- Archivos `*.key`, `*.pem`, `*.crt`

Estos archivos están protegidos en `.gitignore`.

## Configuración Inicial

### 1. Copiar plantilla de configuración

```bash
cd backend
cp .env.example .env
```

### 2. Generar credenciales seguras

```bash
# Ejecutar script de generación
./scripts/verify-env.sh --generate
```

Esto generará valores seguros para:
- `SECRET_KEY` (64 caracteres hex) - Firma de JWT
- `REDIS_PASSWORD` (32 caracteres hex) - Contraseña de Redis
- `POSTGRES_PASSWORD` (32 caracteres hex) - Contraseña de PostgreSQL
- `MIXMASTER_API_TOKEN` (32 caracteres hex) - Token de API

### 3. Actualizar archivo `.env`

Edita `backend/.env` y reemplaza los placeholders con las credenciales generadas:

```bash
nano .env  # o tu editor preferido
```

### 4. Verificar configuración

```bash
./scripts/verify-env.sh
```

Este script valida:
- ✅ Todas las variables requeridas están definidas
- ✅ No hay placeholders sin reemplazar
- ✅ Las contraseñas tienen longitud adecuada
- ✅ No se usan contraseñas inseguras comunes

## Variables Requeridas

### Seguridad
- `SECRET_KEY`: Clave para firmar JWT (64+ caracteres)
- `MIXMASTER_API_TOKEN`: Token para autenticación de API

### Base de Datos
- `POSTGRES_USER`: Usuario de PostgreSQL (default: mixmaster)
- `POSTGRES_PASSWORD`: Contraseña de PostgreSQL (generar con script)
- `POSTGRES_DB`: Nombre de la base de datos (default: mixmaster)
- `DATABASE_URL`: URL completa de conexión (se construye automáticamente)

### Redis
- `REDIS_PASSWORD`: Contraseña de Redis (generar con script)

### Rate Limiting
- `MIXMASTER_RATE_LIMIT_REQUESTS`: Máximo de requests por ventana (default: 30)
- `MIXMASTER_RATE_LIMIT_WINDOW_SECONDS`: Duración de ventana en segundos (default: 60)

### OAuth
- `GOOGLE_CLIENT_ID`: Client ID de Google OAuth
  - Obtener desde [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

### Analytics
- `NEXT_PUBLIC_GA_MEASUREMENT_ID`: ID de Google Analytics (formato: G-XXXXXXXXXX)

## Despliegue en Producción

### 1. En el servidor

```bash
# Crear directorio de configuración
sudo mkdir -p /opt/mixmaster/backend
cd /opt/mixmaster/backend

# Crear .env con permisos restrictivos
sudo touch .env
sudo chmod 600 .env
sudo chown root:root .env

# Editar con valores de producción
sudo nano .env
```

### 2. Validar configuración de Docker

El `docker-compose.yaml` está configurado para **requerir** variables críticas:

```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in .env}
```

Si falta alguna variable, Docker Compose fallará con un mensaje claro.

### 3. Desplegar

```bash
cd /opt/mixmaster/backend

# Verificar configuración
./scripts/verify-env.sh

# Levantar servicios
docker compose up -d --build

# Verificar que todo arranca
docker compose ps
docker compose logs -f --tail=50
```

## Rotación de Credenciales

Se recomienda rotar credenciales cada **6 meses** o después de cualquier incidente.

### Proceso de rotación

1. **Generar nuevas credenciales**:
   ```bash
   ./scripts/verify-env.sh --generate > new-credentials.txt
   ```

2. **Actualizar `.env` en servidor**:
   ```bash
   sudo nano /opt/mixmaster/backend/.env
   # Reemplazar valores antiguos con los nuevos
   ```

3. **Redesplegar servicios**:
   ```bash
   docker compose down
   docker compose up -d
   ```

4. **Verificar funcionamiento**:
   ```bash
   # Test Redis
   docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping

   # Test PostgreSQL
   docker compose exec db psql -U mixmaster -d mixmaster -c "SELECT 1;"

   # Test API
   curl https://api.music-mix-master.com/health
   ```

5. **Documentar rotación**:
   - Actualizar fecha en tabla de rotaciones
   - Marcar credenciales antiguas como REVOCADAS
   - Eliminar archivo `new-credentials.txt` de forma segura

## Auditoría y Monitoreo

### Revisar logs de acceso

```bash
# Logs de PostgreSQL
docker compose logs db | grep -i "authentication\|failed"

# Logs de Redis
docker compose logs redis | grep -i "auth\|denied"

# Logs de API
docker compose logs web | grep -i "401\|403\|unauthorized"
```

### Verificar usuarios de base de datos

```bash
docker compose exec db psql -U mixmaster -d mixmaster -c "
  SELECT username, email, created_at
  FROM users
  ORDER BY created_at DESC
  LIMIT 20;
"
```

## En caso de compromiso

Si sospechas que las credenciales fueron comprometidas:

1. **Inmediato**: Rotar todas las credenciales
2. **Auditar**: Revisar logs de acceso no autorizado
3. **Invalidar**: Cambiar `SECRET_KEY` (invalida todos los JWT)
4. **Notificar**: Evaluar obligaciones legales de notificación (GDPR)
5. **Investigar**: Identificar vector de ataque
6. **Remediar**: Aplicar controles adicionales

## Buenas Prácticas

✅ **DO**:
- Generar credenciales con `openssl rand -hex`
- Usar longitudes mínimas: SECRET_KEY 64, passwords 32
- Verificar configuración con `./scripts/verify-env.sh`
- Rotar credenciales cada 6 meses
- Documentar rotaciones
- Usar permisos restrictivos en `.env` (600)

❌ **DON'T**:
- Commitear archivos `.env` al repositorio
- Usar contraseñas débiles o comunes
- Compartir credenciales por email/chat
- Reutilizar contraseñas entre entornos
- Dejar valores por defecto en producción
- Almacenar credenciales sin cifrar

## Contacto

Para reportar incidentes de seguridad, contactar a:
- Email: security@music-mix-master.com (si aplica)
- O abrir issue privado en GitHub

---

**Última actualización**: 2026-01-30
**Próxima revisión**: 2026-07-30

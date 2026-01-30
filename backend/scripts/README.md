# Scripts de Utilidad

## verify-env.sh

Script de verificación y generación de credenciales.

### Uso

#### Generar nuevas credenciales

```bash
./scripts/verify-env.sh --generate
```

Genera valores seguros para:
- SECRET_KEY (64 caracteres hex)
- REDIS_PASSWORD (32 caracteres hex)
- POSTGRES_PASSWORD (32 caracteres hex)
- MIXMASTER_API_TOKEN (32 caracteres hex)

#### Verificar configuración actual

```bash
./scripts/verify-env.sh
```

Valida que:
- ✅ Todas las variables requeridas están definidas
- ✅ No hay placeholders sin reemplazar
- ✅ Las contraseñas tienen longitud adecuada
- ✅ No se usan contraseñas inseguras comunes

### Ejemplo de flujo completo

```bash
# 1. Copiar plantilla
cp .env.example .env

# 2. Generar credenciales
./scripts/verify-env.sh --generate > credentials.txt

# 3. Editar .env con las credenciales generadas
nano .env

# 4. Verificar que todo está correcto
./scripts/verify-env.sh

# 5. Eliminar archivo temporal de credenciales
rm credentials.txt
```

### Códigos de salida

- `0`: Todo correcto
- `1`: Hay problemas en la configuración

### Integración con CI/CD

```bash
# En pipeline de CI/CD, verificar antes de desplegar
./scripts/verify-env.sh || exit 1
docker compose up -d
```

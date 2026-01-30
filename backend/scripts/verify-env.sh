#!/bin/bash
# Script de verificación de configuración y credenciales
# Uso: ./scripts/verify-env.sh [--generate]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENV_FILE="${ENV_FILE:-.env}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Mix Master - Verificación de .env  ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Función para verificar si una variable está definida
check_var() {
    local var_name="$1"
    local var_value="${!var_name}"
    local is_secret="${2:-false}"

    if [ -z "$var_value" ]; then
        echo -e "${RED}[✘]${NC} $var_name: NO DEFINIDA"
        return 1
    elif [ "$var_value" = "generate-with-openssl-rand-hex-32" ] || \
         [ "$var_value" = "generate-with-openssl-rand-hex-16" ] || \
         [ "$var_value" = "your-google-client-id.apps.googleusercontent.com" ] || \
         [ "$var_value" = "G-XXXXXXXXXX" ]; then
        echo -e "${YELLOW}[⚠]${NC} $var_name: PLACEHOLDER (debe ser reemplazado)"
        return 1
    else
        if [ "$is_secret" = "true" ]; then
            # Ocultar valor de secretos
            echo -e "${GREEN}[✔]${NC} $var_name: Definida (${#var_value} caracteres)"
        else
            echo -e "${GREEN}[✔]${NC} $var_name: $var_value"
        fi
        return 0
    fi
}

# Función para generar credenciales
generate_credentials() {
    echo -e "\n${BLUE}Generando nuevas credenciales seguras...${NC}\n"

    echo "# Credenciales generadas el $(date)"
    echo "# Guardar en lugar seguro (password manager)"
    echo ""
    echo "SECRET_KEY=$(openssl rand -hex 32)"
    echo "REDIS_PASSWORD=$(openssl rand -hex 16)"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
    echo "MIXMASTER_API_TOKEN=$(openssl rand -hex 16)"
    echo ""
    echo -e "${YELLOW}IMPORTANTE: Copiar estos valores a tu archivo .env${NC}"
}

# Si se pasa --generate, solo generar y salir
if [ "$1" = "--generate" ]; then
    generate_credentials
    exit 0
fi

# Verificar que existe el archivo .env
if [ ! -f "$BACKEND_DIR/$ENV_FILE" ]; then
    echo -e "${RED}[ERROR]${NC} Archivo $ENV_FILE no encontrado en $BACKEND_DIR"
    echo ""
    echo -e "${YELLOW}Pasos para crear el archivo:${NC}"
    echo "  1. Copiar la plantilla:"
    echo "     cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env"
    echo ""
    echo "  2. Generar credenciales:"
    echo "     ./scripts/verify-env.sh --generate"
    echo ""
    echo "  3. Editar $BACKEND_DIR/.env con las credenciales generadas"
    exit 1
fi

# Cargar variables del .env
export $(grep -v '^#' "$BACKEND_DIR/$ENV_FILE" | grep -v '^$' | xargs)

echo -e "${BLUE}=== Variables Críticas (Seguridad) ===${NC}"
all_ok=true

check_var "SECRET_KEY" true || all_ok=false
check_var "MIXMASTER_API_TOKEN" true || all_ok=false

echo -e "\n${BLUE}=== Variables de Base de Datos ===${NC}"
check_var "POSTGRES_USER" false || all_ok=false
check_var "POSTGRES_PASSWORD" true || all_ok=false
check_var "POSTGRES_DB" false || all_ok=false
check_var "DATABASE_URL" false || all_ok=false

echo -e "\n${BLUE}=== Variables de Redis ===${NC}"
check_var "REDIS_PASSWORD" true || all_ok=false

echo -e "\n${BLUE}=== Variables de Rate Limiting ===${NC}"
check_var "MIXMASTER_RATE_LIMIT_REQUESTS" false || all_ok=false
check_var "MIXMASTER_RATE_LIMIT_WINDOW_SECONDS" false || all_ok=false

echo -e "\n${BLUE}=== Variables de OAuth ===${NC}"
check_var "GOOGLE_CLIENT_ID" false || all_ok=false

echo -e "\n${BLUE}=== Variables de Analytics ===${NC}"
check_var "NEXT_PUBLIC_GA_MEASUREMENT_ID" false || all_ok=false

# Verificaciones adicionales de seguridad
echo -e "\n${BLUE}=== Verificaciones de Seguridad ===${NC}"

# Verificar longitud de SECRET_KEY (debe ser 64 caracteres hex)
if [ ${#SECRET_KEY} -lt 64 ]; then
    echo -e "${YELLOW}[⚠]${NC} SECRET_KEY demasiado corto (${#SECRET_KEY} chars, recomendado: 64+)"
    all_ok=false
else
    echo -e "${GREEN}[✔]${NC} SECRET_KEY tiene longitud adecuada"
fi

# Verificar que no se usen contraseñas inseguras comunes
INSECURE_PASSWORDS=("password" "123456" "admin" "securepassword" "mixmaster")
for pwd in "${INSECURE_PASSWORDS[@]}"; do
    if [ "$POSTGRES_PASSWORD" = "$pwd" ] || [ "$REDIS_PASSWORD" = "$pwd" ]; then
        echo -e "${RED}[✘]${NC} Contraseña insegura detectada: '$pwd'"
        all_ok=false
    fi
done

if $all_ok; then
    echo -e "\n${GREEN}[✔] Todas las verificaciones pasaron correctamente${NC}"
else
    echo -e "\n${YELLOW}[⚠] Hay problemas en la configuración${NC}"
    echo -e "    Ejecuta: ./scripts/verify-env.sh --generate"
    echo -e "    Y actualiza tu archivo .env con las nuevas credenciales"
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo ""

# Código de salida
if $all_ok; then
    exit 0
else
    exit 1
fi

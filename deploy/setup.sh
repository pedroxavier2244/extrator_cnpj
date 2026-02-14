#!/usr/bin/env bash
# =============================================================================
# setup.sh — Configura o servidor Oracle Cloud (Ubuntu 22.04) do zero
#
# USO:
#   1. Edite as variáveis da seção CONFIGURAÇÃO abaixo
#   2. Copie este arquivo para o servidor via scp ou cole no terminal
#   3. Execute:  bash setup.sh
#
# O script instala PostgreSQL, Python 3.11, clona o projeto,
# cria o banco, aplica as migrations e sobe a API como serviço systemd.
# =============================================================================
set -euo pipefail

# =============================================================================
# CONFIGURAÇÃO — edite antes de rodar
# =============================================================================
GITHUB_REPO="https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git"  # <-- altere
APP_DIR="/opt/extrator_cnpj"
DB_NAME="cnpj"
DB_USER="cnpj_user"
DB_PASS="troque_esta_senha_segura"   # <-- altere
API_PORT="8000"
PYTHON_VERSION="3.11"
# =============================================================================

log() { echo -e "\n\033[1;32m>>> $*\033[0m\n"; }
err() { echo -e "\033[1;31m[ERRO] $*\033[0m" >&2; exit 1; }

[[ $EUID -ne 0 ]] && err "Execute como root: sudo bash setup.sh"

# --- Sistema ---
log "Atualizando sistema..."
apt-get update -qq
apt-get upgrade -y -qq

log "Instalando dependências do sistema..."
apt-get install -y -qq \
    git curl wget unzip \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python3-pip \
    postgresql postgresql-contrib \
    build-essential libpq-dev

# --- PostgreSQL ---
log "Configurando PostgreSQL..."
systemctl enable postgresql
systemctl start postgresql

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"

# Aumenta shared_buffers e work_mem para melhor performance de queries
PG_CONF=$(sudo -u postgres psql -t -c "SHOW config_file;" | tr -d ' ')
cat >> "${PG_CONF}" <<EOF

# Tuning para extrator CNPJ
shared_buffers = 256MB
work_mem = 64MB
maintenance_work_mem = 256MB
effective_cache_size = 512MB
EOF
systemctl restart postgresql
log "PostgreSQL configurado."

# --- Projeto ---
log "Clonando repositório..."
if [[ -d "${APP_DIR}" ]]; then
    cd "${APP_DIR}" && git pull
else
    git clone "${GITHUB_REPO}" "${APP_DIR}"
fi

cd "${APP_DIR}"

log "Criando ambiente virtual Python..."
python${PYTHON_VERSION} -m venv .venv
source .venv/bin/activate

log "Instalando dependências Python..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# --- .env ---
DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"

if [[ ! -f "${APP_DIR}/.env" ]]; then
    log "Criando .env..."
    cat > "${APP_DIR}/.env" <<EOF
DATABASE_URL=${DATABASE_URL}
RAW_DATA_PATH=/opt/extrator_cnpj/data/raw
STAGING_PATH=/opt/extrator_cnpj/data/staging
PROCESSED_PATH=/opt/extrator_cnpj/data/processed
BATCH_SIZE=30000
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1
APP_NAME=Sistema CNPJ
ETL_HASH_ALGORITHM=sha256
REDIS_URL=
CACHE_TTL_SECONDS=86400
BATCH_MAX_SIZE=1000
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
EOF
else
    log ".env já existe, mantendo o existente."
fi

# --- Diretórios de dados ---
log "Criando diretórios de dados..."
mkdir -p "${APP_DIR}/data/raw" \
         "${APP_DIR}/data/staging" \
         "${APP_DIR}/data/processed"

# --- Migrations ---
log "Aplicando migrations do banco..."
source "${APP_DIR}/.venv/bin/activate"
cd "${APP_DIR}"
PYTHONPATH="${APP_DIR}" alembic upgrade head

# --- Serviço systemd ---
log "Configurando serviço systemd..."
cat > /etc/systemd/system/cnpj-api.service <<EOF
[Unit]
Description=Extrator CNPJ - API FastAPI
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT} --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cnpj-api

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cnpj-api
systemctl start cnpj-api

# --- Firewall ---
log "Abrindo porta ${API_PORT} no firewall..."
if command -v ufw &>/dev/null; then
    ufw allow "${API_PORT}/tcp"
fi

# --- Resultado ---
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "IP_DO_SERVIDOR")

log "========================================================="
log "Instalação concluída!"
echo ""
echo "  API rodando em: http://${SERVER_IP}:${API_PORT}"
echo "  Teste:          curl http://${SERVER_IP}:${API_PORT}/api/v1/health"
echo ""
echo "  Próximo passo: baixar os arquivos da Receita Federal"
echo "  Execute:        bash ${APP_DIR}/deploy/download_cnpj.sh"
echo ""
echo "  Ver logs da API: journalctl -u cnpj-api -f"
log "========================================================="

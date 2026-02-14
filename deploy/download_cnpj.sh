#!/usr/bin/env bash
# =============================================================================
# download_cnpj.sh — Baixa os arquivos do CNPJ direto da Receita Federal
#                    e executa o ETL no servidor
#
# USO:
#   bash /opt/extrator_cnpj/deploy/download_cnpj.sh
#
# Os arquivos são baixados direto do servidor da Receita Federal via WebDAV
# (protocolo suportado pelo Nextcloud da RFB) sem precisar de login.
# =============================================================================
set -euo pipefail

APP_DIR="/opt/extrator_cnpj"
RAW_DIR="${APP_DIR}/data/raw"
SHARE_TOKEN="YggdBLfdninEJX9"
BASE_URL="https://arquivos.receitafederal.gov.br/public.php/webdav"

log()  { echo -e "\n\033[1;32m[$(date '+%H:%M:%S')] $*\033[0m"; }
warn() { echo -e "\033[1;33m[AVISO] $*\033[0m"; }
err()  { echo -e "\033[1;31m[ERRO] $*\033[0m" >&2; exit 1; }

command -v wget  &>/dev/null || apt-get install -y wget  -qq
command -v curl  &>/dev/null || apt-get install -y curl  -qq

mkdir -p "${RAW_DIR}"
cd "${RAW_DIR}"

# =============================================================================
# 1. Lista todos os arquivos disponíveis no compartilhamento da RFB
# =============================================================================
log "Listando arquivos disponíveis na Receita Federal..."

FILES=$(curl -s --user "${SHARE_TOKEN}:" \
    -X PROPFIND \
    --header "Depth: 1" \
    "${BASE_URL}/" 2>/dev/null \
    | grep -oP '(?<=<d:href>)[^<]+\.zip(?=</d:href>)' \
    | sed 's|.*/public.php/webdav/||' \
    || true)

if [[ -z "${FILES}" ]]; then
    warn "Não foi possível listar via WebDAV. Usando lista fixa de arquivos conhecidos..."
    # Lista fixa baseada no formato padrão da Receita Federal
    # Atualize se a Receita mudar os nomes dos arquivos
    FILES="Empresas0.zip Empresas1.zip Empresas2.zip Empresas3.zip Empresas4.zip \
Empresas5.zip Empresas6.zip Empresas7.zip Empresas8.zip Empresas9.zip \
Estabelecimentos0.zip Estabelecimentos1.zip Estabelecimentos2.zip Estabelecimentos3.zip \
Estabelecimentos4.zip Estabelecimentos5.zip Estabelecimentos6.zip Estabelecimentos7.zip \
Estabelecimentos8.zip Estabelecimentos9.zip \
Socios0.zip Socios1.zip Socios2.zip Socios3.zip Socios4.zip \
Socios5.zip Socios6.zip Socios7.zip Socios8.zip Socios9.zip \
Simples.zip \
Cnaes.zip Motivos.zip Municipios.zip Naturezas.zip Paises.zip Qualificacoes.zip"
fi

log "Arquivos encontrados:"
echo "${FILES}" | tr ' ' '\n' | grep -v '^$' | sed 's/^/  /'

# =============================================================================
# 2. Baixa cada arquivo (pula se já existir e tiver tamanho > 0)
# =============================================================================
TOTAL=0
BAIXADOS=0
PULADOS=0

for FILE in ${FILES}; do
    [[ -z "${FILE}" ]] && continue
    TOTAL=$((TOTAL + 1))

    DEST="${RAW_DIR}/${FILE}"

    if [[ -f "${DEST}" && -s "${DEST}" ]]; then
        warn "Pulando ${FILE} (já existe)"
        PULADOS=$((PULADOS + 1))
        continue
    fi

    log "Baixando ${FILE}..."
    wget \
        --user="${SHARE_TOKEN}" \
        --password="" \
        --progress=bar:force \
        --tries=3 \
        --timeout=120 \
        --continue \
        -O "${DEST}" \
        "${BASE_URL}/${FILE}" \
    || {
        warn "Falha ao baixar ${FILE} via WebDAV, tentando link direto..."
        DIRECT_URL="https://arquivos.receitafederal.gov.br/index.php/s/${SHARE_TOKEN}/download?files=${FILE}"
        wget \
            --progress=bar:force \
            --tries=3 \
            --timeout=120 \
            --continue \
            -O "${DEST}" \
            "${DIRECT_URL}" \
        || { warn "Não foi possível baixar ${FILE}, pulando..."; rm -f "${DEST}"; continue; }
    }

    BAIXADOS=$((BAIXADOS + 1))
    log "${FILE} baixado. Tamanho: $(du -sh "${DEST}" | cut -f1)"
done

log "Download concluído: ${BAIXADOS} baixados, ${PULADOS} já existiam, ${TOTAL} total."

# =============================================================================
# 3. Verifica espaço em disco antes do ETL
# =============================================================================
DISCO_LIVRE=$(df -BG "${APP_DIR}" | awk 'NR==2{print $4}' | tr -d 'G')
if [[ "${DISCO_LIVRE}" -lt 25 ]]; then
    warn "Pouco espaço em disco: ${DISCO_LIVRE}GB livre. Recomendado mínimo 25GB."
    warn "O ETL pode falhar. Considere liberar espaço antes de continuar."
    read -rp "Continuar mesmo assim? [s/N] " RESP
    [[ "${RESP,,}" != "s" ]] && exit 1
fi

# =============================================================================
# 4. Executa o ETL
# =============================================================================
log "Iniciando ETL (pode levar 2-4 horas)..."
log "Acompanhe o progresso com:  tail -f /tmp/etl.log"

source "${APP_DIR}/.venv/bin/activate"
cd "${APP_DIR}"

nohup bash -c "
    PYTHONPATH=${APP_DIR} python -m etl.orchestrator 2>&1 | tee /tmp/etl.log
    echo 'ETL finalizado com código: '\$?
" &

ETL_PID=$!
log "ETL rodando em background (PID: ${ETL_PID})"
echo ""
echo "  Acompanhar progresso:  tail -f /tmp/etl.log"
echo "  Ver se ainda está rodando: ps -p ${ETL_PID}"
echo ""
echo "  Quando o ETL terminar, a API já estará atualizada automaticamente."
echo "  Não é necessário reiniciar o serviço."

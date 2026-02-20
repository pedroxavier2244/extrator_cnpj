# ETL — Documentação Técnica para Desenvolvedores

> Pipeline de importação de dados públicos da Receita Federal (CNPJ) para PostgreSQL.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura do Pipeline](#arquitetura-do-pipeline)
- [Estrutura de Arquivos](#estrutura-de-arquivos)
- [Fonte de Dados](#fonte-de-dados)
- [Fluxo de Execução](#fluxo-de-execução)
- [Processadores](#processadores)
- [Utilitários](#utilitários)
- [Rastreamento de Importações](#rastreamento-de-importações)
- [Configuração](#configuração)
- [Como Executar](#como-executar)
- [Como Adicionar um Novo Processador](#como-adicionar-um-novo-processador)
- [Decisões de Design](#decisões-de-design)

---

## Visão Geral

O ETL importa arquivos ZIP disponibilizados pela Receita Federal contendo dados cadastrais de todas as empresas brasileiras (~57 milhões de CNPJs). O processo é **idempotente**: rodar múltiplas vezes com os mesmos arquivos produz o mesmo resultado no banco.

**Características principais:**
- Suporte a ZIPs aninhados (ZIP dentro de ZIP)
- Processamento em chunks via Pandas (sem carregar tudo na memória)
- Inserção em massa via `COPY FROM STDIN` do PostgreSQL
- Upsert com `INSERT ... ON CONFLICT` para evitar duplicatas
- Deduplicação por hash SHA-256 por arquivo
- Rastreamento de status por importação na tabela `importacoes`

---

## Arquitetura do Pipeline

```
data/raw/*.zip
      │
      ▼
┌─────────────────────────────────────────┐
│           orchestrator.py               │
│                                         │
│  1. Calcula SHA-256 do ZIP              │
│  2. Verifica se já foi processado       │
│  3. Extrai e classifica arquivos        │
│  4. Chama cada processor               │
│  5. Move ZIP para data/processed/       │
│  6. Atualiza status em importacoes      │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│         processors/*.py                 │
│                                         │
│  Para cada chunk do CSV:                │
│  1. Lê CSV (latin1, sep=;)              │
│  2. Normaliza strings e datas           │
│  3. COPY para tabela staging            │
│  4. UPSERT staging → tabela final       │
│  5. Limpa staging                       │
└─────────────────────────────────────────┘
      │
      ▼
  PostgreSQL
```

---

## Estrutura de Arquivos

```
etl/
├── orchestrator.py              # Ponto de entrada — coordena todo o pipeline
├── processors/
│   ├── empresas_processor.py        # Dados básicos das empresas
│   ├── estabelecimentos_processor.py # Endereços e CNAEs dos estabelecimentos
│   ├── socios_processor.py          # Sócios e acionistas
│   ├── simples_processor.py         # Opção pelo Simples Nacional / MEI
│   ├── cnaes_processor.py           # Tabela de referência: atividades econômicas
│   ├── motivos_processor.py         # Tabela de referência: motivos de situação
│   ├── municipios_processor.py      # Tabela de referência: municípios
│   ├── naturezas_processor.py       # Tabela de referência: naturezas jurídicas
│   ├── paises_processor.py          # Tabela de referência: países
│   ├── qualificacoes_processor.py   # Tabela de referência: qualificações de sócios
│   └── reference_processor.py       # Utilitário genérico usado pelos processadores de referência
└── utils/
    ├── postgres_copy.py             # COPY + UPSERT no PostgreSQL
    ├── file_hash.py                 # Cálculo de hash SHA-256
    └── normalize.py                 # Normalização de datas
```

---

## Fonte de Dados

Os arquivos são disponibilizados pela Receita Federal em:

```
https://arquivos.receitafederal.gov.br
```

### Tipos de arquivo e padrão de nome

| Padrão no nome | Tipo | Destino no banco |
|----------------|------|-----------------|
| `EMPRE` | Dados básicos das empresas | `empresas` |
| `ESTABELE` | Estabelecimentos/filiais | `estabelecimentos` |
| `SOCIO` | Sócios e acionistas | `socios` |
| `SIMPLES` | Simples Nacional / MEI | `simples` |
| `CNAE` | Atividades econômicas | `cnaes` |
| `MOTI` | Motivos de situação | `motivos` |
| `MUNIC` | Municípios | `municipios` |
| `NATJU` | Naturezas jurídicas | `naturezas` |
| `PAIS` | Países | `paises` |
| `QUALS` | Qualificações de sócios | `qualificacoes` |

### Formato dos arquivos CSV

- **Encoding:** `latin1` (ISO-8859-1)
- **Separador:** `;` (ponto e vírgula)
- **Header:** pode estar ausente (a RFB às vezes omite)
- **Datas:** formato `YYYYMMDD` (ex: `20230102`)
- **Valores nulos:** campo vazio `""` ou ausente

### Estrutura de ZIP aninhado

Os arquivos da RFB tipicamente chegam assim:

```
Download.zip
└── Empresas0.zip          ← ZIP aninhado
    └── K3241.K03200Y0.D40308.EMPRECSV   ← CSV real
```

O orchestrator detecta e extrai automaticamente ZIPs aninhados.

---

## Fluxo de Execução

### orchestrator.py — passo a passo

```python
run(force=False)
  └── Para cada *.zip em data/raw/:
        └── process_zip_file(zip_path, force)
              │
              ├── 1. Calcula SHA-256 do arquivo
              │
              ├── 2. Se não force e já processado com sucesso:
              │       → loga e move para data/processed/
              │       → retorna 0 (sem reprocessar)
              │
              ├── 3. Insere registro em importacoes com status PROCESSING
              │
              ├── 4. _extract_classified_files()
              │       → abre o ZIP externo
              │       → para cada arquivo interno:
              │           - se for .zip: extrai o ZIP aninhado, classifica, extrai CSVs
              │           - senão: classifica e extrai o CSV
              │       → retorna dict com paths agrupados por tipo
              │
              ├── 5. Chama os processadores na ordem:
              │       empresas → estabelecimentos → socios
              │       cnaes → motivos → municipios → naturezas → paises → qualificacoes → simples
              │
              ├── 6. Se nenhum registro processado: FAILED
              │
              ├── 7. Se faltar tipos auxiliares: PARTIAL
              │
              └── 8. Sucesso: SUCCES → move ZIP para data/processed/
```

### Classificação de arquivos

A função `_classify_name()` identifica o tipo pelo nome do arquivo:

```python
def _classify_name(file_name: str) -> str | None:
    upper = Path(file_name).name.upper()
    if "EMPRE"   in upper: return "empresas"
    if "ESTABELE" in upper: return "estabelecimentos"
    if "SOCIO"   in upper: return "socios"
    if "CNAE"    in upper: return "cnaes"
    if "MOTI"    in upper: return "motivos"
    if "MUNIC"   in upper: return "municipios"
    if "NATJU"   in upper: return "naturezas"
    if "PAIS"    in upper: return "paises"
    if "QUALS"   in upper: return "qualificacoes"
    if "SIMPLES" in upper: return "simples"
    return None  # arquivo ignorado
```

---

## Processadores

Todos os processadores seguem o mesmo padrão:

```
CSV → chunks (50k linhas) → normaliza → staging → upsert → tabela final
```

### Padrão de um processador

```python
CSV_COLUMNS    = [...]   # colunas que existem no CSV da RFB
INSERT_COLUMNS = [...]   # colunas que serão inseridas no banco
STAGING_TABLE  = "stg_X" # tabela temporária de staging
TARGET_TABLE   = "X"     # tabela final

def process_X_csv(file_path, engine, chunk_size) -> int:
    _ensure_staging_table(engine)        # cria stg se não existir

    chunks = pd.read_csv(file_path, ...)  # lê em chunks

    for chunk in chunks:
        prepared = _prepare_chunk(chunk)  # normaliza
        copy_dataframe_to_staging(engine, prepared, STAGING_TABLE)
        upsert_from_staging(engine, STAGING_TABLE, TARGET_TABLE, ...)
        processed += len(prepared)

    return processed  # total de linhas processadas
```

---

### empresas_processor.py

**Arquivo RFB:** `EMPRECSV` (ex: `Empresas0.zip`)

**Colunas do CSV:**

| Coluna CSV | Coluna no banco | Descrição |
|------------|-----------------|-----------|
| `cnpj_basico` | `cnpj_basico` | CNPJ raiz (8 dígitos) — **chave primária** |
| `razao_social` | `razao_social` | Razão social |
| `natureza_juridica` | `natureza_juridica` | Código da natureza jurídica |
| `qualificacao_responsavel` | descartada | Não inserida no banco |
| `capital_social` | `capital_social` | Capital social declarado |
| `porte_empresa` | `porte_empresa` | Porte da empresa |
| `ente_federativo` | descartada | Não inserida no banco |

**Conflict:** `ON CONFLICT (cnpj_basico) DO UPDATE` — atualiza todos os campos.

---

### estabelecimentos_processor.py

**Arquivo RFB:** `ESTABELECSV` (ex: `Estabelecimentos0.zip`)

**Processamento especial:**
- Constrói `cnpj_completo` concatenando `cnpj_basico + cnpj_ordem + cnpj_dv`
- Valida que `cnpj_completo` tem exatamente 14 caracteres
- Normaliza colunas de data: `data_situacao`, `inicio`, `data_situacao_especial`
- Remove duplicatas por `cnpj_completo` dentro do chunk

**Colunas do CSV (28 colunas):**

| Coluna CSV | Coluna no banco | Observação |
|------------|-----------------|------------|
| `cnpj_basico` | `cnpj_basico` | |
| `cnpj_ordem` | — | Usado apenas para montar `cnpj_completo` |
| `cnpj_dv` | — | Usado apenas para montar `cnpj_completo` |
| `matriz_filial` | descartada | |
| `nome_fantasia` | `nome_fantasia` | |
| `situacao` | `situacao` | |
| `data_situacao` | descartada (staging) | Normalizada mas não persiste |
| `motivo` | `motivo` | |
| `pais` | `pais` | |
| `cnae_principal` | `cnae_principal` | |
| `cnae_secundario` | `cnae_secundario` | Múltiplos valores separados por `;` |
| `uf` | `uf` | |
| `municipio` | `municipio` | |
| *(outras 15 colunas)* | descartadas | Endereço, telefone, email — não persistidos |

**Conflict:** `ON CONFLICT (cnpj_completo) DO UPDATE`.

---

### socios_processor.py

**Arquivo RFB:** `SOCIOCSV` (ex: `Socios0.zip`)

**Processamento especial:**
- Renomeia colunas: `nome` → `nome_socio`, `cpf_cnpj` → `cpf_cnpj_socio`
- Normaliza data de entrada: `data_entrada`
- Upsert com expressão de índice NULL-safe:
  `(cnpj_basico, COALESCE(nome_socio, ''), COALESCE(cpf_cnpj_socio, ''))`

**Colunas do CSV:**

| Coluna CSV | Coluna no banco | Observação |
|------------|-----------------|------------|
| `cnpj_basico` | `cnpj_basico` | |
| `tipo` | descartada | Tipo do sócio (1=PF, 2=PJ, 3=Estrangeiro) |
| `nome` | `nome_socio` | |
| `cpf_cnpj` | `cpf_cnpj_socio` | Mascarado pela RFB |
| `qualificacao` | `qualificacao` | |
| `data_entrada` | `data_entrada` | |
| `pais` | `pais` | |
| `cpf_rep` | descartada | CPF do representante legal |
| `nome_rep` | descartada | Nome do representante legal |
| `qualificacao_rep` | descartada | Qualificação do representante |
| `faixa_etaria` | descartada | |

---

### Processadores de Referência

Os processadores `cnaes`, `motivos`, `municipios`, `naturezas`, `paises` e `qualificacoes` são todos idênticos em estrutura — usam `reference_processor.process_reference_csv()`:

**Tabelas de referência:**

| Processador | Tabela | Colunas CSV | Chave |
|-------------|--------|-------------|-------|
| `cnaes` | `cnaes` | `codigo`, `descricao` | `codigo` |
| `motivos` | `motivos` | `codigo`, `descricao` | `codigo` |
| `municipios` | `municipios` | `codigo`, `descricao` | `codigo` |
| `naturezas` | `naturezas` | `codigo`, `descricao` | `codigo` |
| `paises` | `paises` | `codigo`, `descricao` | `codigo` |
| `qualificacoes` | `qualificacoes` | `codigo`, `descricao` | `codigo` |

Todas com `ON CONFLICT (codigo) DO UPDATE SET descricao = EXCLUDED.descricao`.

---

### simples_processor.py

**Arquivo RFB:** `Simples.zip`

Registra a situação de cada empresa no Simples Nacional e MEI.

**Colunas:** `cnpj_basico`, `opcao_pelo_simples`, `data_opcao_pelo_simples`, `data_exclusao_do_simples`, `opcao_pelo_mei`, `data_opcao_pelo_mei`, `data_exclusao_do_mei`

**Conflict:** `ON CONFLICT (cnpj_basico) DO UPDATE`.

---

## Utilitários

### etl/utils/postgres_copy.py

Responsável pela carga eficiente no PostgreSQL.

#### `copy_dataframe_to_staging(engine, dataframe, staging_table)`

Carrega um DataFrame diretamente na tabela de staging usando `COPY FROM STDIN`:

```
DataFrame → StringIO (CSV em memória) → COPY FROM STDIN → staging_table
```

- **Trunca a staging antes de cada COPY** para evitar mistura com dados de runs anteriores
- Usa `cursor.copy_expert()` do psycopg2 para máximo desempenho
- Retorna o número de linhas copiadas

#### `upsert_from_staging(engine, staging_table, target_table, insert_columns, conflict_columns, conflict_expressions=None)`

Executa upsert da staging para a tabela final:

```sql
INSERT INTO target_table (col1, col2, ...)
SELECT DISTINCT ON (conflict_cols) col1, col2, ...
FROM staging_table
ORDER BY conflict_cols
ON CONFLICT (conflict_cols)
DO UPDATE SET col1 = EXCLUDED.col1, col2 = EXCLUDED.col2, ...
```

- **`conflict_expressions`**: permite usar expressões SQL no ON CONFLICT (necessário para o índice NULL-safe de sócios)
- **Trunca a staging ao final** para liberar espaço
- Usa `DISTINCT ON` para deduplicar dentro da própria staging antes do upsert

#### `quote_ident(identifier)`

Sanitiza identificadores SQL com aspas duplas para evitar SQL injection:

```python
quote_ident("stg_empresas")  # → '"stg_empresas"'
quote_ident('tabela"maliciosa')  # → '"tabela""maliciosa"'
```

---

### etl/utils/normalize.py

#### `normalize_date_columns(chunk, date_columns)`

Normaliza colunas de data de DataFrames Pandas:

1. Converte para string e strip
2. Tenta parsear no formato `YYYYMMDD` (padrão RFB)
3. Se falhar, tenta parsear com `pd.to_datetime` genérico
4. Descarta datas fora do intervalo `1900–2100` (datas inválidas da RFB)
5. Retorna no formato `YYYY-MM-DD` ou `None`

```python
# Exemplo
chunk["data_opcao"] = "20230102"  # → "2023-01-02"
chunk["data_opcao"] = "00000000"  # → None (descartado)
chunk["data_opcao"] = ""          # → None
```

---

### etl/utils/file_hash.py

#### `calculate_file_hash(file_path, algorithm="sha256")`

Calcula o hash do arquivo em blocos de 8KB para não carregar o arquivo inteiro na memória:

```python
hash = calculate_file_hash(Path("Empresas0.zip"))
# → "a3f5c8d2e1b4..."  (SHA-256 hex)
```

Usado pelo orchestrator para detectar se um arquivo já foi processado com sucesso.

---

## Rastreamento de Importações

Cada execução do ETL registra seu status na tabela `importacoes`:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | int | ID autoincrement |
| `nome_arquivo` | text | Nome do arquivo ZIP |
| `hash_arquivo` | text | SHA-256 do arquivo |
| `status` | text | Status da importação |
| `registros_processados` | int | Total de linhas processadas |
| `registros_inseridos` | int | Total de linhas inseridas/atualizadas |

### Status possíveis

| Status | Significado |
|--------|-------------|
| `PROCESSING` | Em andamento |
| `SUCCESS` | Concluído com todos os tipos de arquivo |
| `PARTIAL` | Concluído, mas faltaram tipos auxiliares (ex: sem CNAE) |
| `FAILED` | Erro durante o processamento |

### Lógica de deduplicação

```
Novo arquivo ZIP
      │
      ▼
Calcular SHA-256
      │
      ▼
SELECT 1 FROM importacoes
WHERE hash_arquivo = :hash
  AND status = 'SUCCESS'
  AND (registros_processados > 0 OR registros_inseridos > 0)
      │
  ┌───┴───────────────┐
Existe?            Não existe
  │                    │
  ▼                    ▼
Ignorar arquivo    Processar
(loga e move)
```

Para forçar reprocessamento mesmo que o hash exista, use o flag `--force`.

---

## Configuração

Variáveis de ambiente relevantes para o ETL (definidas no `.env`):

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | — | URL de conexão PostgreSQL (obrigatória) |
| `RAW_DATA_PATH` | `data/raw` | Diretório com os ZIPs da RFB |
| `STAGING_PATH` | `data/staging` | Diretório temporário de extração |
| `PROCESSED_PATH` | `data/processed` | Diretório de arquivos processados |
| `BATCH_SIZE` | `50000` | Linhas por chunk do Pandas |
| `ETL_HASH_ALGORITHM` | `sha256` | Algoritmo de hash (sha256 ou md5) |

---

## Como Executar

### Execução padrão

```bash
# Ativa o virtualenv
source .venv/bin/activate

# Executa o ETL (processa todos os ZIPs em data/raw/)
PYTHONPATH=. python -m etl.orchestrator
```

### Forçar reprocessamento (ignora hash)

```bash
PYTHONPATH=. python -m etl.orchestrator --force
```

### Acompanhar progresso em background

```bash
PYTHONPATH=. nohup python -m etl.orchestrator > /tmp/etl.log 2>&1 &
tail -f /tmp/etl.log
```

### Verificar status das importações no banco

```sql
SELECT
    nome_arquivo,
    status,
    registros_processados,
    registros_inseridos
FROM importacoes
ORDER BY id DESC
LIMIT 20;
```

---

## Como Adicionar um Novo Processador

Siga este passo a passo para adicionar suporte a um novo tipo de arquivo da RFB:

### 1. Criar o processador em `etl/processors/novo_processor.py`

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from app.config import settings
from app.database import engine as default_engine
from etl.utils.postgres_copy import copy_dataframe_to_staging, quote_ident, upsert_from_staging

# 1. Definir colunas do CSV conforme especificação da RFB
CSV_COLUMNS = ["codigo", "descricao"]

# 2. Definir colunas que serão inseridas no banco
INSERT_COLUMNS = ["codigo", "descricao"]

STAGING_TABLE = "stg_novo"
TARGET_TABLE  = "novo"


def _ensure_staging_table(engine: Engine) -> None:
    sql = f"""
        CREATE TABLE IF NOT EXISTS {quote_ident(STAGING_TABLE)} (
            codigo TEXT,
            descricao TEXT
        )
    """
    with engine.begin() as connection:
        connection.execute(text(sql))


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.copy()
    for col in chunk.columns:
        chunk[col] = chunk[col].astype("string").str.strip()
    chunk = chunk.replace({"": None, pd.NA: None})
    return chunk[INSERT_COLUMNS].dropna(subset=["codigo"])


def process_novo_csv(
    file_path: str | Path,
    engine: Engine = default_engine,
    chunk_size: int = settings.BATCH_SIZE,
) -> int:
    _ensure_staging_table(engine)

    try:
        chunks = pd.read_csv(
            file_path,
            sep=";",
            dtype=str,
            encoding="latin1",
            chunksize=chunk_size,
            usecols=CSV_COLUMNS,
            keep_default_na=False,
        )
    except ValueError:
        # CSV sem header — mapeia por posição
        chunks = pd.read_csv(
            file_path,
            sep=";",
            dtype=str,
            encoding="latin1",
            chunksize=chunk_size,
            header=None,
            names=CSV_COLUMNS,
            usecols=list(range(len(CSV_COLUMNS))),
            keep_default_na=False,
        )

    processed = 0
    for chunk in chunks:
        prepared = _prepare_chunk(chunk)
        if prepared.empty:
            continue
        copy_dataframe_to_staging(engine, prepared, STAGING_TABLE)
        upsert_from_staging(
            engine,
            staging_table=STAGING_TABLE,
            target_table=TARGET_TABLE,
            insert_columns=INSERT_COLUMNS,
            conflict_columns=["codigo"],
        )
        processed += len(prepared)

    return processed
```

### 2. Criar a migration Alembic

```bash
alembic revision -m "add_novo_table"
```

Edite o arquivo gerado em `migrations/versions/`:

```python
def upgrade() -> None:
    op.create_table(
        "novo",
        sa.Column("codigo", sa.String(), primary_key=True),
        sa.Column("descricao", sa.Text(), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("novo")
```

```bash
alembic upgrade head
```

### 3. Registrar no orchestrator

Em `etl/orchestrator.py`:

```python
# Adicionar import
from etl.processors.novo_processor import process_novo_csv

# Adicionar na classificação
def _classify_name(file_name: str) -> str | None:
    ...
    if "NOVO" in upper:   # padrão do nome do arquivo RFB
        return "novo"
    ...

# Adicionar no dict de extracted
extracted: dict[str, list[Path]] = {
    ...
    "novo": [],
}

# Adicionar no loop de processamento
for file_path in extracted["novo"]:
    total_processed += process_novo_csv(file_path)

# Se for tipo obrigatório, adicionar em REQUIRED_AUXILIARY_TYPES
REQUIRED_AUXILIARY_TYPES = {
    ...
    "novo",
}
```

---

## Decisões de Design

### Por que COPY + UPSERT em vez de INSERT direto?

O `COPY FROM STDIN` do PostgreSQL é **10-50x mais rápido** que INSERT row-by-row. Para 57 milhões de registros, isso reduz o tempo de carga de horas para minutos.

O fluxo staging → upsert separa a responsabilidade:
- `COPY` → máxima velocidade de ingestão
- `INSERT ... ON CONFLICT` → garante idempotência

### Por que tabelas de staging?

Permitem:
1. Carregar dados brutos sem checar conflitos (mais rápido)
2. Deduplicar com `DISTINCT ON` antes do upsert
3. Rollback simples: se o upsert falhar, a staging é truncada e o dado não foi para produção

### Por que chunks de 50k linhas?

Equilíbrio entre uso de memória e overhead de transação. Com arquivos de 10M+ linhas, carregar tudo de uma vez exigiria >16GB de RAM. Chunks de 50k usam ~200MB por vez.

### Por que SHA-256 por arquivo e não por linha?

Verificar hash de linha exigiria ler e hashear 57M registros antes de qualquer importação. Hash do arquivo ZIP é O(1) em termos de complexidade e suficiente para detectar reprocessamento.

### Por que a ordem importa no orchestrator?

```
empresas → estabelecimentos → socios → tabelas de referência
```

Na prática, o PostgreSQL não valida foreign keys via `ON CONFLICT` nesta implementação, mas a ordem semântica é mantida para clareza. As tabelas de referência podem ser carregadas em qualquer ordem pois não têm dependência entre si.

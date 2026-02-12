# SPEC.md — Sistema CNPJ (MVP controlado)

## Objetivo
Importar ZIPs da Receita Federal (CNPJ) para PostgreSQL e permitir busca via API FastAPI.

---

## Escopo MVP (único permitido)

### Backend
- FastAPI
- PostgreSQL
- SQLAlchemy + Alembic
- Pandas (chunks)
- structlog

### ETL
ZIP → CSV → staging → COPY → UPSERT

### API
- GET /api/v1/cnpj/{cnpj}
- GET /api/v1/empresas/search
- GET /api/v1/health

---

## Contrato de arquivos

### EMPRE
cnpj_basico;razao_social;natureza_juridica;qualificacao_responsavel;capital_social;porte_empresa;ente_federativo

### ESTABELE
cnpj_basico;cnpj_ordem;cnpj_dv;matriz_filial;nome_fantasia;situacao;data_situacao;motivo;cidade_exterior;pais;inicio;cnae_principal;cnae_secundario;tipo_logradouro;logradouro;numero;complemento;bairro;cep;uf;municipio;ddd1;telefone1;ddd2;telefone2;email;situacao_especial;data_situacao_especial

### SOCIO
cnpj_basico;tipo;nome;cpf_cnpj;qualificacao;data_entrada;pais;cpf_rep;nome_rep;qualificacao_rep;faixa_etaria

---

## Banco de dados

### empresas
- cnpj_basico PK
- razao_social
- natureza_juridica
- capital_social
- porte_empresa

### estabelecimentos
- id PK
- cnpj_completo UNIQUE
- cnpj_basico FK
- nome_fantasia
- situacao
- uf
- municipio

### socios
- id PK
- cnpj_basico FK
- nome_socio
- cpf_cnpj_socio

### importacoes
- id
- nome_arquivo
- hash_arquivo
- status
- registros_processados

---

## Regras ETL

- SHA256 para evitar reprocessamento
- COPY + UPSERT
- chunk de 50k
- datas inválidas viram NULL
- strings vazias viram NULL

---

## Busca

- Full Text Search PostgreSQL
- ordenação por relevância

---

## Estrutura mínima

app/
etl/
alembic/
data/

---

## Fora de escopo (não implementar)

- Redis
- Prometheus
- autenticação
- particionamento
- admin endpoints

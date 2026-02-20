# API de Consulta CNPJ — Documentação de Integração

> Dados públicos da Receita Federal servidos via REST API com autenticação por API Key.

---

## Sumário

- [Autenticação](#autenticação)
- [URL Base](#url-base)
- [Rate Limiting](#rate-limiting)
- [Formato de Resposta](#formato-de-resposta)
- [Endpoints](#endpoints)
  - [Health Check](#1-health-check)
  - [Consultar CNPJ](#2-consultar-cnpj)
  - [Consulta em Lote](#3-consulta-em-lote-batch)
  - [Buscar Empresas](#4-buscar-empresas)
- [Códigos de Erro](#códigos-de-erro)
- [Exemplos de Integração](#exemplos-de-integração)

---

## Autenticação

Todos os endpoints (exceto `/health`) requerem uma API Key enviada no header da requisição.

```
X-API-Key: sua_chave_aqui
```

Sem a chave ou com chave inválida, a resposta será:

```json
HTTP/1.1 401 Unauthorized

{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "API Key invalida ou ausente"
  }
}
```

---

## URL Base

```
http://<seu-servidor>:8000/api/v1
```

Em ambiente de desenvolvimento, a documentação interativa (Swagger UI) está disponível em:

```
http://<seu-servidor>:8000/docs
```

---

## Rate Limiting

Limites por IP por minuto:

| Endpoint | Limite |
|----------|--------|
| `GET /cnpj/{cnpj}` | 60 req/min |
| `POST /cnpj/batch` | 10 req/min |
| `GET /empresas/search` | 30 req/min |
| `GET /health` | 120 req/min |

Ao exceder o limite:

```json
HTTP/1.1 429 Too Many Requests

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Limite de requisições excedido"
  }
}
```

---

## Formato de Resposta

Todas as respostas são JSON com `Content-Type: application/json`.

Erros seguem sempre o mesmo envelope:

```json
{
  "error": {
    "code": "CODIGO_DO_ERRO",
    "message": "Descrição legível do erro",
    "request_id": "uuid-para-rastreamento"
  }
}
```

---

## Endpoints

---

### 1. Health Check

Verifica disponibilidade da API, banco de dados e cache.

```
GET /api/v1/health
```

**Autenticação:** Não requerida

**Resposta de sucesso:**

```json
HTTP/1.1 200 OK

{
  "status": "ok",
  "database": "ok",
  "cache": "ok",
  "version": "1.0.0",
  "uptime_seconds": 3600.5
}
```

**Campos de status:**

| Campo | Valores possíveis |
|-------|------------------|
| `status` | `ok`, `degraded`, `unhealthy` |
| `database` | `ok`, `unavailable` |
| `cache` | `ok`, `unavailable`, `disabled` |

- `degraded` → banco respondeu mas levou mais de 200ms
- `unhealthy` → banco inacessível (resposta HTTP 503)

---

### 2. Consultar CNPJ

Retorna dados completos de uma empresa: informações cadastrais, estabelecimentos e sócios.

```
GET /api/v1/cnpj/{cnpj}
```

**Autenticação:** Requerida (`X-API-Key`)

**Parâmetros de path:**

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj` | string | CNPJ com 8 dígitos (raiz) ou 14 dígitos (completo). Aceita formatado (com `.`, `/`, `-`) ou apenas números. |

**Exemplos de CNPJ aceitos:**
- `33000167000101` — 14 dígitos sem formatação
- `33.000.167/0001-01` — 14 dígitos formatado
- `33000167` — 8 dígitos (retorna todos os estabelecimentos da empresa)

**Comportamento por tamanho:**
- **8 dígitos:** retorna a empresa + **todos** os seus estabelecimentos + sócios
- **14 dígitos:** retorna a empresa + **apenas o estabelecimento** do CNPJ informado + sócios

**Resposta de sucesso:**

```json
HTTP/1.1 200 OK

{
  "empresa": {
    "cnpj_basico": "33000167",
    "razao_social": "PETROLEO BRASILEIRO S A PETROBRAS",
    "natureza_juridica": "2038",
    "natureza_juridica_descricao": "Sociedade Anônima Aberta",
    "capital_social": "205431960490.52",
    "porte_empresa": "05",
    "opcao_pelo_simples": "N",
    "data_opcao_pelo_simples": null,
    "data_exclusao_do_simples": null,
    "opcao_pelo_mei": "N",
    "data_opcao_pelo_mei": null,
    "data_exclusao_do_mei": null
  },
  "estabelecimentos": [
    {
      "id": 1,
      "cnpj_completo": "33000167000101",
      "cnpj_basico": "33000167",
      "nome_fantasia": "PETROBRAS",
      "situacao": "02",
      "uf": "RJ",
      "municipio": "6001",
      "municipio_descricao": "RIO DE JANEIRO",
      "cnae_principal": "0600001",
      "cnae_principal_descricao": "Extração de petróleo e gás natural",
      "cnae_secundario": "3520401;3600601",
      "pais": null,
      "pais_descricao": null,
      "motivo": null,
      "motivo_descricao": null
    }
  ],
  "socios": [
    {
      "id": 1,
      "cnpj_basico": "33000167",
      "nome_socio": "JEAN PAUL TERRA PRATES",
      "cpf_cnpj_socio": "***123456**",
      "qualificacao": "05",
      "qualificacao_descricao": "Administrador",
      "pais": null,
      "pais_descricao": null,
      "data_entrada": "2023-01-02"
    }
  ]
}
```

**Campos da Empresa:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cnpj_basico` | string | CNPJ raiz com 8 dígitos |
| `razao_social` | string\|null | Razão social |
| `natureza_juridica` | string\|null | Código da natureza jurídica |
| `natureza_juridica_descricao` | string\|null | Descrição da natureza jurídica |
| `capital_social` | string\|null | Capital social declarado |
| `porte_empresa` | string\|null | Código do porte (`00`=Não informado, `01`=Micro, `03`=Pequena, `05`=Demais) |
| `opcao_pelo_simples` | string\|null | `S`=Sim, `N`=Não |
| `data_opcao_pelo_simples` | date\|null | Data de opção pelo Simples Nacional |
| `data_exclusao_do_simples` | date\|null | Data de exclusão do Simples Nacional |
| `opcao_pelo_mei` | string\|null | `S`=Sim, `N`=Não |
| `data_opcao_pelo_mei` | date\|null | Data de opção pelo MEI |
| `data_exclusao_do_mei` | date\|null | Data de exclusão do MEI |

**Campos do Estabelecimento:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | int | ID interno |
| `cnpj_completo` | string | CNPJ completo com 14 dígitos |
| `cnpj_basico` | string | CNPJ raiz com 8 dígitos |
| `nome_fantasia` | string\|null | Nome fantasia |
| `situacao` | string\|null | Código da situação (`01`=Nula, `02`=Ativa, `03`=Suspensa, `04`=Inapta, `08`=Baixada) |
| `uf` | string\|null | UF do estabelecimento |
| `municipio` | string\|null | Código do município (IBGE) |
| `municipio_descricao` | string\|null | Nome do município |
| `cnae_principal` | string\|null | Código CNAE principal |
| `cnae_principal_descricao` | string\|null | Descrição da atividade principal |
| `cnae_secundario` | string\|null | Códigos CNAE secundários separados por `;` |
| `pais` | string\|null | Código do país (para empresas estrangeiras) |
| `pais_descricao` | string\|null | Nome do país |
| `motivo` | string\|null | Código do motivo da situação |
| `motivo_descricao` | string\|null | Descrição do motivo |

**Campos do Sócio:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | int | ID interno |
| `cnpj_basico` | string | CNPJ raiz da empresa |
| `nome_socio` | string\|null | Nome do sócio ou razão social |
| `cpf_cnpj_socio` | string\|null | CPF/CNPJ mascarado conforme divulgado pela RFB |
| `qualificacao` | string\|null | Código de qualificação |
| `qualificacao_descricao` | string\|null | Descrição da qualificação |
| `pais` | string\|null | Código do país do sócio estrangeiro |
| `pais_descricao` | string\|null | Nome do país |
| `data_entrada` | date\|null | Data de entrada na sociedade |

**Erros:**

| HTTP | Código | Situação |
|------|--------|----------|
| 400 | `VALIDATION_ERROR` | CNPJ com tamanho inválido |
| 401 | `UNAUTHORIZED` | API Key ausente ou inválida |
| 404 | `NOT_FOUND` | CNPJ não encontrado na base |
| 429 | `RATE_LIMIT_EXCEEDED` | Limite de requisições excedido |
| 500 | `INTERNAL_ERROR` | Erro interno |
| 503 | `SERVICE_UNAVAILABLE` | Banco de dados indisponível |

---

### 3. Consulta em Lote (Batch)

Consulta múltiplos CNPJs em uma única requisição. Utiliza cache Redis para otimização.

```
POST /api/v1/cnpj/batch
Content-Type: application/json
X-API-Key: sua_chave_aqui
```

**Autenticação:** Requerida (`X-API-Key`)

**Corpo da requisição:**

```json
{
  "cnpjs": [
    "33000167000101",
    "00000000000191",
    "11111111000191"
  ]
}
```

| Campo | Tipo | Regras |
|-------|------|--------|
| `cnpjs` | array de strings | Mínimo 1, máximo 1000 itens. Aceita 8 ou 14 dígitos, formatado ou não. |

**Resposta de sucesso:**

```json
HTTP/1.1 200 OK

{
  "resultados": {
    "33000167000101": {
      "empresa": { ... },
      "estabelecimentos": [ ... ],
      "socios": [ ... ]
    }
  },
  "nao_encontrados": [
    "00000000000191",
    "11111111000191"
  ],
  "total": 3,
  "encontrados": 1
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `resultados` | object | Mapa de CNPJ → dados. A chave é o CNPJ exatamente como foi enviado na requisição. |
| `nao_encontrados` | array | CNPJs não encontrados na base ou com formato inválido |
| `total` | int | Total de CNPJs enviados na requisição |
| `encontrados` | int | Total de CNPJs encontrados |

> **Atenção:** CNPJs inválidos (diferente de 8 ou 14 dígitos) são automaticamente movidos para `nao_encontrados`.

**Cache:** Resultados de batch são cacheados por CNPJ raiz. Requisições subsequentes com os mesmos CNPJs são servidas do cache sem bater no banco.

---

### 4. Buscar Empresas

Busca empresas por razão social usando full-text search em português.

```
GET /api/v1/empresas/search?q={termo}&page={pagina}&page_size={itens}
```

**Autenticação:** Requerida (`X-API-Key`)

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|-----------|------|-------------|--------|-----------|
| `q` | string | Sim | — | Termo de busca (1–200 caracteres) |
| `page` | int | Não | `1` | Página atual (mínimo 1) |
| `page_size` | int | Não | `20` | Itens por página (1–100) |

**Resposta de sucesso:**

```json
HTTP/1.1 200 OK

{
  "resultados": [
    {
      "cnpj_basico": "33000167",
      "razao_social": "PETROLEO BRASILEIRO S A PETROBRAS",
      "natureza_juridica": "2038",
      "capital_social": "205431960490.52",
      "porte_empresa": "05",
      "relevancia": 0.0759906
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `resultados` | array | Lista de empresas encontradas |
| `relevancia` | float | Score de relevância do full-text search (maior = mais relevante) |
| `total` | int | Total de registros encontrados |
| `page` | int | Página atual |
| `page_size` | int | Itens por página |
| `pages` | int | Total de páginas |

> **Nota:** O campo `relevancia` é exclusivo deste endpoint. A busca usa o dicionário `portuguese` do PostgreSQL, suportando stemming (ex: "petróleo" encontra "petroleo").

---

## Códigos de Erro

| HTTP | Código | Descrição |
|------|--------|-----------|
| `401` | `UNAUTHORIZED` | API Key ausente ou inválida |
| `404` | `NOT_FOUND` | Recurso não encontrado |
| `422` | `VALIDATION_ERROR` | Dados de entrada inválidos |
| `429` | `RATE_LIMIT_EXCEEDED` | Limite de requisições excedido |
| `500` | `INTERNAL_ERROR` | Erro interno inesperado |
| `503` | `SERVICE_UNAVAILABLE` | Banco de dados indisponível |

---

## Exemplos de Integração

### cURL

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Consultar CNPJ completo
curl -H "X-API-Key: sua_chave" \
  http://localhost:8000/api/v1/cnpj/33000167000101

# Consultar por CNPJ raiz (todos os estabelecimentos)
curl -H "X-API-Key: sua_chave" \
  http://localhost:8000/api/v1/cnpj/33000167

# Batch
curl -X POST \
  -H "X-API-Key: sua_chave" \
  -H "Content-Type: application/json" \
  -d '{"cnpjs": ["33000167000101", "60701190000104"]}' \
  http://localhost:8000/api/v1/cnpj/batch

# Busca por nome
curl -H "X-API-Key: sua_chave" \
  "http://localhost:8000/api/v1/empresas/search?q=petrobras&page=1&page_size=10"
```

---

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "sua_chave"}

# Consultar CNPJ
response = requests.get(f"{BASE_URL}/cnpj/33000167000101", headers=HEADERS)
data = response.json()

empresa = data["empresa"]
print(empresa["razao_social"])  # PETROLEO BRASILEIRO S A PETROBRAS

# Batch
cnpjs = ["33000167000101", "60701190000104", "00000000000000"]
response = requests.post(
    f"{BASE_URL}/cnpj/batch",
    headers=HEADERS,
    json={"cnpjs": cnpjs},
)
batch = response.json()
print(f"Encontrados: {batch['encontrados']}/{batch['total']}")
print(f"Não encontrados: {batch['nao_encontrados']}")

# Busca paginada
response = requests.get(
    f"{BASE_URL}/empresas/search",
    headers=HEADERS,
    params={"q": "petrobras", "page": 1, "page_size": 20},
)
busca = response.json()
for empresa in busca["resultados"]:
    print(empresa["razao_social"], empresa["relevancia"])
```

---

### JavaScript / Node.js

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';
const HEADERS = { 'X-API-Key': 'sua_chave' };

// Consultar CNPJ
const res = await fetch(`${BASE_URL}/cnpj/33000167000101`, { headers: HEADERS });
const data = await res.json();
console.log(data.empresa.razao_social);

// Batch
const batch = await fetch(`${BASE_URL}/cnpj/batch`, {
  method: 'POST',
  headers: { ...HEADERS, 'Content-Type': 'application/json' },
  body: JSON.stringify({ cnpjs: ['33000167000101', '60701190000104'] }),
});
const result = await batch.json();
console.log(`Encontrados: ${result.encontrados}/${result.total}`);

// Busca
const search = await fetch(
  `${BASE_URL}/empresas/search?q=petrobras&page=1&page_size=10`,
  { headers: HEADERS }
);
const empresas = await search.json();
empresas.resultados.forEach(e => console.log(e.razao_social));
```

---

### PHP

```php
<?php
$baseUrl = 'http://localhost:8000/api/v1';
$apiKey  = 'sua_chave';

// Consultar CNPJ
$ch = curl_init("$baseUrl/cnpj/33000167000101");
curl_setopt($ch, CURLOPT_HTTPHEADER, ["X-API-Key: $apiKey"]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$data = json_decode(curl_exec($ch), true);
echo $data['empresa']['razao_social'];

// Batch
$ch = curl_init("$baseUrl/cnpj/batch");
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "X-API-Key: $apiKey",
    "Content-Type: application/json",
]);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    'cnpjs' => ['33000167000101', '60701190000104'],
]));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$result = json_decode(curl_exec($ch), true);
echo "Encontrados: {$result['encontrados']}/{$result['total']}";
```

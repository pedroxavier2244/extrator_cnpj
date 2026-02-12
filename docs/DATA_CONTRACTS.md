# DATA_CONTRACTS

## Fonte analisada
- Base: `data/staging/2026-01`
- Método: leitura direta dos ZIPs auxiliares e amostragem das 5 primeiras linhas de cada entrada.
- Observação: todos os CSVs auxiliares analisados não possuem header explícito; contratos abaixo são inferidos por posição e padrão dos valores.

## cnaes
- Arquivo: `data/staging/2026-01/Cnaes.zip` -> `F.K03200$Z.D60110.CNAECSV`
- Nº de colunas: 2 (constante nas 5 linhas)
- 5 primeiras linhas:
  - `"0111301";"Cultivo de arroz"`
  - `"0111302";"Cultivo de milho"`
  - `"0111303";"Cultivo de trigo"`
  - `"0111399";"Cultivo de outros cereais não especificados anteriormente"`
  - `"0112101";"Cultivo de algodão herbáceo"`
- Contrato proposto:
  - Tabela: `cnaes`
  - Colunas: `codigo` (TEXT), `descricao` (TEXT)
- UPSERT key: `codigo`
- Merge: atualizar `descricao`

## motivos
- Arquivo: `data/staging/2026-01/Motivos.zip` -> `F.K03200$Z.D60110.MOTICSV`
- Nº de colunas: 2
- 5 primeiras linhas:
  - `"00";"SEM MOTIVO"`
  - `"01";"EXTINCAO POR ENCERRAMENTO LIQUIDACAO VOLUNTARIA"`
  - `"02";"INCORPORACAO"`
  - `"03";"FUSAO"`
  - `"04";"CISAO TOTAL"`
- Contrato proposto:
  - Tabela: `motivos`
  - Colunas: `codigo` (TEXT), `descricao` (TEXT)
- UPSERT key: `codigo`
- Merge: atualizar `descricao`

## municipios
- Arquivo: `data/staging/2026-01/Municipios.zip` -> `F.K03200$Z.D60110.MUNICCSV`
- Nº de colunas: 2
- 5 primeiras linhas:
  - `"0001";"GUAJARA-MIRIM"`
  - `"0002";"ALTO ALEGRE DOS PARECIS"`
  - `"0003";"PORTO VELHO"`
  - `"0004";"BURITIS"`
  - `"0005";"JI-PARANA"`
- Contrato proposto:
  - Tabela: `municipios`
  - Colunas: `codigo` (TEXT), `descricao` (TEXT)
- UPSERT key: `codigo`
- Merge: atualizar `descricao`

## naturezas
- Arquivo: `data/staging/2026-01/Naturezas.zip` -> `F.K03200$Z.D60110.NATJUCSV`
- Nº de colunas: 2
- 5 primeiras linhas:
  - `"0000";"Natureza Jurídica não informada"`
  - `"3271";"Órgão de Direção Local de Partido Político"`
  - `"3280";"Comitê Financeiro de Partido Político"`
  - `"3298";"Frente Plebiscitária ou Referendária"`
  - `"3301";"Organização Social (OS)"`
- Contrato proposto:
  - Tabela: `naturezas`
  - Colunas: `codigo` (TEXT), `descricao` (TEXT)
- UPSERT key: `codigo`
- Merge: atualizar `descricao`

## paises
- Arquivo: `data/staging/2026-01/Paises.zip` -> `F.K03200$Z.D60110.PAISCSV`
- Nº de colunas: 2
- 5 primeiras linhas:
  - `"000";"COLIS POSTAUX"`
  - `"013";"AFEGANISTAO"`
  - `"017";"ALBANIA"`
  - `"020";"ALBORAN-PEREJIL,ILHAS"`
  - `"023";"ALEMANHA"`
- Contrato proposto:
  - Tabela: `paises`
  - Colunas: `codigo` (TEXT), `descricao` (TEXT)
- UPSERT key: `codigo`
- Merge: atualizar `descricao`

## qualificacoes
- Arquivo: `data/staging/2026-01/Qualificacoes.zip` -> `F.K03200$Z.D60110.QUALSCSV`
- Nº de colunas: 2
- 5 primeiras linhas:
  - `"00";"Não informada"`
  - `"05";"Administrador"`
  - `"08";"Conselheiro de Administração"`
  - `"09";"Curador"`
  - `"10";"Diretor"`
- Contrato proposto:
  - Tabela: `qualificacoes`
  - Colunas: `codigo` (TEXT), `descricao` (TEXT)
- UPSERT key: `codigo`
- Merge: atualizar `descricao`

## simples
- Arquivo: `data/staging/2026-01/Simples.zip` -> `F.K03200$W.SIMPLES.CSV.D60110`
- Nº de colunas: 7
- 5 primeiras linhas:
  - `"00000000";"N";"20070701";"20070701";"N";"20090701";"20090701"`
  - `"00000006";"N";"20180101";"20191231";"N";"00000000";"00000000"`
  - `"00000008";"N";"20140101";"20211231";"N";"00000000";"00000000"`
  - `"00000011";"S";"20070701";"00000000";"N";"00000000";"00000000"`
  - `"00000013";"N";"20090101";"20231231";"N";"00000000";"00000000"`
- Contrato proposto (inferência por posição, sem header no arquivo):
  - Tabela: `simples`
  - Colunas: `cnpj_basico` (TEXT), `col_2` (TEXT), `col_3` (TEXT), `col_4` (TEXT), `col_5` (TEXT), `col_6` (TEXT), `col_7` (TEXT)
- UPSERT key: `cnpj_basico`
- Merge: atualizar `col_2..col_7`
- Ambiguidade: nomes semânticos das colunas 2..7 não podem ser confirmados apenas pelo arquivo (sem header).

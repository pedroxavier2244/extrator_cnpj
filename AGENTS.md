# AGENTS.md — Regras obrigatórias para IA neste repositório

## 1) Regra principal (anti-alucinação)
- Não invente requisitos, tabelas, endpoints ou bibliotecas.
- Tudo deve vir exclusivamente de SPEC.md.

## 2) Escopo
- Implemente somente o MVP descrito em SPEC.md.
- Tudo que estiver marcado como Fase 2 é proibido sem pedido explícito.

## 3) Dependências
- Use apenas as bibliotecas listadas no requirements.txt do MVP.
- Se algo faltar, pare e pergunte antes de codar.

## 4) Forma de trabalho
- Gere um arquivo por vez.
- Retorne somente código (sem explicações) quando solicitado.
- Não reescreva arquivos sem necessidade.

## 5) Quando perguntar
Pergunte se faltar:
- schema dos CSVs
- chaves de UPSERT
- paths
- conexão de banco

## 6) Prioridade
Se houver conflito entre exemplos e regras:
➡️ sempre seguir SPEC.md

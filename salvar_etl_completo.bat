@echo off
setlocal enabledelayedexpansion

echo [1/7] Subindo containers...
docker compose up -d --build
if errorlevel 1 goto :error

echo [2/7] Aplicando migrations...
docker exec -i cnpj_api python -m alembic -c /app/alembic.ini upgrade head
if errorlevel 1 goto :error

echo [3/7] Limpando importacoes travadas (PROCESSING -> FAILED)...
docker exec -i cnpj_postgres psql -U cnpj -d cnpj -c "update importacoes set status='FAILED' where status='PROCESSING';"
if errorlevel 1 goto :error

echo [4/7] Garantindo ZIP em /app/data/raw...
docker exec -i cnpj_api sh -lc "if [ -f /app/data/processed/2026-01.zip ]; then mv -f /app/data/processed/2026-01.zip /app/data/raw/2026-01.zip; fi"
if errorlevel 1 goto :error

echo [5/7] Rodando ETL completo com --force (pode demorar)...
docker exec -i cnpj_api python -m etl.orchestrator --force
if errorlevel 1 goto :error

echo [6/7] Verificando status das importacoes...
docker exec -i cnpj_postgres psql -U cnpj -d cnpj -c "select id,nome_arquivo,status,registros_processados,registros_inseridos from importacoes order by id desc limit 10;"
if errorlevel 1 goto :error

echo [7/7] Verificando contagem das tabelas auxiliares...
docker exec -i cnpj_postgres psql -U cnpj -d cnpj -c "select 'cnaes' as tabela,count(*) as total from cnaes union all select 'motivos',count(*) from motivos union all select 'municipios',count(*) from municipios union all select 'naturezas',count(*) from naturezas union all select 'paises',count(*) from paises union all select 'qualificacoes',count(*) from qualificacoes union all select 'simples',count(*) from simples;"
if errorlevel 1 goto :error

echo.
echo Finalizado com sucesso.
goto :end

:error
echo.
echo Falhou em alguma etapa. Revise o erro acima.
exit /b 1

:end
endlocal
exit /b 0

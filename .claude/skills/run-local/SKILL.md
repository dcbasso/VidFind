---
name: run-local
description: Sobe o VidFind localmente com Docker Compose (meilisearch + web) e confirma que está no ar em http://localhost:8080. Use quando o usuário pedir para rodar, subir, reiniciar ou ver o projeto local, ou depois de mudar templates/config/app.py.
---

# Rodar o VidFind localmente

Objetivo: deixar o app acessível em **http://localhost:8080** reutilizando o índice
Meilisearch já populado (volumes `ad-search_*`). Stack definida em `docker-compose.yml`.

## Pré-requisitos (verificar, não recriar)

1. **`.env` existe** na raiz do projeto (gitignored). Contém `VIDEOS_PATH`,
   `MEILI_MASTER_KEY`, `COMPOSE_PROJECT_NAME=ad-search`, etc.
   - Se não existir: avisar o usuário e parar. Não inventar valores nem expor a
     `MEILI_MASTER_KEY` em nenhum output (mascarar sempre).
2. **Docker** disponível (`docker compose version`).

## Passos

1. **Subir os serviços** (do diretório do projeto):
   ```bash
   docker compose up -d meilisearch web
   ```
   - **Adicionar `--build`** quando `web/app.py`, `web/config.json`, `web/static/**`
     ou `web/templates/**` mudaram — o Dockerfile **copia** os arquivos no build, então
     sem `--build` o container serve código velho:
     ```bash
     docker compose up -d --build meilisearch web
     ```
   - Não subir `indexer`, `whisper-worker` nem `ollama` só para visualizar a tela.

2. **Esperar ficar saudável** (curl com retry embutido — sem `sleep`, que o harness
   bloqueia em foreground):
   ```bash
   curl -s --retry 15 --retry-delay 1 --retry-connrefused --retry-all-errors \
     -o /dev/null -w "web HTTP %{http_code}\n" http://localhost:8080/
   ```

3. **Confirmar** estado e índice:
   ```bash
   docker compose ps
   curl -s http://localhost:8080/api/stats
   ```

4. **Reportar** ao usuário: URL (`http://localhost:8080`), containers de pé e as
   contagens do índice (legendas/cenas/vídeos). Lembrar de dar **F5** se a aba já
   estava aberta antes do rebuild.

## Verificação visual (opcional)

Para screenshot do resultado, usar Playwright do scratchpad
(`node_modules/playwright` + browsers em `~/.cache/ms-playwright`). Se o
`node_modules` sumiu, `npm install playwright` no scratchpad reinstala (browsers já
em cache). Navegar em headless para `http://localhost:8080` e capturar.

## Diagnóstico rápido

- **web caiu / HTTP 000**: `docker compose up -d web` novamente; ver
  `docker compose logs --tail=50 web`.
- **`meilisearch` reiniciando** (uptime baixo): checar `docker compose logs
  meilisearch` — pode ser OOM. Confirmar `restart:` no compose.
- **Mudança não aparece**: faltou `--build` (Dockerfile copia no build).

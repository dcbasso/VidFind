# Ad-Search — Contexto do Projeto

## O que é

**VidFind** — sistema para indexar e buscar por texto o conteúdo falado em vídeos de um acervo local. Transcreve os vídeos com Whisper, salva legendas `.srt`, indexa os segmentos no Meilisearch e expõe uma interface web de busca com retorno de timestamp.

## Arquitetura (4 serviços Docker)

```
ad-search/
├── docker-compose.yml
├── .env                        ← VIDEOS_PATH + MEILI_MASTER_KEY
├── indexer/
│   ├── Dockerfile
│   └── indexer.py              ← pipeline de transcrição e indexação
└── web/
    ├── Dockerfile
    ├── app.py                  ← API Flask (busca + filtros)
    └── templates/index.html    ← frontend de busca
```

| Serviço          | Imagem / Build         | Porta | Função                                      |
|------------------|------------------------|-------|---------------------------------------------|
| `meilisearch`    | getmeili/meilisearch   | 7700  | Motor de busca full-text                    |
| `whisper-worker` | openai-whisper-asr-webservice | 9000 | Transcrição de áudio para SRT via HTTP |
| `indexer`        | ./indexer              | —     | Job único: percorre vídeos, transcreve, indexa |
| `web`            | ./web                  | 8080  | Interface de busca (Flask + Jinja2)         |

## Pipeline do indexador (`indexer/indexer.py`)

1. Aguarda Meilisearch e Whisper ficarem disponíveis
2. Percorre recursivamente `VIDEOS_PATH` buscando `.mp4 / .mov` (ignora pastas ocultas)
3. Para cada vídeo, pula se já tem `.srt` salvo **e** está indexado no Meilisearch
4. Extrai áudio com `ffmpeg` → WAV PCM 16kHz mono (arquivo temporário)
5. Envia o WAV para `POST /asr?output=srt&language=pt` no Whisper
6. Salva o `.srt` em volume separado (`srt_data`), espelhando a estrutura de pastas
7. Parseia o SRT em segmentos e indexa no Meilisearch com os campos:
   - `id` (MD5 do caminho + índice do segmento)
   - `video_path`, `video_name`, `folder`
   - `srt_path`, `start`, `end`, `timestamp`
   - `text` (fala transcrita — campo de busca principal)

## API web (`web/app.py`)

- `GET /` — serve `index.html`
- `GET /video` — serve `video.html` (página de detalhe de vídeo)
- `GET /api/config` — configuração injetável (`web/config.json`)
- `GET /api/search?q=&folder=&limit=` — busca no Meilisearch, retorna hits com texto destacado (`<mark>`)
- `GET /api/search/scenes?q=&folder=&limit=` — busca no índice de cenas
- `GET /api/folders` — lista pastas únicas para o filtro de pasta
- `GET /api/stats` — estatísticas do índice Meilisearch
- `GET /api/videos` — lista vídeos únicos indexados com contagem de segmentos
- `GET /api/transcript?video_path=` — todos os segmentos de um vídeo
- `GET /api/scenes?video_path=` — todas as cenas de um vídeo
- `GET /api/subtitle?video_path=` — download do SRT
- `GET /api/transcript/txt?video_path=` — download do TXT sem timestamps
- `GET /api/scenes/txt?video_path=` — download das descrições de cenas em TXT
- `GET /api/video?path=` — streaming do vídeo com suporte a byte-range
- `GET /api/video?path=&download=1` — download do vídeo

## Frontend

Ver **[FRONTEND.md](FRONTEND.md)** para o SDD completo (temas, componentes, APIs, regras de extensão).

Resumo operacional:
- Configuração injetável em `web/config.json` (logo, título, tema padrão) — não alterar código para personalizar
- Três temas: `dark` / `mid` / `light` — controlados por `data-theme` em `<html>` via CSS variables
- Sidebar redimensionável por drag; largura persistida em `localStorage`
- Rotas frontend: `/` (busca/cenas/vídeos) e `/video?path=&t=` (detalhe)
- Nunca hardcodar cores — usar sempre as CSS variables do sistema de temas

## Templates

```
web/templates/
├── index.html   ← busca, cenas, listagem de vídeos (3 abas)
└── video.html   ← detalhe: player + legenda + cenas (página dedicada)
```

## Configuração essencial (`.env`)

```env
VIDEOS_PATH=/caminho/para/seus/videos
MEILI_MASTER_KEY=sua-chave-secreta-aqui
```

## Comandos principais

```bash
# Sobe serviços persistentes
docker compose up -d meilisearch whisper-worker web

# Roda o indexador (uma vez; retoma de onde parou se interrompido)
docker compose up indexer

# Acompanha logs do indexador
docker compose logs -f indexer

# Reindexa novos vídeos adicionados à pasta
docker compose up indexer
```

## Modelo Whisper em uso

`small` (ASR_ENGINE: faster_whisper) — ~1 GB RAM, qualidade ótima. Hardware alvo: J1800 sem GPU (lento — considere rodar overnight para acervos grandes).

## Detalhes técnicos importantes

- **Idempotência**: o indexador verifica existência do `.srt` no volume E presença no índice antes de reprocessar — seguro para rodar múltiplas vezes.
- **Idioma fixo**: transcrição sempre em `language=pt` (português). Se o acervo mudar de idioma, ajustar a URL no `transcribe()`.
- **Formatos suportados**: `.mp4`, `.MP4`, `.mov`, `.MOV` — definidos em `VIDEO_EXTS`.
- **Timeout ffmpeg**: 5 minutos por vídeo. Timeout Whisper: 30 minutos por arquivo.
- **Índice Meilisearch**: `videos` — atributos pesquisáveis: `text`, `video_name`, `folder`; filtráveis: `video_path`, `folder`; ordenáveis: `start`.

# Ad-Search — Busca em Acervo de Vídeos

Transcreve automaticamente arquivos de vídeo com Whisper e indexa
os segmentos no Meilisearch para busca por texto com retorno de timestamp.

## Estrutura

```
ad-search/
├── docker-compose.yml
├── .env                   ← configure aqui
├── indexer/
│   ├── Dockerfile
│   └── indexer.py         ← transcreve + indexa
└── web/
    ├── Dockerfile
    ├── app.py             ← API Flask
    └── templates/
        └── index.html     ← interface de busca
```

## Configuração

### 1. Edite o `.env`

```env
VIDEOS_PATH=/mnt/publicidade        # caminho real dos vídeos no servidor
MEILI_MASTER_KEY=minha_chave_segura  # troque por algo seguro
```

---

## Primeira vez (instalação)

### 2. Suba os serviços base

```bash
docker compose up -d meilisearch whisper-worker web
```

Aguarde ~30 segundos para os serviços iniciarem.

### 3. Rode o indexador

```bash
docker compose up indexer
```

O indexador vai:
- Percorrer todas as subpastas de `VIDEOS_PATH`
- Enviar cada vídeo ao Whisper para transcrição
- Salvar o `.srt` em volume separado
- Indexar todos os segmentos no Meilisearch

Acompanhe o progresso:

```bash
docker compose logs -f indexer
```

Vídeos já indexados são pulados automaticamente em execuções futuras.

### 4. Acesse a interface

```
http://localhost:8080
```

---

## Atualizar a interface web (após mudanças no código)

Se o código do `web/` foi alterado, reconstrua apenas o contêiner web sem derrubar o Meilisearch:

```bash
docker compose up -d --build web
```

O Meilisearch e o Whisper continuam rodando. Os dados indexados são preservados.

---

## Deploy no servidor (após indexar na máquina local)

Os vídeos já estão no servidor — só precisa levar o índice e as legendas.

### 1. Exportar os volumes na máquina local

```bash
docker run --rm -v ad-search_meili_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/meili_data.tar.gz -C /data .

docker run --rm -v ad-search_srt_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/srt_data.tar.gz -C /data .
```

Isso gera dois arquivos `.tar.gz` na pasta atual.

### 2. Copiar para o servidor

```bash
scp meili_data.tar.gz srt_data.tar.gz usuario@servidor:/caminho/ad-search/
```

Copie também a pasta do projeto (`docker-compose.yml`, `web/`, `indexer/`) se ainda não estiver lá.

### 3. No servidor: ajustar o `.env`

```env
VIDEOS_PATH=/caminho/real/dos/videos/no/servidor
MEILI_MASTER_KEY=minha_chave_segura
```

### 4. No servidor: importar os volumes

```bash
docker run --rm -v ad-search_meili_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/meili_data.tar.gz -C /data

docker run --rm -v ad-search_srt_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/srt_data.tar.gz -C /data
```

### 5. No servidor: subir apenas web + Meilisearch

O Whisper **não precisa** rodar no servidor — a transcrição já foi feita.

```bash
docker compose up -d meilisearch web
```

### 6. Acessar

```
http://<ip-do-servidor>:8080
```

Tudo estará funcionando: busca, player, downloads, legendas.

---

## Adicionar novos vídeos no futuro

Copie os vídeos para a pasta e rode novamente:

```bash
docker compose up indexer
```

Apenas os arquivos novos serão processados.

---

## Outros comandos úteis

```bash
# Ver status de todos os contêineres
docker compose ps

# Parar tudo
docker compose down

# Reiniciar apenas a web
docker compose restart web

# Ver logs da web
docker compose logs -f web

# Acompanhar indexação em andamento
docker compose logs -f indexer
```

---

## O que a interface oferece

| Funcionalidade | Como usar |
|---|---|
| Busca por fala | Tab "Busca" — digite qualquer palavra |
| Filtrar por pasta | Sidebar esquerda |
| Assistir ao trecho exato | Botão "▶ Assistir" no resultado |
| Ver legenda completa | Botão "≡ Legenda" no resultado |
| Baixar legenda (.srt) | Botão "↓ SRT" |
| Baixar transcrição (.txt) | Botão "↓ TXT" — apenas as falas, sem timestamps |
| Baixar vídeo | Botão "↓ Vídeo" |
| Listar todos os vídeos indexados | Tab "Vídeos" |

---

## Portas utilizadas

| Serviço       | Porta |
|--------------|-------|
| Interface web | 8080  |
| Meilisearch   | 7700  |
| Whisper API   | 9000  |

---

## Tempo estimado de transcrição

Com o modelo `small` num J1800 (sem GPU):

| Duração do vídeo | Tempo estimado |
|-----------------|----------------|
| 30 segundos     | ~2–3 min       |
| 1 minuto        | ~4–6 min       |
| 3 minutos       | ~12–18 min     |

Para centenas de vídeos curtos, deixe o indexador rodando overnight.
Ele retoma de onde parou se for interrompido.

---

## Trocar modelo do Whisper

No `docker-compose.yml`, altere `ASR_MODEL`:

| Modelo   | Qualidade  | RAM usada | Velocidade                   |
|----------|------------|-----------|------------------------------|
| `tiny`   | básica     | ~400 MB   | mais rápido                  |
| `base`   | boa        | ~600 MB   | rápido                       |
| `small`  | ótima ✅   | ~1 GB     | moderado                     |
| `medium` | excelente  | ~2 GB     | lento (arriscado no J1800)   |

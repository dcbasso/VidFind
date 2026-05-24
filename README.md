<p align="center">
  <img src="web/assets/logo.png" alt="VidFind" height="56">
</p>

# VidFind — Video Archive Search

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Search your video archive by what was said or what was seen. Powered by Whisper (speech-to-text), LLaVA (scene description) and Meilisearch — returns timestamped results with in-browser playback. Fully self-hosted.

## Structure

```
ad-search/
├── docker-compose.yml
├── .env                   ← configure here
├── indexer/
│   ├── Dockerfile
│   └── indexer.py         ← transcribes + indexes
└── web/
    ├── Dockerfile
    ├── app.py             ← Flask API
    └── templates/
        └── index.html     ← search interface
```

## Configuration

### 1. Edit `.env`

```env
VIDEOS_PATH=/path/to/your/videos   # absolute path to your video archive
MEILI_MASTER_KEY=your-secret-key   # replace with a secure string
OLLAMA_MODEL=llava:13b             # vision model for scene analysis
TIMEBOX_INTERVAL=10                # seconds between analyzed frames
```

See `.env.example` for all available options.

---

## First run (installation)

### 2. Start base services

```bash
docker compose up -d meilisearch whisper-worker web
```

Wait ~30 seconds for the services to start.

### 3. Pull the vision model

```bash
docker compose exec ollama ollama pull llava:13b
```

### 4. Run the indexer

```bash
./reindex.sh
```

Or manually:

```bash
docker compose up indexer
```

The indexer will:
- Walk all subdirectories of `VIDEOS_PATH`
- Send each video to Whisper for transcription
- Save `.srt` files to a separate volume
- Index all speech segments in Meilisearch
- Extract frames every `TIMEBOX_INTERVAL` seconds
- Describe each frame with LLaVA and index the visual descriptions

Track progress:

```bash
docker compose logs -f indexer
```

Already-indexed videos are skipped automatically on future runs.

### 5. Open the interface

```
http://localhost:8080
```

---

## Search modes

| Tab | What it searches |
|---|---|
| **Subtitles** | Spoken words — indexed from Whisper transcription |
| **Scenes** | Visual content — indexed from LLaVA frame descriptions |
| **Videos** | Lists all indexed videos |

---

## Features

| Feature | How to use |
|---|---|
| Search by speech | "Subtitles" tab — type any word |
| Search by scene | "Scenes" tab — describe what you see |
| Filter by folder | Left sidebar |
| Watch exact moment | "▶ Watch" button on result |
| View full transcript | "≡ Subtitles" button on result |
| Download subtitle (.srt) | "↓ SRT" button |
| Download transcript (.txt) | "↓ TXT" button — speech only, no timestamps |
| Download video | "↓ Video" button |

---

## Updating the web interface

If `web/` code was changed, rebuild only the web container:

```bash
docker compose up -d --build web
```

Meilisearch and Whisper keep running. Indexed data is preserved.

---

## Deploy to a server (after indexing locally)

Videos are already on the server — you only need to transfer the index and subtitles.

### 1. Export volumes on local machine

```bash
docker run --rm -v ad-search_meili_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/meili_data.tar.gz -C /data .

docker run --rm -v ad-search_srt_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/srt_data.tar.gz -C /data .
```

### 2. Copy to server

```bash
scp meili_data.tar.gz srt_data.tar.gz user@server:/path/to/ad-search/
```

Also copy the project folder (`docker-compose.yml`, `web/`, `indexer/`) if not already there.

### 3. On the server: adjust `.env`

```env
VIDEOS_PATH=/real/path/to/videos/on/server
MEILI_MASTER_KEY=your-secret-key
```

### 4. On the server: import volumes

```bash
docker run --rm -v ad-search_meili_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/meili_data.tar.gz -C /data

docker run --rm -v ad-search_srt_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/srt_data.tar.gz -C /data
```

### 5. On the server: start web + Meilisearch only

Whisper and Ollama **do not need to run** on the server — transcription and scene analysis are already done.

```bash
docker compose up -d meilisearch web
```

### 6. Access

```
http://<server-ip>:8080
```

---

## Adding new videos

Copy the videos to the folder and run:

```bash
./reindex.sh
```

Only new files will be processed.

---

## Useful commands

```bash
# Check all container statuses
docker compose ps

# Stop everything
docker compose down

# Restart web only
docker compose restart web

# View web logs
docker compose logs -f web

# Monitor indexing progress
docker compose logs -f indexer
```

---

## Ports

| Service       | Port |
|--------------|------|
| Web interface | 8080 |
| Meilisearch   | 7700 |
| Whisper API   | 9000 |
| Ollama        | 11434 |

---

## Transcription time estimates

With `small` model on a J1800 (no GPU):

| Video duration | Estimated time |
|----------------|----------------|
| 30 seconds     | ~2–3 min       |
| 1 minute       | ~4–6 min       |
| 3 minutes      | ~12–18 min     |

For hundreds of short videos, let the indexer run overnight. It resumes from where it left off if interrupted.

---

## Whisper model options

In `docker-compose.yml`, change `ASR_MODEL`:

| Model    | Quality    | RAM usage | Speed                        |
|----------|------------|-----------|------------------------------|
| `tiny`   | basic      | ~400 MB   | fastest                      |
| `base`   | good       | ~600 MB   | fast                         |
| `small`  | great ✅   | ~1 GB     | moderate                     |
| `medium` | excellent  | ~2 GB     | slow                         |

## LLaVA model options

Set `OLLAMA_MODEL` in `.env`:

| Model       | Quality    | VRAM needed | Speed   |
|-------------|------------|-------------|---------|
| `llava:7b`  | good       | ~5–6 GB     | faster  |
| `llava:13b` | better ✅  | ~10–12 GB   | moderate|
| `llava:34b` | best       | ~20 GB      | slow    |

---

## License

MIT License — free to use, modify and distribute.  
If you use or fork this project, please keep the original copyright notice.

© 2025 [Dante Basso](https://github.com/dcbasso) — see [LICENSE](LICENSE) for full terms.

#!/usr/bin/env python3
# VidFind — https://github.com/dcbasso/VidFind
# Copyright (c) 2025 Dante Basso. MIT License.
"""
Indexador de vídeos — VidFind 2025
- Percorre subpastas de VIDEOS_PATH buscando arquivos .mp4 / .MP4
- Ignora pastas ocultas (começando com .)
- Extrai áudio como WAV e envia ao Whisper via API HTTP
- Salva .srt em volume separado (espelhando estrutura)
- Indexa segmentos no Meilisearch com texto + pasta + timestamp
- Extrai frames a cada TIMEBOX_INTERVAL segundos e descreve com LLaVA (Ollama)
- Indexa descrições visuais em índice separado 'video_scenes'
"""

import os
import re
import time
import base64
import hashlib
import subprocess
import tempfile
import requests
import meilisearch
from pathlib import Path
from tqdm import tqdm

VIDEOS_PATH      = os.environ.get("VIDEOS_PATH", "/videos")
SCAN_SUBDIR      = os.environ.get("VIDEO_SCAN_SUBDIR", "")
SRT_PATH         = os.environ.get("SRT_OUTPUT_PATH", "/srt")
MEILI_URL        = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_KEY        = os.environ.get("MEILI_KEY", "changeme123")
WHISPER_URL      = os.environ.get("WHISPER_URL", "http://whisper-worker:9000")
OLLAMA_URL       = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL     = os.environ.get("OLLAMA_MODEL", "llava")
TIMEBOX_INTERVAL = int(os.environ.get("TIMEBOX_INTERVAL", "10"))
INDEX_NAME       = "videos"
SCENES_INDEX     = "video_scenes"

VIDEO_EXTS = {".mp4", ".MP4", ".mov", ".MOV"}

DESCRIBE_PROMPT = (
    "Descreva objetivamente o que está acontecendo nesta cena de vídeo em português. "
    "Mencione pessoas, objetos, ações e ambiente visíveis. Seja conciso (1-2 frases)."
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def srt_time_to_seconds(t: str) -> float:
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_srt(srt_text: str):
    blocks = re.split(r"\n\n+", srt_text.strip())
    segments = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            times = lines[1].split(" --> ")
            start = srt_time_to_seconds(times[0].strip())
            end   = srt_time_to_seconds(times[1].strip())
            text  = " ".join(lines[2:]).strip()
            if text:
                segments.append({"start": start, "end": end, "text": text})
        except Exception:
            continue
    return segments


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def file_id(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()


def wait_for_service(url: str, name: str, retries=20, delay=5):
    print(f"⏳ Aguardando {name}...")
    for i in range(retries):
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                print(f"✅ {name} disponível.")
                return
        except Exception:
            pass
        print(f"   tentativa {i+1}/{retries}...")
        time.sleep(delay)
    raise RuntimeError(f"❌ {name} não respondeu após {retries} tentativas.")


# ── Whisper ───────────────────────────────────────────────────────────────────

def transcribe(video_path: str) -> str | None:
    """Extrai áudio como WAV 16kHz mono e envia para o Whisper."""
    url = f"{WHISPER_URL}/asr?output=srt&language=pt&task=transcribe"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        result = subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            wav_path
        ], capture_output=True, timeout=300)

        if result.returncode != 0:
            print(f"   ❌ ffmpeg falhou: {result.stderr.decode()[:200]}")
            return None

        with open(wav_path, "rb") as f:
            r = requests.post(
                url,
                files={"audio_file": (Path(video_path).stem + ".wav", f, "audio/wav")},
                timeout=1800
            )

        if r.status_code == 200:
            return r.text
        else:
            print(f"   ⚠️  Whisper retornou {r.status_code}")
            return None

    except Exception as e:
        print(f"   ❌ Erro ao transcrever {video_path}: {e}")
        return None
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


# ── Meilisearch ───────────────────────────────────────────────────────────────

def _wait_tasks(client: meilisearch.Client, tasks):
    for task in tasks:
        client.wait_for_task(task.task_uid)


def setup_index(client: meilisearch.Client):
    try:
        client.create_index(INDEX_NAME, {"primaryKey": "id"})
    except Exception:
        pass

    index = client.index(INDEX_NAME)
    _wait_tasks(client, [
        index.update_searchable_attributes(["text", "video_name", "folder"]),
        index.update_filterable_attributes(["video_path", "folder"]),
        index.update_sortable_attributes(["start"]),
    ])
    print(f"✅ Índice '{INDEX_NAME}' configurado.")
    return index


def setup_visual_index(client: meilisearch.Client):
    try:
        client.create_index(SCENES_INDEX, {"primaryKey": "id"})
    except Exception:
        pass

    index = client.index(SCENES_INDEX)
    _wait_tasks(client, [
        index.update_searchable_attributes(["description", "video_name", "folder"]),
        index.update_filterable_attributes(["video_path", "folder"]),
        index.update_sortable_attributes(["start"]),
    ])
    print(f"✅ Índice '{SCENES_INDEX}' configurado.")
    return index


def already_indexed(index, video_path: str) -> bool:
    try:
        results = index.search("", {"filter": f'video_path = "{video_path}"', "limit": 1})
        return len(results["hits"]) > 0
    except Exception:
        return False


# ── Visual analysis (LLaVA / Ollama) ─────────────────────────────────────────

def get_video_duration(video_path: str) -> float | None:
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ], capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return None


def extract_frame(video_path: str, second: float, tmp_dir: str) -> str | None:
    frame_path = os.path.join(tmp_dir, f"frame_{int(second)}.jpg")
    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(second),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "4",
            frame_path
        ], capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(frame_path):
            return frame_path
    except Exception:
        pass
    return None


def describe_frame(frame_path: str) -> str | None:
    try:
        with open(frame_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": DESCRIBE_PROMPT,
            "images": [img_b64],
            "stream": False,
        }
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120,
        )
        if r.status_code == 200:
            return r.json().get("response", "").strip()
    except Exception as e:
        tqdm.write(f"      ⚠️  Ollama erro: {e}")
    return None


def process_visual(video_path: str, index, rel_path: str, folder: str, name: str):
    duration = get_video_duration(video_path)
    if not duration or duration < 1:
        tqdm.write(f"   ⚠️  Não foi possível obter duração do vídeo.")
        return 0

    seconds = [s for s in range(0, int(duration), TIMEBOX_INTERVAL)]
    if not seconds:
        seconds = [0]

    docs = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for sec in seconds:
            frame_path = extract_frame(video_path, float(sec), tmp_dir)
            if not frame_path:
                continue

            description = describe_frame(frame_path)
            if not description:
                continue

            end_sec = min(sec + TIMEBOX_INTERVAL, duration)
            doc_id  = f"scene_{file_id(video_path)}_{sec}"
            docs.append({
                "id":          doc_id,
                "video_path":  video_path,
                "video_name":  name,
                "folder":      folder,
                "start":       float(sec),
                "end":         float(end_sec),
                "timestamp":   format_timestamp(float(sec)),
                "description": description,
            })

            os.remove(frame_path)

    if docs:
        index.add_documents(docs)

    return len(docs)


# ── Walk ignorando pastas ocultas ─────────────────────────────────────────────

def walk_videos(root: str):
    video_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for f in filenames:
            if Path(f).suffix in VIDEO_EXTS:
                video_files.append(os.path.join(dirpath, f))
    return sorted(video_files)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    wait_for_service(f"{MEILI_URL}/health", "Meilisearch")
    wait_for_service(f"{WHISPER_URL}/", "Whisper")
    wait_for_service(f"{OLLAMA_URL}/api/tags", "Ollama")

    client       = meilisearch.Client(MEILI_URL, MEILI_KEY)
    index        = setup_index(client)
    visual_index = setup_visual_index(client)

    scan_root = os.path.join(VIDEOS_PATH, SCAN_SUBDIR) if SCAN_SUBDIR else VIDEOS_PATH
    video_files = walk_videos(scan_root)
    print(f"\n🎬 {len(video_files)} vídeos encontrados em '{scan_root}'\n")

    skipped = 0
    processed = 0
    failed = 0

    for video_path in tqdm(video_files, desc="Processando"):
        rel_path = os.path.relpath(video_path, VIDEOS_PATH)
        folder   = str(Path(rel_path).parent)
        name     = Path(video_path).stem

        srt_dest = os.path.join(SRT_PATH, Path(rel_path).with_suffix(".srt"))

        subtitle_done = os.path.exists(srt_dest) and already_indexed(index, video_path)
        visual_done   = already_indexed(visual_index, video_path)

        if subtitle_done and visual_done:
            skipped += 1
            continue

        tqdm.write(f"\n📼 {rel_path}")

        # ── Legendas ──────────────────────────────────────────────────────────
        if not subtitle_done:
            if not os.path.exists(srt_dest):
                srt_text = transcribe(video_path)
                if not srt_text or not srt_text.strip():
                    tqdm.write(f"   ⚠️  Sem fala detectada.")
                    failed += 1
                else:
                    os.makedirs(os.path.dirname(srt_dest), exist_ok=True)
                    with open(srt_dest, "w", encoding="utf-8") as f:
                        f.write(srt_text)
                    tqdm.write(f"   💾 SRT salvo.")
            else:
                with open(srt_dest, "r", encoding="utf-8") as f:
                    srt_text = f.read()

            if os.path.exists(srt_dest):
                segments = parse_srt(open(srt_dest).read())
                if segments:
                    docs = []
                    for i, seg in enumerate(segments):
                        doc_id = f"{file_id(video_path)}_{i}"
                        docs.append({
                            "id":         doc_id,
                            "video_path": video_path,
                            "video_name": name,
                            "folder":     folder,
                            "srt_path":   srt_dest,
                            "start":      seg["start"],
                            "end":        seg["end"],
                            "timestamp":  format_timestamp(seg["start"]),
                            "text":       seg["text"],
                        })
                    index.add_documents(docs)
                    tqdm.write(f"   ✅ {len(docs)} segmentos de legenda indexados.")
                    processed += 1

        # ── Cenas visuais ─────────────────────────────────────────────────────
        if not visual_done:
            tqdm.write(f"   🎞️  Analisando cenas (intervalo {TIMEBOX_INTERVAL}s)…")
            n_scenes = process_visual(video_path, visual_index, rel_path, folder, name)
            if n_scenes > 0:
                tqdm.write(f"   🖼️  {n_scenes} cenas indexadas.")
            else:
                tqdm.write(f"   ⚠️  Nenhuma cena descrita.")

    print(f"\n{'─'*50}")
    print(f"✅ Processados : {processed}")
    print(f"⏭️  Pulados     : {skipped} (já indexados)")
    print(f"❌ Falhos      : {failed} (sem fala detectada)")
    print(f"{'─'*50}")
    print("🏁 Indexação concluída!")


if __name__ == "__main__":
    main()

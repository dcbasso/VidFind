# VidFind — https://github.com/dcbasso/VidFind
# Copyright (c) 2025 Dante Basso. MIT License.

import os
import json
import subprocess
from pathlib import Path
import requests
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response, abort

app = Flask(__name__)

MEILI_URL   = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_KEY   = os.environ.get("MEILI_KEY", "changeme123")
VIDEOS_PATH = os.environ.get("VIDEOS_PATH", "/videos")
SRT_PATH    = os.environ.get("SRT_PATH", "/srt")
INDEX_NAME   = "videos"
SCENES_INDEX = "video_scenes"

HEADERS = {
    "Authorization": f"Bearer {MEILI_KEY}",
    "Content-Type": "application/json",
}


def _meili_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _safe_resolve(base: str, user_path: str) -> Path:
    base_p = Path(base).resolve()
    full_p = Path(user_path).resolve()
    if str(full_p) != str(base_p) and not str(full_p).startswith(str(base_p) + "/"):
        abort(403)
    return full_p


def _fetch_segments(video_path: str):
    body = {
        "q": "",
        "limit": 10000,
        "filter": f'video_path = "{_meili_escape(video_path)}"',
        "sort": ["start:asc"],
        "attributesToRetrieve": ["start", "end", "timestamp", "text", "srt_path"],
    }
    r = requests.post(
        f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
        headers=HEADERS,
        json=body,
        timeout=30,
    )
    return r.json().get("hits", [])


def _to_srt_time(seconds):
    s = float(seconds)
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _build_srt(segments):
    parts = []
    for i, seg in enumerate(segments, 1):
        start = _to_srt_time(seg.get("start", 0))
        end   = _to_srt_time(seg.get("end", 0))
        text  = seg.get("text", "")
        parts.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(parts)


def _stream_file(filepath, mime):
    """Stream file with byte-range support for video seeking."""
    file_size = filepath.stat().st_size
    range_header = request.headers.get("Range")

    if range_header:
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0]) if byte_range[0] else 0
        end   = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
        end   = min(end, file_size - 1)
        length = end - start + 1

        def generate():
            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return Response(
            generate(),
            status=206,
            mimetype=mime,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    resp = send_file(str(filepath), mimetype=mime, conditional=True)
    resp.headers["Accept-Ranges"] = "bytes"
    return resp


# ── Existing routes ──────────────────────────────────────────────────────────

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(os.path.join(app.root_path, "assets"), filename)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video")
def video_page():
    return render_template("video.html")


@app.route("/api/config")
def app_config():
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path) as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({"logo_url": None, "title": None, "theme": "dark"})


@app.route("/api/search")
def search():
    q      = request.args.get("q", "").strip()
    folder = request.args.get("folder", "").strip()
    limit  = int(request.args.get("limit", 50))

    if not q:
        return jsonify({"hits": [], "total": 0})

    body = {
        "q": q,
        "limit": limit,
        "attributesToHighlight": ["text"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
    }

    if folder:
        body["filter"] = f'folder = "{_meili_escape(folder)}"'

    r = requests.post(
        f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
        headers=HEADERS,
        json=body,
        timeout=10,
    )
    data = r.json()

    hits = []
    for h in data.get("hits", []):
        hits.append({
            "video_name": h.get("video_name"),
            "video_path": h.get("video_path"),
            "folder":     h.get("folder"),
            "timestamp":  h.get("timestamp"),
            "start":      h.get("start"),
            "text":       h.get("_formatted", {}).get("text", h.get("text")),
        })

    return jsonify({"hits": hits, "total": data.get("estimatedTotalHits", len(hits))})


@app.route("/api/folders")
def folders():
    r = requests.post(
        f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
        headers=HEADERS,
        json={"q": "", "limit": 1000, "attributesToRetrieve": ["folder"]},
        timeout=10,
    )
    data = r.json()
    folders_set = sorted({h["folder"] for h in data.get("hits", []) if h.get("folder")})
    return jsonify(folders_set)


@app.route("/api/stats")
def stats():
    r_sub = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}/stats", headers=HEADERS, timeout=5)
    r_vis = requests.get(f"{MEILI_URL}/indexes/{SCENES_INDEX}/stats", headers=HEADERS, timeout=5)
    sub = r_sub.json() if r_sub.ok else {}
    vis = r_vis.json() if r_vis.ok else {}
    return jsonify({
        **sub,
        "sceneDocuments": vis.get("numberOfDocuments", 0),
    })


@app.route("/api/system")
def system_info():
    """System-wide index stats for the "Dados do sistema" dialog.

    Every field is best-effort: any part that fails resolves to null so the
    dialog can still render what is available without breaking the page.
    """
    captions = scenes = None
    last_indexed = None
    try:
        r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}/stats", headers=HEADERS, timeout=5)
        if r.ok:
            captions = r.json().get("numberOfDocuments")
    except Exception:
        pass
    try:
        r = requests.get(f"{MEILI_URL}/indexes/{SCENES_INDEX}/stats", headers=HEADERS, timeout=5)
        if r.ok:
            scenes = r.json().get("numberOfDocuments")
    except Exception:
        pass

    # Unique videos + folders, derived from the videos index in a single query.
    videos = folders = None
    try:
        r = requests.post(
            f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
            headers=HEADERS,
            json={"q": "", "limit": 10000, "attributesToRetrieve": ["video_path", "folder"]},
            timeout=30,
        )
        hits = r.json().get("hits", [])
        videos = len({h.get("video_path") for h in hits if h.get("video_path")})
        folders = len({h.get("folder") for h in hits if h.get("folder")})
    except Exception:
        pass

    # Last indexed: most recent updatedAt reported by Meilisearch.
    try:
        r = requests.get(f"{MEILI_URL}/indexes/{INDEX_NAME}", headers=HEADERS, timeout=5)
        if r.ok:
            last_indexed = r.json().get("updatedAt")
    except Exception:
        pass

    # Disk usage: total size of the video files under VIDEOS_PATH.
    disk_bytes = None
    try:
        base = Path(VIDEOS_PATH)
        if base.exists():
            total = 0
            for p in base.rglob("*"):
                if p.is_file() and p.suffix.lower() in (".mp4", ".mov"):
                    try:
                        total += p.stat().st_size
                    except Exception:
                        pass
            disk_bytes = total
    except Exception:
        pass

    return jsonify({
        "folders": folders,
        "videos": videos,
        "captions": captions,
        "scenes": scenes,
        "last_indexed": last_indexed,
        "disk_bytes": disk_bytes,
    })


@app.route("/api/search/scenes")
def search_scenes():
    q      = request.args.get("q", "").strip()
    folder = request.args.get("folder", "").strip()
    limit  = int(request.args.get("limit", 50))

    if not q:
        return jsonify({"hits": [], "total": 0})

    body = {
        "q": q,
        "limit": limit,
        "attributesToHighlight": ["description"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
    }

    if folder:
        body["filter"] = f'folder = "{_meili_escape(folder)}"'

    r = requests.post(
        f"{MEILI_URL}/indexes/{SCENES_INDEX}/search",
        headers=HEADERS,
        json=body,
        timeout=10,
    )
    data = r.json()

    hits = []
    for h in data.get("hits", []):
        hits.append({
            "video_name":  h.get("video_name"),
            "video_path":  h.get("video_path"),
            "folder":      h.get("folder"),
            "timestamp":   h.get("timestamp"),
            "start":       h.get("start"),
            "description": h.get("_formatted", {}).get("description", h.get("description")),
        })

    return jsonify({"hits": hits, "total": data.get("estimatedTotalHits", len(hits))})


# ── New routes ────────────────────────────────────────────────────────────────

@app.route("/api/videos")
def videos():
    """List all unique indexed videos with segment counts."""
    r = requests.post(
        f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
        headers=HEADERS,
        json={
            "q": "",
            "limit": 10000,
            "attributesToRetrieve": ["video_path", "video_name", "folder"],
        },
        timeout=30,
    )
    data = r.json()
    seen = {}
    for h in data.get("hits", []):
        vp = h.get("video_path")
        if not vp:
            continue
        if vp not in seen:
            seen[vp] = {
                "video_path":    vp,
                "video_name":    h.get("video_name"),
                "folder":        h.get("folder"),
                "segment_count": 0,
            }
        seen[vp]["segment_count"] += 1
    result = sorted(seen.values(), key=lambda x: (x.get("folder") or "", x.get("video_name") or ""))
    return jsonify(result)


@app.route("/api/transcript")
def transcript():
    """All segments of a video ordered by start time."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        return jsonify({"error": "video_path required"}), 400
    segments = _fetch_segments(video_path)
    return jsonify({"segments": segments, "total": len(segments)})


@app.route("/api/subtitle")
def subtitle():
    """Download the SRT file for a video."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        abort(400)
    segments = _fetch_segments(video_path)
    if not segments:
        abort(404)

    video_name = Path(video_path).stem

    # Try to serve the actual SRT file from the mounted volume
    srt_rel = segments[0].get("srt_path", "")
    if srt_rel and SRT_PATH:
        try:
            srt_file = _safe_resolve(SRT_PATH, srt_rel)
            if srt_file.exists():
                return send_file(
                    str(srt_file),
                    as_attachment=True,
                    download_name=f"{video_name}.srt",
                    mimetype="text/plain; charset=utf-8",
                )
        except Exception:
            pass

    # Fallback: reconstruct SRT from Meilisearch data
    content = _build_srt(segments)
    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{video_name}.srt"'},
    )


@app.route("/api/transcript/txt")
def transcript_txt():
    """Download plain text transcript (spoken lines only, no timestamps)."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        abort(400)
    segments = _fetch_segments(video_path)
    if not segments:
        abort(404)

    video_name = Path(video_path).stem
    txt = "\n".join(seg.get("text", "") for seg in segments if seg.get("text", "").strip())
    return Response(
        txt,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{video_name}.txt"'},
    )


@app.route("/api/video")
def video():
    """Stream a video file with byte-range support (for HTML5 player seeking)."""
    path = request.args.get("path", "").strip()
    if not path:
        abort(400)
    try:
        video_file = _safe_resolve(VIDEOS_PATH, path)
    except Exception:
        abort(403)
    if not video_file.exists():
        abort(404)

    ext  = video_file.suffix.lower()
    mime = "video/mp4" if ext == ".mp4" else "video/quicktime" if ext == ".mov" else "application/octet-stream"

    as_dl = request.args.get("download") == "1"
    if as_dl:
        return send_file(str(video_file), as_attachment=True, mimetype=mime)

    return _stream_file(video_file, mime)


def _resolution_tokens():
    """Ordered list of resolution folder/suffix tokens (config-driven)."""
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path) as f:
            toks = json.load(f).get("resolutions")
        if isinstance(toks, list) and toks:
            return [str(t) for t in toks]
    except Exception:
        pass
    return ["4k", "1080p", "720p"]


def _resolution_label(token: str) -> str:
    """Best-effort display label from a token: 4k -> 4K, 1080p -> 1080p."""
    return token.upper() if token.lower().endswith("k") else token


def _find_raw_variant(folder: Path, clip_id: str):
    """RAW files don't share the `_<token>` suffix convention — they keep
    only the camera clip id (e.g. C0219.MP4 for .../C0219_169_1080p.mp4).
    Match by stem, case-insensitively, since camera output is often .MP4."""
    try:
        if not folder.is_dir():
            return None
        for f in folder.iterdir():
            if f.is_file() and f.stem.lower() == clip_id.lower():
                return f
    except Exception:
        pass
    return None


def _resolution_variants(video_path: str):
    """Given an indexed video path, return the resolution variants that
    actually exist on disk. Convention (pasta + sufixo espelhado):
    the resolution is BOTH the first path segment under VIDEOS_PATH and a
    `_<token>` suffix in the filename — except RAW, matched by clip id
    (see _find_raw_variant). Returns [] on any failure so the caller can
    fall back to the single original download."""
    try:
        base = Path(VIDEOS_PATH).resolve()
        orig = _safe_resolve(VIDEOS_PATH, video_path)
        rel = orig.relative_to(base)
    except Exception:
        return []
    parts = rel.parts
    if len(parts) < 2:
        return []  # no resolution folder to swap
    tokens = _resolution_tokens()
    cur = parts[0]
    if cur not in tokens:
        return []  # first segment isn't a known resolution → don't guess
    stem, suffix = orig.stem, orig.suffix
    cur_sfx = f"_{cur}"
    base_stem = stem[: -len(cur_sfx)] if stem.endswith(cur_sfx) else stem
    clip_id = base_stem.split("_")[0]
    variants = []
    for tok in tokens:
        folder = base.joinpath(tok, *parts[1:-1])
        if tok == "RAW":
            cand = _find_raw_variant(folder, clip_id)
        else:
            name = f"{base_stem}_{tok}{suffix}" if stem.endswith(cur_sfx) else orig.name
            candidate = folder / name
            cand = candidate if candidate.is_file() else None
        if cand is None:
            continue
        try:
            variants.append({
                "token": tok,
                "label": _resolution_label(tok),
                "path": str(cand),
                "size": cand.stat().st_size,
            })
        except Exception:
            continue
    return variants


@app.route("/api/resolutions")
def resolutions():
    """List downloadable resolution variants for an indexed video.
    Only variants present on disk are returned; empty list means 'just use
    the original path' (frontend keeps a single plain download button)."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        abort(400)
    return jsonify({"variants": _resolution_variants(video_path)})


@app.route("/api/scenes")
def scenes_api():
    """All scenes of a video ordered by start time."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        return jsonify({"error": "video_path required"}), 400
    body = {
        "q": "",
        "limit": 10000,
        "filter": f'video_path = "{_meili_escape(video_path)}"',
        "sort": ["start:asc"],
        "attributesToRetrieve": ["start", "end", "timestamp", "description"],
    }
    r = requests.post(
        f"{MEILI_URL}/indexes/{SCENES_INDEX}/search",
        headers=HEADERS,
        json=body,
        timeout=30,
    )
    segments = r.json().get("hits", [])
    return jsonify({"segments": segments, "total": len(segments)})


@app.route("/api/scenes/txt")
def scenes_txt():
    """Download scene descriptions as plain text with timestamps."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        abort(400)
    body = {
        "q": "",
        "limit": 10000,
        "filter": f'video_path = "{_meili_escape(video_path)}"',
        "sort": ["start:asc"],
        "attributesToRetrieve": ["timestamp", "description"],
    }
    r = requests.post(
        f"{MEILI_URL}/indexes/{SCENES_INDEX}/search",
        headers=HEADERS,
        json=body,
        timeout=30,
    )
    segments = r.json().get("hits", [])
    if not segments:
        abort(404)
    video_name = Path(video_path).stem
    lines = [
        f"[{seg.get('timestamp', '')}] {seg.get('description', '')}"
        for seg in segments
        if seg.get("description", "").strip()
    ]
    return Response(
        "\n".join(lines),
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{video_name}_cenas.txt"'},
    )


@app.route("/api/metadata")
def metadata():
    """Technical metadata (codec, resolution, duration, etc) via ffprobe."""
    video_path = request.args.get("video_path", "").strip()
    if not video_path:
        abort(400)
    try:
        video_file = _safe_resolve(VIDEOS_PATH, video_path)
    except Exception:
        abort(403)
    if not video_file.exists():
        abort(404)

    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(video_file),
            ],
            capture_output=True, text=True, timeout=30,
        )
        probe = json.loads(proc.stdout)
    except Exception:
        return jsonify({"error": "ffprobe_failed"}), 500

    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def _fps(stream):
        raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
        if not raw or raw == "0/0":
            return None
        num, _, den = raw.partition("/")
        try:
            return round(float(num) / float(den), 2) if den and float(den) else float(num)
        except (ValueError, ZeroDivisionError):
            return None

    result = {
        "file_name":  video_file.name,
        "size":       video_file.stat().st_size,
        "duration":   float(fmt.get("duration")) if fmt.get("duration") else None,
        "bit_rate":   int(fmt.get("bit_rate")) if fmt.get("bit_rate") else None,
        "format_name": fmt.get("format_long_name"),
        "video": None,
        "audio": None,
    }
    if video_stream:
        result["video"] = {
            "codec":    video_stream.get("codec_long_name") or video_stream.get("codec_name"),
            "width":    video_stream.get("width"),
            "height":   video_stream.get("height"),
            "fps":      _fps(video_stream),
            "bit_rate": int(video_stream["bit_rate"]) if video_stream.get("bit_rate") else None,
            "pix_fmt":  video_stream.get("pix_fmt"),
        }
    if audio_stream:
        result["audio"] = {
            "codec":       audio_stream.get("codec_long_name") or audio_stream.get("codec_name"),
            "sample_rate": audio_stream.get("sample_rate"),
            "channels":    audio_stream.get("channels"),
            "bit_rate":    int(audio_stream["bit_rate"]) if audio_stream.get("bit_rate") else None,
        }
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

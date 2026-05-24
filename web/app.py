# VidFind — https://github.com/dcbasso/VidFind
# Copyright (c) 2025 Dante Basso. MIT License.

import os
import json
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

#!/usr/bin/env bash
# Empacota o projeto ad-search + volumes Docker para transferência ao servidor.
# Saída: /home/dcbasso/worksapce/Hexata/ad-search-<data>.zip
set -euo pipefail

DEST_DIR="/home/dcbasso/worksapce/Hexata"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y%m%d_%H%M)
WORK_DIR=$(mktemp -d)
BUNDLE="$WORK_DIR/ad-search"

echo "==> Preparando bundle em $BUNDLE"
mkdir -p "$BUNDLE/volumes"

# ── 1. Código-fonte (sem .env, __pycache__, volumes locais) ─────────────────
echo "==> Copiando código-fonte..."
rsync -a --exclude='.env' \
         --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.git' \
         --exclude='servidor/pack.sh' \
         "$PROJECT_DIR/" "$BUNDLE/project/"

# ── 2. Volume srt_data (legendas .srt) ──────────────────────────────────────
echo "==> Exportando volume srt_data..."
docker run --rm \
  -v ad-search_srt_data:/srt:ro \
  -v "$BUNDLE/volumes":/backup \
  alpine \
  tar czf /backup/srt_data.tar.gz -C /srt .
echo "    $(du -sh "$BUNDLE/volumes/srt_data.tar.gz" | cut -f1)  srt_data.tar.gz"

# ── 3. Volume meili_data (índice de busca) ───────────────────────────────────
echo "==> Exportando volume meili_data (pode demorar alguns segundos)..."
docker run --rm \
  -v ad-search_meili_data:/meili_data:ro \
  -v "$BUNDLE/volumes":/backup \
  alpine \
  tar czf /backup/meili_data.tar.gz -C /meili_data .
echo "    $(du -sh "$BUNDLE/volumes/meili_data.tar.gz" | cut -f1)  meili_data.tar.gz"

# ── 4. Gerar o zip final ─────────────────────────────────────────────────────
OUTPUT="$DEST_DIR/ad-search-$DATE.zip"
echo "==> Criando $OUTPUT ..."
(cd "$WORK_DIR" && zip -r "$OUTPUT" ad-search/)

rm -rf "$WORK_DIR"

echo ""
echo "✅ Pronto: $OUTPUT"
echo "   $(du -sh "$OUTPUT" | cut -f1)"

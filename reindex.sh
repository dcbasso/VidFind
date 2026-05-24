#!/bin/bash
set -e

echo "🔍 Verificando modelo LLaVA..."
MODEL="${OLLAMA_MODEL:-llava:13b}"

INSTALLED=$(curl -s http://localhost:11434/api/tags | python3 -c "
import json, sys
d = json.load(sys.stdin)
models = [m['name'] for m in d.get('models', [])]
print('yes' if any('$MODEL' in m for m in models) else 'no')
" 2>/dev/null || echo "no")

if [ "$INSTALLED" = "no" ]; then
  echo "📥 Baixando $MODEL (pode demorar)..."
  docker compose exec ollama ollama pull "$MODEL"
  echo "✅ Modelo pronto."
else
  echo "✅ $MODEL já instalado."
fi

echo ""
echo "🔨 Rebuilding indexer..."
docker compose build indexer

echo ""
echo "🎬 Iniciando indexação..."
docker compose up indexer

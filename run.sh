#!/usr/bin/env bash
# run.sh — start the ApexView server
set -e

cd "$(dirname "$0")/backend"

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║   ApexView — Bird's-Eye View     ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# Install deps if needed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "  → Installing Python dependencies..."
  pip install -r requirements.txt --quiet
fi

# Check for ffmpeg (optional but recommended)
if command -v ffmpeg &>/dev/null; then
  echo "  ✓ ffmpeg found — H.264 re-encoding enabled"
else
  echo "  ! ffmpeg not found — install it for browser-compatible output"
  echo "    macOS:   brew install ffmpeg"
  echo "    Ubuntu:  sudo apt install ffmpeg"
  echo "    Windows: https://ffmpeg.org/download.html"
fi

echo ""
echo "  → Starting server at http://localhost:8000"
echo ""

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

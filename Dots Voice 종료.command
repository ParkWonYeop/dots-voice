#!/bin/zsh
set -euo pipefail
cd -- "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
".tts-venv/bin/python" src/voice_launcher.py --stop
if [[ -t 0 ]]; then read '?Enter를 누르면 닫힙니다.'; fi

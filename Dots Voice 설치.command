#!/bin/zsh
set -euo pipefail
cd -- "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
trap 'print "설치 실패. 위 오류를 확인하세요."; read "?Enter를 누르면 닫힙니다."' ZERR
if ! command -v python3.11 >/dev/null; then
  print 'Python 3.11이 필요합니다. Homebrew 사용 시: brew install python@3.11'
  read '?Enter를 누르면 닫힙니다.'
  exit 1
fi
python3.11 src/setup_chrome.py "$@"
if [[ -t 0 ]]; then read '?Enter를 누르면 닫힙니다.'; fi

#!/bin/sh
set -eu
DOTS_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DOTS_ROOT"
DOTS_PYTHON=${DOTS_PYTHON:-python3.11}
"$DOTS_PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
mkdir -p runtime/vendor/infer_pack models artifacts
DOTS_RVC_REV=d8ef15799470193f7c8176ef471245753a656626
DOTS_CONTENTVEC_REV=ab04aa7067b99ee05cc82499bc64916b980a1967
for module in models modules attentions commons transforms; do
  curl -fsSL "https://raw.githubusercontent.com/w-okada/voice-changer/$DOTS_RVC_REV/server/voice_changer/RVC/inferencer/rvc_models/infer_pack/$module.py" -o "runtime/vendor/infer_pack/$module.py"
done
touch runtime/vendor/infer_pack/__init__.py
curl -fsSL "https://raw.githubusercontent.com/w-okada/voice-changer/$DOTS_RVC_REV/LICENSE" -o runtime/vendor/LICENSE
curl -fsSL "https://huggingface.co/lengyue233/content-vec-best/raw/$DOTS_CONTENTVEC_REV/config.json" -o runtime/vendor/contentvec-config.json
if [ ! -f models/contentvec.bin ]; then
  curl -fL "https://huggingface.co/lengyue233/content-vec-best/resolve/$DOTS_CONTENTVEC_REV/pytorch_model.bin" -o models/contentvec.bin
fi
printf '%s\n' 'Setup complete. Start .venv/bin/python bridge_server.py --model /path/to/model.pth'

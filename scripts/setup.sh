#!/usr/bin/env bash
# Idempotent environment setup (Claude Code cloud "Setup script", local machine, or CI). Needs: python3, node>=18.
set -e; cd "$(dirname "$0")/.."
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo"
command -v ffmpeg >/dev/null || { $SUDO apt-get update -y -qq && $SUDO apt-get install -y -qq ffmpeg; }
fc-list 2>/dev/null | grep -qi "inter" || $SUDO apt-get install -y -qq fonts-inter 2>/dev/null || echo "! font Inter tidak terpasang: tampilan teks akan memakai font cadangan"
# --ignore-installed ALWAYS: Debian images ship Pillow 10.2.0 for the system Python; pip would call ">=10" satisfied and Python 3.13 then fails with ImportError _imaging.
python3 -m pip install -q --ignore-installed -r requirements.txt 2>/dev/null || python3 -m pip install -q --ignore-installed --break-system-packages -r requirements.txt   # 2nd form: Debian "externally managed" Python
node -e "require('playwright')" 2>/dev/null || { npm install --silent && npx --yes playwright install --with-deps chromium; }
python3 -c 'import PIL.Image,numpy,PIL;assert tuple(map(int,PIL.__version__.split(".")[:2]))>=(11,0),PIL.__version__' || { echo 'SETUP GAGAL: Pillow>=11/numpy tidak bisa dipakai'; exit 4; }
echo "setup OK: $(ffmpeg -version | head -1 | cut -c1-30) | node $(node -v) | anthropic $(python3 -c 'import anthropic;print(anthropic.__version__)')"

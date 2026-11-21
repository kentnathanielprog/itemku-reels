#!/usr/bin/env bash
# Entry point for a scheduled Claude cloud session. usage: session_run.sh produce|publish [extra args]
# Uses this session's own Claude login for the LLM roles (no API key), and the repo only as persistent storage.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE=${1:?produce|publish}; shift || true
DRY=0; for a in "$@"; do [ "$a" = "--dry-run" ] && DRY=1; done      # dry-run must never write or push state
git checkout -q main && git pull -q --ff-only origin main || echo "PERINGATAN: git pull gagal"
# State only survives if this session can push. Live runs abort (a post that cannot be recorded would be posted again next time); dry-run just reports.
if git push --dry-run -q origin HEAD:main >/tmp/_pf.log 2>&1; then echo "PUSH: ok"; else
  echo "PUSH: GAGAL ($(tail -1 /tmp/_pf.log | cut -c1-160))"; [ $DRY = 1 ] || { echo "ABORT: sesi ini tidak bisa menyimpan state ke GitHub (tambahkan repo ke sumber routine). Tidak ada yang diproses."; exit 3; }
fi
# Some cloud images ship a broken system Pillow that pip does not override: install into our own folder and put it first on PYTHONPATH (inherited by every python subprocess).
export PYTHONPATH="$HOME/.pydeps${PYTHONPATH:+:$PYTHONPATH}"
PYCHK='import PIL.Image,numpy,PIL;assert tuple(map(int,PIL.__version__.split(".")[:2]))>=(11,0)'   # Debian's 10.2.0 must not count as "installed"
if ! python3 -c "$PYCHK" 2>/dev/null; then
  echo "SETUP: memasang Pillow>=11/numpy ke $HOME/.pydeps"; python3 -m pip install --break-system-packages --ignore-installed --target "$HOME/.pydeps" --upgrade 'Pillow>=11,<14' 'numpy>=1.26' 2>&1 | tail -4 || true
fi
if ! python3 -c "$PYCHK" 2>/dev/null || ! command -v ffmpeg >/dev/null; then
  echo "SETUP: memasang dependensi..."; bash scripts/setup.sh 2>&1 | tail -15 || true
  python3 -c "$PYCHK" 2>/dev/null && command -v ffmpeg >/dev/null || { echo "ABORT: dependensi (Pillow/numpy/ffmpeg) tidak bisa dipasang di sesi ini. Tidak ada yang diproses."; exit 4; }
fi
save() { git config user.name reels-bot; git config user.email reels-bot@users.noreply.github.com
  git add auto/state short/stories; git diff --cached --quiet || git commit -q -m "state: $MODE $(date -u +%FT%H:%M)"
  for i in 1 2 3; do git pull -q --rebase origin main && git push -q origin main && break || sleep 3; done; }
case "$MODE" in
produce)
  export LLM_BACKEND=claude_cli LLM_CLI_ALLOW_LOCAL_LOGIN=1
  python3 auto/produce.py "$@"; [ $DRY = 1 ] && exit 0; save; bash scripts/media_sync.sh push;;
publish)
  bash scripts/media_sync.sh pull
  python3 auto/publish.py "$@"; [ $DRY = 1 ] && exit 0; python3 auto/insights.py 2>/dev/null || true; save; bash scripts/media_sync.sh push;;
*) echo "mode?"; exit 2;;
esac

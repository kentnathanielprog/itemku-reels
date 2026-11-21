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
[ -d node_modules/playwright ] || bash scripts/setup.sh >/dev/null 2>&1
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

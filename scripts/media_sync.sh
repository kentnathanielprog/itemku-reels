#!/usr/bin/env bash
# Carry rendered videos between cloud sessions (containers are ephemeral) via the orphan branch `media`.
# push: publish videos of queue items still ready/publishing | pull: restore them into out/
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
push)
  T=$(mktemp -d); python3 - "$T" <<'PY'
import json,sys,shutil,pathlib
q=json.load(open('auto/state/queue.json')); n=0
for i in q:
    if i['status'] in ('ready','publishing') and pathlib.Path(i['video']).exists():
        d=pathlib.Path(sys.argv[1])/i['video']; d.parent.mkdir(parents=True,exist_ok=True); shutil.copy(i['video'],d); n+=1
print(f'media: {n} video')
PY
  URL=$(git remote get-url origin)
  git -C "$T" init -q -b media && git -C "$T" add -A && git -C "$T" -c user.name=reels-bot -c user.email=reels-bot@users.noreply.github.com commit -q --allow-empty -m "media $(date -u +%FT%H:%M)"
  git -C "$T" push -q -f "$URL" media:media; rm -rf "$T";;
pull)
  git fetch -q origin media 2>/dev/null || { echo "belum ada branch media"; exit 0; }
  git archive FETCH_HEAD | tar -x -C . ; ls out 2>/dev/null | head;;
*) echo "usage: media_sync.sh push|pull"; exit 2;;
esac

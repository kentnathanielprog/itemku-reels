#!/usr/bin/env bash
# Sourced by session_run.sh (and tests). save_state <label>: commit auto/state + short/stories and push to origin/$STATE_BRANCH (default main).
# Hard failure: returns 1 after 3 failed pull-rebase+push attempts (rebase aborted, tree left clean). Callers MUST treat that as a failed run.
save_state() {
  local mode=${1:-state} br=${STATE_BRANCH:-main} i
  git config user.name reels-bot; git config user.email reels-bot@users.noreply.github.com
  git add auto/state short/stories
  git diff --cached --quiet || git commit -q -m "state: $mode $(date -u +%FT%H:%M)"
  for i in 1 2 3; do
    if git pull -q --rebase origin "$br" 2>/dev/null && git push -q origin "HEAD:$br" 2>/dev/null; then echo "STATE: tersimpan (percobaan $i)"; return 0; fi
    git rebase --abort 2>/dev/null || true
    sleep "${STATE_RETRY_SLEEP:-3}"
  done
  echo "STATE GAGAL: perubahan state TIDAK terdorong ke origin/$br setelah 3 percobaan." >&2
  return 1
}

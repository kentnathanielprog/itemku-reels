#!/usr/bin/env bash
# Tests scripts/state_save.sh against local git remotes (no network): success, rejected push, rebase conflict, clean tree afterwards.
set -u; REPO=$(cd "$(dirname "$0")/.." && pwd); P=0; F=0
ok(){ echo "  ✓ $1"; P=$((P+1)); }; bad(){ echo "  ✗ $1"; F=$((F+1)); }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
g(){ git -c user.name=t -c user.email=t@t "$@"; }
git init -q --bare -b main "$T/origin.git"
git clone -q "$T/origin.git" "$T/w1" 2>/dev/null; cd "$T/w1"; mkdir -p auto/state short/stories; echo '[]' > auto/state/queue.json; g add -A; g commit -qm init; g push -q origin main
git clone -q "$T/origin.git" "$T/w2" 2>/dev/null
run_save(){ ( cd "$1"; . "$REPO/scripts/state_save.sh"; STATE_RETRY_SLEEP=0 save_state test ) >"$T/out.log" 2>&1; }
cd "$T/w1"; echo '[{"id":"x"}]' > auto/state/queue.json; run_save "$T/w1" && ok "push normal berhasil" || bad "push normal"
[ "$(git -C "$T/origin.git" rev-parse main)" = "$(git -C "$T/w1" rev-parse HEAD)" ] && ok "origin menerima commit state" || bad "origin tidak menerima"
# remote advanced with a NON-conflicting change -> rebase + push succeeds
cd "$T/w2"; git pull -q origin main; echo hi > auto/note.txt; g add -A; g commit -qm other; git push -q origin main
cd "$T/w1"; echo '[{"id":"x"},{"id":"y"}]' > auto/state/queue.json; run_save "$T/w1" && ok "origin maju (tanpa konflik): rebase lalu push berhasil" || bad "rebase tanpa konflik"
# conflict on the same file -> must FAIL and leave the tree clean (no half rebase)
cd "$T/w2"; git pull -q origin main; echo '[{"id":"CONFLICT-REMOTE"}]' > auto/state/queue.json; g add -A; g commit -qm remote-edit; git push -q origin main
cd "$T/w1"; echo '[{"id":"CONFLICT-LOCAL"}]' > auto/state/queue.json
run_save "$T/w1"; rc=$?; [ $rc -ne 0 ] && ok "konflik state: save_state GAGAL keras (exit $rc)" || bad "konflik state dianggap sukses"
grep -q "STATE GAGAL" "$T/out.log" && ok "pesan 'STATE GAGAL' dicetak" || bad "tidak ada pesan gagal"
[ ! -d "$T/w1/.git/rebase-merge" ] && [ ! -d "$T/w1/.git/rebase-apply" ] && ok "rebase dibatalkan, tidak ada rebase setengah jalan" || bad "rebase menggantung"
# origin rejects pushes (hook) -> fail
git init -q --bare -b main "$T/o2.git"; git clone -q "$T/o2.git" "$T/w3" 2>/dev/null; cd "$T/w3"; mkdir -p auto/state short/stories; echo '[]' > auto/state/queue.json; g add -A; g commit -qm init; git push -q origin main
printf '#!/bin/sh\necho rejected >&2\nexit 1\n' > "$T/o2.git/hooks/pre-receive"; chmod +x "$T/o2.git/hooks/pre-receive"
echo '[1]' > auto/state/queue.json; run_save "$T/w3"; [ $? -ne 0 ] && ok "push ditolak origin: save_state gagal keras" || bad "push ditolak dianggap sukses"
# session_run.sh wiring: no leftover fire-and-forget save(), and failure maps to exit 5 before media push
grep -q 'save_state "$MODE"' "$REPO/scripts/session_run.sh" && grep -q 'exit 5' "$REPO/scripts/session_run.sh" && ! grep -qE '^save\(\)|; save;' "$REPO/scripts/session_run.sh" && ok "session_run.sh memakai save_state dan keluar 5 bila gagal" || bad "wiring session_run.sh"
echo "passed=$P failed=$F"; [ $F -eq 0 ]

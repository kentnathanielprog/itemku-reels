#!/usr/bin/env bash
# Scheduled-run wrapper must refuse manual-only flags (no git or network is touched: the check runs first).
set -u; cd "$(dirname "$0")/.."; P=0; F=0
ok(){ echo "  ✓ $1"; P=$((P+1)); }; bad(){ echo "  ✗ $1"; F=$((F+1)); }
for fl in --force --ignore-burst; do
  out=$(bash scripts/session_run.sh publish $fl 2>&1); rc=$?
  [ $rc -eq 2 ] && echo "$out" | grep -q "hanya untuk panggilan manual" && ok "session_run.sh publish $fl ditolak (exit 2)" || bad "session_run.sh publish $fl tidak ditolak (rc=$rc)"
done
out=$(bash scripts/session_run.sh produce --force 2>&1); [ $? -eq 2 ] && ok "session_run.sh produce --force ditolak" || bad "produce --force"
grep -q 'ALLOW_FORCE' scripts/session_run.sh && ok "override eksplisit ALLOW_FORCE=1 tersedia untuk panggilan manual" || bad "ALLOW_FORCE"
echo "passed=$P failed=$F"; [ $F -eq 0 ]

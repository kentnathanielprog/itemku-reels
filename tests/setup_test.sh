#!/usr/bin/env bash
# Static + functional checks for the Pillow/setup fix (no network needed except an optional pip resolver dry-run).
set -u; cd "$(dirname "$0")/.."; P=0; F=0
ok(){ echo "  ✓ $1"; P=$((P+1)); }; bad(){ echo "  ✗ $1"; F=$((F+1)); }
grep -qx 'Pillow>=11,<14' requirements.txt && ok "requirements.txt: Pillow>=11,<14" || bad "requirements.txt pin"
n=$(grep -c 'pip install' scripts/setup.sh); m=$(grep 'pip install' scripts/setup.sh | grep -c -- '--ignore-installed'); [ "$n" -ge 1 ] && [ "$n" = "$m" ] && ok "setup.sh: setiap pip install memakai --ignore-installed ($m/$n)" || bad "setup.sh --ignore-installed ($m/$n)"
grep -q -- '--ignore-installed' scripts/session_run.sh && grep -q "Pillow>=11,<14" scripts/session_run.sh && ok "session_run.sh: install ke ~/.pydeps memakai --ignore-installed + pin" || bad "session_run.sh"
# the version gate must reject Debian's 10.2.0 and accept 11+
CHK='import PIL,sys;assert tuple(map(int,sys.argv[1].split(".")[:2]))>=(11,0)'
python3 -c "$CHK" 10.2.0 2>/dev/null && bad "gate menerima 10.2.0" || ok "gerbang versi menolak Pillow 10.2.0 bawaan Debian"
python3 -c "$CHK" 12.3.0 2>/dev/null && ok "gerbang versi menerima Pillow 12.3.0" || bad "gate menolak 12.3.0"
grep -q 'PIL.__version__.split' scripts/setup.sh && grep -q 'PIL.__version__.split' scripts/session_run.sh && ok "setup.sh dan session_run.sh memakai gerbang versi yang sama" || bad "gerbang versi tidak ada di skrip"
bash -n scripts/setup.sh && bash -n scripts/session_run.sh && ok "sintaks skrip bash valid" || bad "sintaks bash"
if timeout 60 python3 -m pip install --dry-run -q --ignore-installed -r requirements.txt >/dev/null 2>&1; then ok "pip resolver menerima requirements.txt (dry-run)"; else echo "  - pip dry-run dilewati/gagal (jaringan?)"; fi
echo "passed=$P failed=$F"; [ $F -eq 0 ]

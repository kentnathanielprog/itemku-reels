#!/usr/bin/env bash
# produce.py must fail visibly: exit 3 on 0 candidates, exit 4 when candidates exist but nothing is queued. Offline (LLM mock, no network).
set -u; cd "$(dirname "$0")/.."; P=0; F=0
ok(){ echo "  ✓ $1"; P=$((P+1)); }; bad(){ echo "  ✗ $1"; F=$((F+1)); }
T=$(mktemp -d); trap 'rm -rf "$T"; cp /tmp/_pe_queue.json auto/state/queue.json 2>/dev/null; rm -rf out/test-story out/short-test-story short/stories/test-story.json auto/state/runlog/1999-01-02.json; git checkout -q -- auto/state/llm_usage.jsonl 2>/dev/null' EXIT
cp auto/state/queue.json /tmp/_pe_queue.json
echo '[]' > $T/empty.json
LLM_MOCK_DIR=tests/fixtures/mock python3 auto/produce.py --day 1999-01-02 --picks-file $T/empty.json > $T/o1.log 2>&1; rc=$?
[ $rc -eq 3 ] && grep -q "GAGAL: 0 kandidat" $T/o1.log && ok "0 kandidat -> exit 3 + pesan GAGAL" || { bad "0 kandidat (rc=$rc)"; tail -3 $T/o1.log; }
LLM_MOCK_DIR=tests/fixtures/mock python3 auto/produce.py --dry-run --day 1999-01-02 --picks-file $T/empty.json > $T/o2.log 2>&1; [ $? -eq 3 ] && ok "dry-run dengan 0 kandidat juga exit 3" || bad "dry-run 0 kandidat"
python3 tests/make_fixtures.py >/dev/null 2>&1
# candidates exist, but QC says FAIL in every round -> nothing queued -> exit 4
mkdir -p $T/mock; cp tests/fixtures/mock/*.json $T/mock/; python3 - "$T/mock" <<'PY'
import json,sys,pathlib
d=pathlib.Path(sys.argv[1]); q=json.load(open(d/'qc_1.json'))
for r in q['reports']: r['verdict']='FAIL'; r['issues']=['dibuat gagal oleh tes']; r['fixes']=[]
for n in (1,2,3,4): (d/f'qc_{n}.json').write_text(json.dumps(q))
w=json.load(open(d/'writer_1.json'))
for n in (2,3,4): (d/f'writer_{n}.json').write_text(json.dumps(w))
PY
LLM_MOCK_DIR=$T/mock python3 auto/produce.py --day 1999-01-02 --picks-file tests/fixtures/picks.json > $T/o3.log 2>&1; rc=$?
[ $rc -eq 4 ] && grep -q "0 video yang lolos" $T/o3.log && ok "kandidat ada tapi 0 video lolos -> exit 4" || { bad "0 video (rc=$rc)"; tail -4 $T/o3.log; }
LLM_MOCK_DIR=tests/fixtures/mock python3 auto/produce.py --day 1999-01-02 --picks-file tests/fixtures/picks.json > $T/o4.log 2>&1; rc=$?
[ $rc -eq 0 ] && ok "jalur sukses tetap exit 0" || { bad "jalur sukses rc=$rc"; tail -4 $T/o4.log; }
grep -q 'set -e' scripts/session_run.sh && grep -q 'python3 auto/produce.py "\$@"; \[ \$DRY = 1 \] && exit 0' scripts/session_run.sh && ok "session_run.sh (set -e) meneruskan exit non-zero produce, termasuk dry-run" || bad "session_run.sh tidak meneruskan exit produce"
echo "passed=$P failed=$F"; [ $F -eq 0 ]

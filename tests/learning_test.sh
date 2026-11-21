#!/usr/bin/env bash
# Offline test for the learning agent (no network, no token). usage: bash tests/learning_test.sh
set -u; cd "$(dirname "$0")/.."; P=0; F=0
ok(){ echo "OK   $1"; P=$((P+1)); }; bad(){ echo "FAIL $1"; F=$((F+1)); }
T=$(mktemp -d); trap 'rm -rf "$T"; git checkout -q -- auto/config.json auto/scout.py 2>/dev/null' EXIT
python3 - "$T/p.jsonl" <<'PY'
import json,sys,random
random.seed(1); rows=[]
for i in range(24):
    cat='mlbb' if i<12 else 'general'; base=2000 if cat=='mlbb' else 1000
    rows.append({'at':'2026-12-01T00:00:00+00:00','media_id':str(i),'age_h':100,'reach':base+random.randint(-100,100),'plays':base*2,'cat':cat,'hook_type':'news' if i%2 else 'question','n_images':1,'music':False,'duration_s':25,'hour_wib':7 if i%3 else 17})
rows.append({'at':'2026-12-01T00:00:00+00:00','media_id':'young','age_h':5,'reach':9,'plays':9,'cat':'gta','hook_type':'news','n_images':1,'music':False,'duration_s':25,'hour_wib':7})
open(sys.argv[1],'w').write('\n'.join(json.dumps(r) for r in rows)+'\n')
PY
O=$(python3 learning/analyze.py --file "$T/p.jsonl"); echo "$O" | grep -q "Reel dianalisis: 24" && ok "analyzer drops Reels < 48h" || bad "age filter"
echo "$O" | grep -q "mlbb vs general" && echo "$O" | grep -q LOLOS && ok "analyzer flags real gap (mlbb vs general)" || bad "gap detection"
python3 learning/analyze.py --file /nonexistent | grep -q "TOTAL SAMPEL KURANG" && ok "too few Reels -> no conclusion" || bad "min sample"
H1=$(md5sum data/performance.jsonl); python3 learning/collect.py --dry-run >/dev/null 2>&1 && ok "collector dry-run (no network)" || bad "collector dry-run"
[ "$H1" = "$(md5sum data/performance.jsonl)" ] && ok "dry-run did not write data" || bad "dry-run wrote data"
python3 learning/guard.py >/dev/null && ok "guard: clean tree passes" || bad "guard clean"
chg(){ python3 - "$1" "$2" "$3" "$4" <<'PY'
import json,sys
f,k,sub,v=sys.argv[1:5]; d=json.load(open(f)); d[k][sub]=json.loads(v); json.dump(d,open(f,'w'),indent=1)
PY
}
chg auto/config.json cat_bonus mlbb 35; python3 learning/guard.py >/dev/null && ok "guard: +5 step allowed" || bad "guard small step"
git checkout -q -- auto/config.json; chg auto/config.json cat_bonus mlbb 50; python3 learning/guard.py >/dev/null && bad "guard allowed +20" || ok "guard: oversized step rejected"
git checkout -q -- auto/config.json; chg auto/config.json cat_bonus mlbb 35; chg auto/config.json cat_bonus roblox 35; python3 learning/guard.py >/dev/null && bad "guard allowed 2 changes" || ok "guard: 2 changes in one run rejected"
git checkout -q -- auto/config.json; python3 - <<'PY'
import json;d=json.load(open('auto/config.json'));d['denylist'].remove('leak');json.dump(d,open('auto/config.json','w'),indent=1)
PY
python3 learning/guard.py >/dev/null && bad "guard allowed denylist edit" || ok "guard: denylist edit rejected"
git checkout -q -- auto/config.json; echo "# x" >> auto/scout.py; python3 learning/guard.py >/dev/null && bad "guard allowed .py edit" || ok "guard: .py edit rejected"
git checkout -q -- auto/scout.py; python3 - <<'PY'
import json;d=json.load(open('auto/config.json'));d['slots'][0]['time']='09:30';json.dump(d,open('auto/config.json','w'),indent=1)
PY
python3 learning/guard.py >/dev/null && bad "guard allowed 2h slot shift" || ok "guard: slot shift > 60 min rejected"
git checkout -q -- auto/config.json
echo "passed=$P failed=$F"; [ $F -eq 0 ]

#!/usr/bin/env bash
# Offline self-test: no network, no API key. Takes ~40 s (one real render). Safe: restores state afterwards.
set -u; cd "$(dirname "$0")/.."; PASS=0; FAIL=0
ok(){ echo "  ✓ $1"; PASS=$((PASS+1)); }; bad(){ echo "  ✗ $1"; FAIL=$((FAIL+1)); }
cp auto/state/queue.json /tmp/_queue_backup.json; cp auto/state/history.json /tmp/_history_backup.json; cp auto/state/llm_usage.jsonl /tmp/_usage_backup.jsonl 2>/dev/null || rm -f /tmp/_usage_backup.jsonl
cleanup(){ cp /tmp/_queue_backup.json auto/state/queue.json; cp /tmp/_history_backup.json auto/state/history.json
  rm -rf out/test-story out/short-test-story short/stories/test-story.json auto/state/runlog/1999-01-01.json 2>/dev/null; rm -f auto/state/llm_usage.jsonl; [ -f /tmp/_usage_backup.jsonl ] && cp /tmp/_usage_backup.jsonl auto/state/llm_usage.jsonl; }
trap cleanup EXIT
echo "== fixtures"; python3 tests/make_fixtures.py >/dev/null && ok "fixtures dibuat" || { bad "fixtures"; exit 1; }
echo "== unit checks"
python3 - <<'PY' && ok "lint menolak sorotan terbelah dua baris" || bad "lint sorotan lintas baris"
import sys,json,pathlib; sys.path.insert(0,'short'); from lint import lint
s=json.load(open('tests/fixtures/mock/writer_1.json'))['stories'][0]
st={'hook':s['hook'],'message':s['message'],'gong':{'text':'Target ((M8 World\nChampionship)) dong','img':[0]},'source':'x','images':[],'timing':{}}
P,W=lint(st,pathlib.Path('.')); assert any('BARIS' in p for p in P),P
PY
python3 - <<'PY' && ok "pemeriksa bukti menolak kutipan palsu & angka tanpa bukti" || bad "pemeriksa bukti"
import sys,json; sys.path.insert(0,'auto'); import verify_evidence as VE
a=json.load(open('out/test-story/article.json')); s=json.load(open('tests/fixtures/mock/writer_1.json'))['stories'][0]; q=json.load(open('tests/fixtures/mock/qc_1.json'))['reports'][0]
rep={'verdict':'PASS','claims':[{'text':c['text'],'evidence':c['evidence'],**({'derived':{'count_of':c['count_items'],'value':c['count_value']}} if c['count_items'] else {})} for c in q['claims']]}
assert VE.check(s,rep,a)==[],'caso baik harus lulus'
bad=json.loads(json.dumps(rep)); bad['claims'][1]['evidence']='Nova Games mengaku 10 juta pemain mencoba mode baru itu pada hari pertama'
assert VE.check(s,bad,a),'kutipan palsu harus ditolak'
PY
python3 - <<'PY' && ok "gambar buram/kosong/kembar dibuang otomatis" || bad "pemeriksa visual lapis 1"
import sys; sys.path.insert(0,'auto'); import visual as V
h,s=V.check_images(['out/test-story/imgs/img1.jpg','out/test-story/imgs/img1.jpg','out/test-story/imgs/img2.jpg']); assert 1 in h and 0 not in h and 2 not in h,(h,s)
PY
echo "== backend claude_cli (CLI palsu, tanpa jaringan)"
STUB=$(mktemp -d); cat > $STUB/claude <<'SH'
#!/bin/sh
echo '{"is_error":false,"num_turns":1,"total_cost_usd":0.001,"usage":{"input_tokens":5,"output_tokens":7},"structured_output":{"ok":true,"kata":"halo"}}'
SH
chmod +x $STUB/claude
PATH=$STUB:$PATH LLM_BACKEND=claude_cli CLAUDE_CODE_OAUTH_TOKEN=stub python3 - <<'PY' && ok "backend claude_cli: JSON valid + log pemakaian" || bad "backend claude_cli"
import sys; sys.path.insert(0,'auto'); import llm
d,u=llm.call_json('stub','s','u',{"type":"object","required":["ok","kata"]},'claude-haiku-5-5','low'); assert d=={'ok':True,'kata':'halo'} and u['usd']==0.0,(d,u)
try: llm.call_json('stub','s','u',{"type":"object","required":["hilang"]},'claude-haiku-5-5','low'); raise SystemExit('harus gagal')
except llm.LLMError: pass
PY
rm -rf $STUB
python3 - <<'PY' && ok "pemilih musik IG: hindari lagu baru dipakai, terlalu pendek, atau kosong" || bad "ig_audio"
import sys,random; sys.path.insert(0,'auto'); import ig_audio as A
cfg={'audio':{'queries':{'default':['edm']},'audio_volume':70}}
res=[{'audio_id':'1','title':'a','duration_in_ms':5000},{'audio_id':'2','title':'b','duration_in_ms':90000},{'audio_id':'3','title':'c','duration_in_ms':90000}]
posts=[{'music':{'audio_id':'2'}}]
sel=A.pick(lambda q:res,'mlbb',cfg,posts,rng=random.Random(1)); assert sel and sel['audio_id']=='3',sel
assert A.pick(lambda q:[],'mlbb',cfg,[]) is None
def boom(q): raise RuntimeError('x')
assert A.pick(boom,'mlbb',cfg,[]) is None and '"audio_id": "3"' in A.config_param(sel)
PY
echo "== producer offline (writer + QC + vision = jawaban tiruan; render + antrean sungguhan)"
LLM_MOCK_DIR=tests/fixtures/mock python3 auto/produce.py --day 1999-01-01 --picks-file tests/fixtures/picks.json > /tmp/_produce.log 2>&1
grep -q "LULUS" /tmp/_produce.log && ok "QC PASS + bukti terverifikasi" || bad "produser tidak meluluskan (lihat /tmp/_produce.log)"
[ -f out/short-test-story/short.mp4 ] && ok "video dirender" || bad "video tidak ada"
python3 - <<'PY' && ok "QA: 1080x1920, tanpa kedipan, senyap, ada trek AAC" || bad "QA video"
import sys,json,subprocess; sys.path.insert(0,'short'); import qa
s=json.load(open('short/stories/test-story.json')); I,info=qa.run('out/short-test-story/short.mp4',s); assert not I,I
st=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type','-of','csv=p=0','out/short-test-story/short.mp4'],capture_output=True,text=True).stdout.split(); assert 'audio' in st and 'video' in st
PY
python3 - <<'PY' && ok "antrean berisi video siap + caption" || bad "antrean"
import json; q=json.load(open('auto/state/queue.json')); x=[i for i in q if i['id']=='test-story']; assert x and x[0]['status']=='ready' and 'Sumber: TestSite' in x[0]['caption'],x
PY
H1=$(md5sum auto/state/queue.json|cut -d' ' -f1); IG_USER_ID=1 python3 auto/publish.py --dry-run --force >/dev/null 2>&1; H2=$(md5sum auto/state/queue.json|cut -d' ' -f1)
[ "$H1" = "$H2" ] && ok "publisher dry-run tidak mengubah antrean" || bad "dry-run mengubah antrean"
touch auto/STOP; python3 auto/publish.py --dry-run --force 2>&1 | grep -q "STOP aktif" && ok "tombol STOP menghentikan posting" || bad "tombol STOP"; rm -f auto/STOP
echo; echo "HASIL: $PASS lulus, $FAIL gagal"; [ $FAIL -eq 0 ]

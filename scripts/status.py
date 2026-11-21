#!/usr/bin/env python3
"""One-screen status: queue, last run, API usage/cost (no LLM, no images)."""
import json,pathlib,datetime as dt,collections
B=pathlib.Path(__file__).resolve().parent.parent; ST=B/'auto'/'state'
q=json.loads((ST/'queue.json').read_text()); posts=json.loads((ST/'posts.json').read_text())
print(f"STOP aktif: {'YA' if (B/'auto'/'STOP').exists() else 'tidak'} | posting terkirim: {len(posts)} | antrean: {collections.Counter(x['status'] for x in q) or '{}'}")
for x in sorted(q,key=lambda x:x.get('not_before','')): print(f"  {x.get('posted_slot','?'):>6} {x['status']:10} {str(x.get('cat')):8} {str(x.get('topic'))[:60]}")
logs=sorted((ST/'runlog').glob('*.json'))
if logs:
    r=json.loads(logs[-1].read_text()); print(f"run terakhir {r['day']}: {len(r['ok'])} video, {len(r['calls'])} panggilan API")
u=ST/'llm_usage.jsonl'
if u.exists():
    rows=[json.loads(l) for l in u.read_text().splitlines() if l.strip()]; cut=dt.datetime.now().timestamp()-7*86400; w=[r for r in rows if r['t']>=cut]
    print(f"API 7 hari: {len(w)} panggilan | {sum(r['in']+r['cache_read']+r['cache_write'] for r in w)} token masuk, {sum(r['out'] for r in w)} keluar | ~US${sum(r['usd'] for r in w):.2f}")
else: print("API: belum ada panggilan tercatat")

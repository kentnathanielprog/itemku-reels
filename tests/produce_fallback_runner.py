#!/usr/bin/env python3
"""Helper for tests/produce_fallback_test.py (run in a fresh process per scenario). Runs the REAL auto/produce.py with: a fake scout (given picks + spares),
a fake fetch_news (fails for the listed URLs with a stderr message, otherwise serves the synthetic fixture article), LLM answers from LLM_MOCK_DIR, no render, no enqueue.
usage: produce_fallback_runner.py <config.json>   config = {picks:[url..], spare:[url..], fail:[url..], argv:[..]}"""
import sys,os,json,runpy,shutil,pathlib,subprocess
R=pathlib.Path(__file__).resolve().parent.parent; os.chdir(R); sys.path[:0]=[str(R/'auto'),str(R/'short')]
cfg=json.load(open(sys.argv[1])); FAIL=set(cfg.get('fail',[])); calls=[]
import scout
def cand(u,i): return {'cat':'general','entity':None,'title':f'Story number {i} about the new patch','url':u,'age_h':5,'date':'2026-11-22T00:00:00+00:00','site':'Test'}
picks=[cand(u,i) for i,u in enumerate(cfg['picks'])]; spares=[cand(u,100+i) for i,u in enumerate(cfg.get('spare',[]))]
scout.daily_pick=lambda n=6,verbose=False:(picks,picks+spares); scout.score=lambda x,pb:0
real=subprocess.run
def fake_run(args,*a,**k):
    s=' '.join(map(str,args))
    if 'fetch_news.py' in s:
        url,name=args[4],args[5]; calls.append(url)
        if url in FAIL: return subprocess.CompletedProcess(args,1,'','Traceback (most recent call last):\nurllib.error.URLError: simulated network failure for '+url.split('/')[-1])
        d=R/'out'/name; d.mkdir(parents=True,exist_ok=True); art=json.loads((R/'out'/'test-story'/'article.json').read_text()); art['fulltext']+=' '+' '.join(['Teks tambahan netral agar artikel cukup panjang untuk lolos saringan awal.']*10)   # prep() needs >= 500 chars
        (d/'article.json').write_text(json.dumps(art,ensure_ascii=False)); return subprocess.CompletedProcess(args,0,'ok','')
    return real(args,*a,**k)
subprocess.run=fake_run
sys.argv=['auto/produce.py','--day','1999-01-02','--no-render','--no-enqueue']+cfg.get('argv',[])
code=0
try: runpy.run_path(str(R/'auto'/'produce.py'),run_name='__main__')
except SystemExit as e: code=e.code if isinstance(e.code,int) else 1
print(f'FETCH_CALLS: {len(calls)} | order: '+','.join(u.split('/')[-1] for u in calls)); sys.exit(code)

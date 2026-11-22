#!/usr/bin/env python3
"""Offline tests: produce.py must not give up while spare candidates exist, must log WHY an article failed, and must still exit non-zero when nothing can be prepared.
Real produce.py, fake scout/fetch_news/LLM (see produce_fallback_runner.py). usage: python3 tests/produce_fallback_test.py"""
import sys,os,json,shutil,pathlib,tempfile,subprocess
R=pathlib.Path(__file__).resolve().parent.parent; os.chdir(R)
subprocess.run([sys.executable,'tests/make_fixtures.py'],check=True,capture_output=True)
NAME='good-story-0102'; U=lambda s:f'https://example.com/news/{s}'
T=pathlib.Path(tempfile.mkdtemp(prefix='pfb_')); M=T/'mock'; M.mkdir()
for f in ('writer_1','qc_1','visual_1'): (M/f'{f}.json').write_text((R/'tests/fixtures/mock'/f'{f}.json').read_text().replace('"test-story"',f'"{NAME}"'))
USAGE=R/'auto/state/llm_usage.jsonl'; usage_bak=USAGE.read_bytes() if USAGE.exists() else None
def cleanup():
    shutil.rmtree(R/'out'/NAME,ignore_errors=True)
    for f in (R/'short/stories'/f'{NAME}.json',R/'auto/state/runlog/1999-01-02.json'): f.unlink(missing_ok=True)
    if usage_bak is None: USAGE.unlink(missing_ok=True)
    else: USAGE.write_bytes(usage_bak)
def run(picks,spare,fail,argv=()):
    cfgf=T/'c.json'; cfgf.write_text(json.dumps({'picks':[U(x) for x in picks],'spare':[U(x) for x in spare],'fail':[U(x) for x in fail],'argv':list(argv)}))
    env=dict(os.environ,LLM_MOCK_DIR=str(M)); env.pop('LLM_BACKEND',None)
    p=subprocess.run([sys.executable,'tests/produce_fallback_runner.py',str(cfgf)],capture_output=True,text=True,env=env,timeout=300); cleanup(); return p.returncode,p.stdout+p.stderr
RES=[]
def case(name):
    def deco(fn):
        try: fn(); RES.append((name,True,''))
        except AssertionError as e: RES.append((name,False,str(e)[:600]))
        except Exception as e: RES.append((name,False,f'{type(e).__name__}: {e}'[:600]))
        return fn
    return deco
@case('the 2026-11-22 incident: all 3 top picks fail to fetch -> spare candidates are tried and the run SUCCEEDS (exit 0, 1 video)')
def _():
    c,o=run(['a','b','c'],['bad1','good-story','bad2'],['a','b','c','bad1','bad2']); assert c==0,(c,o[-900:])
    assert 'mencoba kandidat cadangan' in o and 'LULUS' in o and 'selesai: 1/3' in o,o[-900:]
@case('the failure reason is logged (exit code + stderr tail), not just "gagal ambil artikel"')
def _():
    c,o=run(['a'],['good-story'],['a']); assert 'gagal ambil artikel (kode 1: ' in o and 'simulated network failure for a' in o,o[-700:]
@case('spares are bounded: 30 failing spares -> at most 12 fetch attempts (+ the 3 picks), exit 3, clear message')
def _():
    sp=[f's{i}' for i in range(30)]; c,o=run(['a','b','c'],sp,['a','b','c']+sp); assert c==3,(c,o[-500:])
    n=int(o.split('FETCH_CALLS: ')[1].split()[0]); assert n==3+12,n; assert 'tidak ada satu pun berita yang bisa disiapkan' in o,o[-500:]
@case('everything fails including the spares -> exit 3 (not 0, not 4)')
def _():
    c,o=run(['a','b'],['s1','s2'],['a','b','s1','s2']); assert c==3 and 'GAGAL' in o,(c,o[-500:])
@case('no spare candidates and the picks fail -> exit 3 as before')
def _():
    c,o=run(['a','b','c'],[],['a','b','c']); assert c==3 and 'GAGAL: 0 kandidat' in o,(c,o[-400:])
@case('dry-run does not go hunting in the spare list: picks fail -> exit 3')
def _():
    c,o=run(['a'],['good-story'],['a'],['--dry-run']); assert c==3 and 'good-story' not in o.split('FETCH_CALLS')[1],(c,o[-400:])
@case('normal path unchanged: the first pick works -> exit 0 and it is fetched first; spares are only tried to fill up to 3 (existing behaviour)')
def _():
    c,o=run(['good-story'],['s1','s2'],['s1','s2']); assert c==0 and 'selesai: 1/3' in o and 'LULUS' in o,(c,o[-500:]); assert 'order: good-story,s1,s2' in o,o[-200:]
    assert 'mencoba kandidat cadangan' not in o,'the spare-fallback banner must only appear when NO pick could be prepared'
if __name__=='__main__':
    bad=0
    for n,ok,msg in RES: print(('  ✓ ' if ok else '  ✗ ')+n+('' if ok else f'\n      {msg}')); bad+=0 if ok else 1
    print(f'passed={len(RES)-bad} failed={bad}'); cleanup(); sys.exit(1 if bad else 0)

#!/usr/bin/env python3
"""Guard (deterministic): verifies that the Learning Agent's pending change only touches what learning/policy.json allows.
usage: python3 learning/guard.py [--base REF]   (default base = HEAD; checks the working tree + index vs REF). Exit 0 = ok, 1 = violation.
Run it BEFORE every commit; the agent must not commit when it fails."""
import json,subprocess,sys,pathlib,fnmatch,re
ROOT=pathlib.Path(__file__).resolve().parent.parent; POL=json.loads((ROOT/'learning'/'policy.json').read_text())
BASE=sys.argv[sys.argv.index('--base')+1] if '--base' in sys.argv else 'HEAD'
def sh(*a): return subprocess.run(a,cwd=ROOT,capture_output=True,text=True)
ALWAYS_OK={'learning/log.md','data/performance.jsonl'}
def hm(t): h,m=t.split(':'); return int(h)*60+int(m)
def check_map(spec,old,new,errs,label,counter):
    for k in set(old)|set(new):
        if old.get(k)==new.get(k): continue
        counter.append(f'{label}.{k}')
        if k not in spec['keys']: errs.append(f'{label}: key {k} not allowed'); continue
        v=new.get(k)
        if not isinstance(v,int) or isinstance(v,bool): errs.append(f'{label}.{k} must be int'); continue
        if not spec['min']<=v<=spec['max']: errs.append(f'{label}.{k}={v} outside [{spec["min"]},{spec["max"]}]')
        if abs(v-old.get(k,0))>spec['max_step']: errs.append(f'{label}.{k} step {abs(v-old.get(k,0))} > {spec["max_step"]}')
    fl=spec.get('floor_all_above')
    if fl is not None and any(v<=fl for v in new.values()): errs.append(f'{label}: every value must stay > {fl}')
def check_slots(spec,old,new,errs,counter):
    ot=[s['time'] for s in old]; nt=[s['time'] for s in new]
    if ot==nt: return
    if len(nt)!=spec['count'] or len(new)!=len(old): errs.append(f'slots: count must stay {spec["count"]}'); return
    if any(set(s)-{'time'} for s in new): errs.append('slots: only the time field may exist'); return
    for a,b in zip(ot,nt):
        if not re.fullmatch(r'\d\d:\d\d',b): errs.append(f'slots: bad time {b}'); return
        if a!=b: counter.append(f'slots.{a}->{b}')
        if abs(hm(a)-hm(b))>spec['max_shift_minutes']: errs.append(f'slots: {a}->{b} shifts > {spec["max_shift_minutes"]} min')
        if not hm(spec['earliest'])<=hm(b)<=hm(spec['latest']): errs.append(f'slots: {b} outside {spec["earliest"]}-{spec["latest"]}')
    s=sorted(hm(t) for t in nt)
    if any(y-x<spec['min_gap_minutes'] for x,y in zip(s,s[1:])): errs.append(f'slots: gap < {spec["min_gap_minutes"]} min')
def main():
    errs=[]; counter=[]
    files=set(sh('git','diff','--name-only',BASE).stdout.split())|set(sh('git','ls-files','--others','--exclude-standard').stdout.split())
    for f in sorted(files):
        if f in ALWAYS_OK: continue
        if f not in POL['editable']:
            errs.append(f'file not editable: {f}'); continue
        old=json.loads(sh('git','show',f'{BASE}:{f}').stdout or '{}'); new=json.loads((ROOT/f).read_text()); spec=POL['editable'][f]
        for k in set(old)|set(new):
            if old.get(k)==new.get(k): continue
            if k not in spec: errs.append(f'{f}: key {k} not editable'); continue
            t=spec[k]['type']
            if t=='int_map': check_map(spec[k],old.get(k,{}),new.get(k,{}),errs,f'{f}:{k}',counter)
            elif t=='time_list': check_slots(spec[k],old.get(k,[]),new.get(k,[]),errs,counter)
            elif t=='text_list':
                if len(new[k])>spec[k]['max_items']: errs.append(f'{f}:{k}: more than {spec[k]["max_items"]} items')
                for x in new[k]:
                    if not re.search(r'\bn\s*=\s*\d+',str(x)): errs.append(f'lesson without evidence "n=": {str(x)[:60]}')
            elif t=='int_bump':
                if new[k]!=old.get(k,0)+1: errs.append(f'{f}:{k} must be old+1')
    if len(counter)>POL['max_changes_per_run']: errs.append(f'{len(counter)} changes ({", ".join(counter)}) > max {POL["max_changes_per_run"]} per run')
    if errs: print('GUARD: VIOLATION'); [print(' -',e) for e in errs]; return 1
    print('GUARD: ok | changes:',counter or 'none (log/data only)'); return 0
sys.exit(main())

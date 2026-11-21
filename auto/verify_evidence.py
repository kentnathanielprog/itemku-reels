#!/usr/bin/env python3
"""Deterministic backstop for the QC agent: the QC agent must quote evidence from the article for every claim/number;
this script checks the quotes really exist in the article text and every number in the video is supported.
usage: python3 verify_evidence.py <story.json> <qc_report.json> <article.json>
qc_report: {"verdict":"PASS|FAIL","claims":[{"text":"...","evidence":"verbatim quote from the article","derived":{"expr":"24.58/11.21"} or {"count_of":["London","Cardiff"],"value":2}?}],"issues":[...]}"""
import json,re,sys,pathlib
def norm(t): return re.sub(r'[^a-z0-9%.,$ ]','',re.sub(r'\s+',' ',t.lower().replace('’',"'").replace('“','"').replace('”','"'))).strip()
UNIT={'juta':1e6,'million':1e6,'m':1e6,'miliar':1e9,'billion':1e9,'bn':1e9,'ribu':1e3,'thousand':1e3,'k':1e3}
def nums(text):
    """all numbers in text, incl. glued to unit letters (24GB, 120Hz, 3.4M); juta/miliar/million/billion scale the value"""
    out=[]
    for m in re.finditer(r'(\d[\d.,]*)(?:\s*(juta|million|miliar|billion|ribu|thousand)\b|(m|k|bn)\b)?',text,flags=re.I):
        s=m.group(1).strip('.,')
        if not s: continue
        cands=[]
        if re.fullmatch(r'\d{1,3}(,\d{3})+(\.\d+)?',s): cands.append(float(s.replace(',','')))            # 2,474,602
        if re.fullmatch(r'\d{1,3}(\.\d{3})+(,\d+)?',s): cands.append(float(s.replace('.','').replace(',','.')))  # 2.474.602
        try: cands.append(float(s.replace(',','.')))
        except Exception: pass
        u=UNIT.get((m.group(2) or m.group(3) or '').lower(),1)
        out+= [c*u for c in cands]
    return out
def supported(v,pool,tol=0.015): return any(abs(v-p)<=tol*max(abs(p),1e-9) or v==p for p in pool)
def story_text(s):
    items=[s['hook']]+list(s['message'])+[s['gong']]
    return ' '.join(re.sub(r'\[\[|\]\]|\(\(|\)\)','',(i['text'] if isinstance(i,dict) else i)) for i in items)
def check(story,qc,article):
    P=[]; full=norm(article.get('fulltext','')+' '+article.get('desc','')+' '+article.get('title',''))
    if qc.get('verdict')!='PASS': P.append('QC verdict bukan PASS')
    pool=nums(article.get('fulltext','')+' '+article.get('desc','')+' '+article.get('title',''))
    for c in qc.get('claims',[]):
        ev=norm(c.get('evidence',''))
        if len(ev)<12: P.append(f"klaim tanpa bukti: {c.get('text','')[:50]}"); continue
        if ev not in full: P.append(f"kutipan bukti TIDAK ADA di artikel: {c.get('evidence','')[:60]!r}")
        d=c.get('derived')
        if d and 'expr' in d:
            try:
                val=eval(d['expr'],{'__builtins__':{}},{})                      # arithmetic only, e.g. 24.58/11.21
                if not isinstance(val,(int,float)): raise ValueError
                for o in re.findall(r'\d+(?:\.\d+)?',d['expr']):
                    if not supported(float(o),[p/u for p in pool for u in (1,1e3,1e6,1e9)]): P.append(f"operand turunan {o} tidak ada di artikel")
            except Exception as e: P.append(f'ekspresi turunan tidak valid: {d.get("expr")}')
    ev_pool=nums(' '.join(c.get('evidence','') for c in qc.get('claims',[])))
    derived_vals=[]
    for c in qc.get('claims',[]):
        d=c.get('derived')
        if not d: continue
        if 'expr' in d:
            try: derived_vals.append(eval(d['expr'],{'__builtins__':{}},{}))
            except Exception: pass
        if 'count_of' in d:                                   # e.g. {"count_of":["London","Manchester","Cardiff"],"value":3}: every item must be in the evidence quote
            ev=norm(c.get('evidence','')); items=d['count_of']
            if all(norm(i) in ev for i in items) and len(items)==d.get('value'): derived_vals.append(float(d['value']))
            else: P.append(f"count_of tidak cocok dengan kutipan bukti: {items}")
    clean=re.sub(r'\b[A-Z]{2,}\s?\d+\b|\b[A-Za-z]+\d+\b|[+]\d+','',story_text(story))   # names like GTA 6, PS5, S18, M7, +1
    for v in nums(clean):
        if v in (0,1) or 1900<=v<=2100: continue
        if not (supported(v,ev_pool) or supported(v,derived_vals) or any(abs(v-d)<=0.5 for d in derived_vals)):
            P.append(f'angka {v:g} di video tidak didukung kutipan bukti (atau turunan terverifikasi)')
    return P
if __name__=='__main__':
    s,q,a=[json.loads(pathlib.Path(x).read_text()) for x in sys.argv[1:4]]
    P=check(s,q,a); print('EVIDENCE OK ✓' if not P else '\n'.join('✗ '+x for x in P)); sys.exit(1 if P else 0)

#!/usr/bin/env python3
"""DAILY PRODUCER - one command. scout -> fetch -> ONE writer call (all stories) -> lint -> ONE QC call (all stories) -> evidence verifier
   -> <= N revision rounds (each = one batched writer call + one batched QC call, only for failed stories) -> render -> QA -> queue.
No sub-agents, no resumed sessions: every API call is stateless and carries only the article text + draft.
usage: python3 auto/produce.py [--dry-run] [--picks-file f.json] [--no-render] [--no-enqueue] [--day YYYY-MM-DD]
env: ANTHROPIC_API_KEY (or LLM_MOCK_DIR=auto/mock for an offline test)"""
import sys,json,subprocess,pathlib,datetime as dt,re,os,time,random
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; ST=ROOT/'state'
sys.path[:0]=[str(ROOT),str(BASE/'short')]
import llm,schemas,verify_evidence as VE,enqueue as EQ,imagepool,music,visual as V
from lint import lint
A=sys.argv[1:]; DRY='--dry-run' in A; NORENDER='--no-render' in A; NOENQ='--no-enqueue' in A
cfg=json.loads((ROOT/'config.json').read_text()); L=cfg['llm']; pb=json.loads((ST/'playbook.json').read_text())
WRITER=(ROOT/'prompts'/'writer.md').read_text(); QCP=(ROOT/'prompts'/'qc.md').read_text(); VISP=(ROOT/'prompts'/'visual.md').read_text()
VISION='--no-vision' not in A
MAXR=min(int(L.get('max_rewrite_rounds',1)),2)                    # hard cap 2
WIB=dt.timezone(dt.timedelta(hours=7)); today=dt.datetime.now(WIB).date().isoformat()
DAY=A[A.index('--day')+1] if '--day' in A else today
rng=random.Random(DAY); USAGE=[]; LOGLINES=[]
def say(m): print(m); LOGLINES.append(m)
def sh(*a,**k): return subprocess.run(list(a),capture_output=True,text=True,**k)
def slug(url,title):
    t=url.rstrip('/').split('/')[-1] or title; t=re.sub(r'^[A-Za-z0-9]{8}-','',t) if re.match(r'^[A-Za-z0-9]{8}-',t) else t
    return re.sub(r'[^a-z0-9]+','-',t.lower()).strip('-')[:38]+'-'+DAY[5:].replace('-','')
def article_text(art):
    """text sent to the LLM: paragraphs only ('clean') when it is substantial, else the page text from the headline on. Evidence is still verified against the FULL text."""
    n=int(L['article_chars']); cl=art.get('clean','')
    full=art.get('fulltext',''); t=re.sub(r'\s*\|\s*[A-Za-z .]+$','',art.get('title',''))[:40]; i=max(full.find(t),0) if t else 0; raw=full[i:i+n]
    return cl[:n] if (len(cl)>=1500 or len(cl)>=0.5*len(raw)) else raw
# ---------------- 1. picks + fetch ----------------
def clean_images(it):
    """layer 1 (free, no LLM): drop certainly-bad images; remember suspects as hints for the vision call"""
    hard,sus=V.check_images(it['images'])
    if hard: say(f"  [visual] {it['id'][:34]}: gambar dibuang otomatis {', '.join(f'#{i}:{f[0]}' for i,f in hard.items())}")
    keep=[i for i in range(len(it['images'])) if i not in hard]; it['suspect']=[keep.index(i) for i in sus if i in keep]
    it['images']=[it['images'][i] for i in keep]
    if not it['images']: say(f"  - lewati {it['id'][:34]}: tidak ada gambar layak"); return False
    return True
def load_picks():
    if '--picks-file' in A:
        items=json.loads(pathlib.Path(A[A.index('--picks-file')+1]).read_text()); out=[]
        for it in items:
            art=json.loads((BASE/it['article_dir']/'article.json').read_text()); d=BASE/'out'/it['id']; d.mkdir(parents=True,exist_ok=True)
            (d/'article.json').write_text(json.dumps(art,ensure_ascii=False)); it['art']=art; out.append(it)
        return out,[]
    import scout
    pick,pool=scout.daily_pick(verbose=True); out=[]
    for p in pick+[]: out.append(prep(p))
    spare=[x for x in pool if x['url'] not in {p['url'] for p in pick}]
    return [x for x in out if x],spare
def prep(p):
    name=slug(p['url'],p['title']); r=sh('python3','-W','ignore',str(BASE/'short'/'fetch_news.py'),p['url'],name,'6')
    f=BASE/'out'/name/'article.json'
    if r.returncode or not f.exists(): say(f"  - lewati {name}: gagal ambil artikel"); return None
    art=json.loads(f.read_text()); imgs=[str(pathlib.Path(i['file']).relative_to(BASE)) for i in art['images'] if i['w']>=1000]
    if len(imgs)<3 and p.get('entity'): imgs+=imagepool.pool(p['entity'],3-len(imgs),exclude=tuple(imgs))
    if len(imgs)<cfg.get('min_images',1) or len(art.get('fulltext',''))<500: say(f"  - lewati {name}: gambar/teks kurang"); return None
    it={'id':name,'cat':p['cat'],'entity':p.get('entity'),'images':imgs,'art':art,'url':p['url']}
    return it if clean_images(it) else None
# ---------------- 2. writer / assemble / lint ----------------
def writer_call(items,prev=None):
    payload=[]
    for it in items:
        d={'id':it['id'],'category':it['cat'],'image_count':len(it['images']),'source':it['art'].get('site',''),'title':it['art'].get('title',''),'article_text':article_text(it['art'])}
        if prev and it['id'] in prev: d['previous_draft']=prev[it['id']]['draft']; d['issues']=prev[it['id']]['issues']
        payload.append(d)
    user=json.dumps({'stories':payload},ensure_ascii=False)
    data,u=llm.call_json('writer',WRITER,user,schemas.WRITER,L['writer_model'],L['writer_effort'],8000); USAGE.append(('writer',u)); return data['stories']
def cta_for(it,k):
    exp=None; var=pb.get('default_cta','A')
    if rng.random()<pb['experiments']['share'] and pb['experiments']['active']:
        e=pb['experiments']['active'][0]; var=rng.choice(list(e['variants'])); exp={'id':e['id'],'variant':var}
    it['exp']=exp; return cfg['cta'][var].format(game=cfg['game_label'].get(it['cat'],'game'))
def assemble(it,w):
    n=len(it['images']); fix=lambda c:{'text':c['text'],'img':[i%n for i in c['img']] or [0]}
    s={'images':it['images'],'out':'short-'+it['id'],'audio':'none','mode':'blur','center_y':800,'source':re.sub(r'\s*\|.*$','',it['art'].get('site','')) or 'sumber',
       'credit':w['credit'],'hashtags':w['hashtags'],'hook':fix(w['hook']),'message':[fix(m) for m in w['message']][:2],'gong':fix(w['gong']),
       'cta':{'text':it.get('cta') or cta_for(it,0),'img':[0]},'timing':{'hook':3,'message':3,'gong':3.9,'cta':2.3},
       'topic':w['topic'],'cat':it['cat'],'hook_type':w['hook_type'],'caption_text':w['caption_text'],'experiment':it.get('exp')}
    it['cta']=s['cta']['text']
    tr=music.pick(cfg['music_mood'].get(it['cat'],[]))                 # deterministic, no LLM; silent when catalog is empty
    if tr:
        s['audio']=tr[0]['file']; s['music']=tr[0]['file']; s['music_start']=tr[0].get('start',0)
        if tr[0].get('attribution'): s['caption_text']+='\n'+tr[0]['attribution']
    return s
# ---------------- 3. QC ----------------
def qc_call(batch):
    payload=[{'id':it['id'],'video_texts':{'hook':it['story']['hook']['text'],'message':[m['text'] for m in it['story']['message']],'gong':it['story']['gong']['text'],'cta':it['story']['cta']['text']},
              'caption_text':it['story']['caption_text'],'source':it['story']['source'],'credit':it['story']['credit'],'article_text':article_text(it['art'])} for it in batch]
    data,u=llm.call_json('qc',QCP,json.dumps({'stories':payload},ensure_ascii=False),schemas.QC,L['qc_model'],L['qc_effort'],12000); USAGE.append(('qc',u)); return {r['id']:r for r in data['reports']}
def to_verify_report(r):
    cl=[]
    for c in r['claims']:
        d=None
        if c['calc_expr']: d={'expr':c['calc_expr']}
        elif c['count_items']: d={'count_of':c['count_items'],'value':c['count_value']}
        cl.append({'text':c['text'],'evidence':c['evidence'],**({'derived':d} if d else {})})
    return {'verdict':r['verdict'],'claims':cl,'issues':r['issues'],'fixes':r['fixes']}
# ---------------- 4. batch with bounded revisions ----------------
def run_batch(items,tag):
    items=list(items); passed=[]; prev={}; todo=items
    for rnd in range(MAXR+1):
        if not todo: break
        ws={w['id']:w for w in writer_call(todo,prev if rnd else None)}; need_qc=[]; prev={}
        for it in todo:
            w=ws.get(it['id'])
            if not w: prev[it['id']]={'draft':{},'issues':['penulis tidak mengembalikan story ini']}; continue
            it['story']=assemble(it,w); (BASE/'short'/'stories'/f"{it['id']}.json").write_text(json.dumps(it['story'],ensure_ascii=False,indent=1))
            P,W=lint(it['story'],BASE)
            if P: prev[it['id']]={'draft':w,'issues':['LINT: '+x for x in P]}; say(f"  [{tag}{rnd}] {it['id']}: lint ✗ {len(P)} (tidak perlu QC, langsung revisi)")
            else: need_qc.append((it,w))
        reps=qc_call([x[0] for x in need_qc]) if need_qc else {}
        for it,w in need_qc:
            r=reps.get(it['id']); 
            if not r: prev[it['id']]={'draft':w,'issues':['QC tidak mengembalikan laporan']}; continue
            vr=to_verify_report(r); d=BASE/'out'/it['id']; d.mkdir(parents=True,exist_ok=True); (d/'qc_report.json').write_text(json.dumps(vr,ensure_ascii=False,indent=1))
            probs=VE.check(it['story'],vr,it['art'])
            if r['verdict']=='PASS' and not probs: say(f"  [{tag}{rnd}] {it['id']}: LULUS (QC PASS + bukti terverifikasi)"); passed.append(it)
            else:
                iss=r['issues']+r['fixes']+['VERIFIER: '+p for p in probs]; prev[it['id']]={'draft':w,'issues':iss}
                say(f"  [{tag}{rnd}] {it['id']}: GAGAL — {(iss[0] if iss else '?')[:90]}")
        todo=[it for it in todo if it['id'] in prev and it not in passed]
    for it in todo: say(f"  x {it['id']}: dibuang setelah {MAXR} revisi")
    return passed
# ---------------- 4b. vision check (one batched call, small thumbnails) ----------------
def vision_stage(passed):
    if not passed or not VISION: return passed
    try:
        data,u=llm.call_json('visual',VISP,V.vision_content(passed),schemas.VISUAL,L.get('vision_model',L['qc_model']),'low',3000); USAGE.append(('visual',u))
    except llm.LLMError as e:
        sus=[f"{it['id'][:30]}:#{','.join(map(str,it['suspect']))}" for it in passed if it.get('suspect')]
        say(f"  ! pemeriksa visual dilewati ({str(e)[:70]}). Gambar dicurigai kartu-tulisan TIDAK terverifikasi: {sus or 'tidak ada'}"); return passed
    reps={r['id']:r for r in data['reports']}; out=[]
    for it in passed:
        r=reps.get(it['id']); drops={im['index']:im for im in (r['images'] if r else []) if im['verdict']=='drop'}
        if not drops: out.append(it); continue
        say(f"  [visual] {it['id'][:34]}: gambar dibuang AI "+', '.join(f"#{i}:{im['problem']}" for i,im in drops.items()))
        ns=V.drop_images(it['story'],list(drops))
        if ns is None: say(f"  x {it['id'][:34]}: dibuang, tidak ada gambar tersisa"); continue
        it['story']=ns; it['images']=ns['images']; (BASE/'short'/'stories'/f"{it['id']}.json").write_text(json.dumps(ns,ensure_ascii=False,indent=1)); out.append(it)
    return out
# ---------------- 5. render + queue ----------------
def finish(passed):
    slots=[s['time'] for s in cfg['slots']]; ok=[]
    for i,it in enumerate(passed):
        sp=BASE/'short'/'stories'/f"{it['id']}.json"
        if not NORENDER:
            r=sh('python3',str(BASE/'short'/'make_video.py'),'build',str(sp)); line=[l for l in r.stdout.splitlines() if 'QA' in l]
            if r.returncode or not line or 'OK' not in line[-1]: say(f"  x {it['id']}: render/QA gagal: {(line[-1] if line else r.stderr[-120:])}"); continue
        if not NOENQ:
            used={x.get('posted_slot') for x in json.loads((ST/'queue.json').read_text()) if x.get('status') in ('ready','publishing') and x['id']!=it['id'] and (x.get('not_before') or '')[:10]==DAY or False}
            free=[t for t in slots if t not in used] or slots
            try: EQ.enqueue(str(sp),free[0],DAY)
            except SystemExit as e: say(f"  x {it['id']}: ditolak antrean: {e}"); continue
        ok.append(it)
    return ok
def main():
    say(f"== produce {DAY} | model penulis {L['writer_model']} / QC {L['qc_model']} | maks revisi {MAXR}")
    items,spare=load_picks(); say(f"  berita terpilih: {len(items)}")
    for it in items: say(f"    - [{it['cat']}/{it.get('entity')}] {it['art'].get('title','')[:80]} ({it['art'].get('site','')}, {len(it['images'])} gambar)")
    if not items: say('  tidak ada berita layak -> tidak ada posting hari ini'); return 0
    if DRY:
        wsz=len(WRITER)+sum(len(article_text(i['art']))+400 for i in items); qsz=len(QCP)+sum(len(article_text(i['art']))+1200 for i in items)
        wi,qi=wsz//4,qsz//4; est=llm.cost(L['writer_model'],wi,1800)+llm.cost(L['qc_model'],qi,3000)
        say(f"  DRY-RUN: penulis ~{wi} token masuk, QC ~{qi} token masuk (perkiraan kasar chars/4); biaya satu putaran ~US${est:.3f} (tanpa revisi)"); return 0
    passed=run_batch(items,'a'); extra=0
    while len(passed)<cfg['per_day'] and spare and extra<int(L.get('max_replacements',1)):
        extra+=1; need=cfg['per_day']-len(passed); cand=[]; 
        for p in spare:
            if len(cand)>=need: break
            if any(p.get('entity') and p['entity']==q.get('entity') for q in passed): continue
            x=prep(p) if '--picks-file' not in A else None
            if x: cand.append(x)
        spare=[p for p in spare if p['url'] not in {c['url'] for c in cand}]
        if cand: say(f"  pengganti: {len(cand)} berita"); passed+=run_batch(cand,'r')
    passed=vision_stage(passed)
    ok=finish(passed)
    tot=sum(u['usd'] for _,u in USAGE); tin=sum(u['in']+u['cache_read']+u['cache_write'] for _,u in USAGE); tout=sum(u['out'] for _,u in USAGE)
    say(f"== selesai: {len(ok)}/{cfg['per_day']} video siap/antre | {len(USAGE)} panggilan API | {tin} token masuk, {tout} keluar | biaya ~US${tot:.3f}")
    (ST/'runlog'/f'{DAY}.json').write_text(json.dumps({'day':DAY,'ok':[i['id'] for i in ok],'calls':[(r,u) for r,u in USAGE],'lines':LOGLINES},ensure_ascii=False,indent=1)); return 0
try: sys.exit(main())
except llm.LLMError as e: print(f'BERHENTI: {e}'); sys.exit(2)

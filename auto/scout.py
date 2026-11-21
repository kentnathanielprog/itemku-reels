#!/usr/bin/env python3
"""Scout (deterministic, no LLM): fresh + safe + non-duplicate candidates per slot category.
usage: python3 scout.py [--cat mlbb] [--n 5]      -> writes state/candidates.json and prints a compact list"""
import json,re,sys,subprocess,datetime as dt,urllib.request,html,pathlib,difflib
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; ST=ROOT/'state'
cfg=json.loads((ROOT/'config.json').read_text()); hist=json.loads((ST/'history.json').read_text())
for _q in json.loads((ST/'queue.json').read_text()):          # queued (not yet posted) items count as used too
    if _q.get('status') in ('ready','publishing','posted'): hist.append({'url':_q.get('source_url'),'title':_q.get('topic') or '','date':_q.get('not_before') or '2000-01-01T00:00:00+00:00'})
DENY=re.compile(r'\b('+'|'.join(re.escape(w) for w in cfg['denylist'])+r')\b',re.I)
def get(u): return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read().decode('utf-8','ignore')
def meta(page,*keys):
    for k in keys:
        m=re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"'%k,page) or re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"'%k,page)
        if m: return html.unescape(m.group(1))
def age_hours(iso):
    try: d=dt.datetime.fromisoformat(iso.replace('Z','+00:00').replace('+0700','+07:00'))
    except Exception: return None
    if d.tzinfo is None: d=d.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc)-d).total_seconds()/3600
def toks(t): return {w for w in re.findall(r'[a-z0-9+]{3,}',t.lower()) if w not in ('the','and','for','with','yang','dan','dari','untuk','game','games')}
def is_dup(title,url):
    now=dt.datetime.now(dt.timezone.utc); cd=dt.timedelta(hours=cfg.get('entity_cooldown_h',24)); ent=entity(title)
    for h in hist:                                   # same entity (e.g. gta) used in the last N hours -> skip, even with a different headline
        try: when=dt.datetime.fromisoformat(h['date'])
        except Exception: continue
        if when.tzinfo is None: when=when.replace(tzinfo=dt.timezone.utc)
        if ent and abs((now-when).total_seconds())<cd.total_seconds() and entity(h['title'])==ent: return True
    cut=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=cfg['dup_days'])
    for h in hist:
        try: when=dt.datetime.fromisoformat(h['date'])
        except Exception: continue
        if when.tzinfo is None: when=when.replace(tzinfo=dt.timezone.utc)
        if when<cut: continue
        if h['url']==url or difflib.SequenceMatcher(None,h['title'].lower(),title.lower()).ratio()>=0.6: return True
        a,b=toks(h['title']),toks(title)
        if a and b and len(a&b)/len(a|b)>=0.5: return True
    return False
SRC=json.loads((BASE/'short'/'sources.json').read_text())
def classify(title,url,default):
    hay=(title+' '+url.rsplit('/',1)[-1].replace('-',' ')).lower()
    for c,v in SRC.items():
        if c!='general' and any(k in hay for k in v['keywords']): return c
    return 'general'
def entity(title):
    t=title.lower()
    for e in cfg.get('entities',[]):
        if re.search(r'\b'+re.escape(e)+r'\b',t): return {'ps5':'playstation','grand theft auto':'gta','rockstar':'gta','mpl':'mlbb','mobile legends':'mlbb'}.get(e,e)
    return None
def found(cat,n):
    out=subprocess.run(['python3',str(BASE/'short'/'find_news.py'),cat,str(n)],capture_output=True,text=True).stdout.splitlines()
    return [tuple(x.rsplit(' | ',1)) for x in out if ' | ' in x]
def scout(cat,n=5,maxcheck=18):
    res=[];why={}
    for title,url in found(cat,maxcheck):
        try: page=get(url)
        except Exception: why[url]='fetch-fail'; continue
        t=meta(page,'og:title','twitter:title') or title; desc=meta(page,'og:description','description') or ''
        date=meta(page,'article:published_time','og:updated_time') or ''; a=age_hours(date)
        if a is None: why[url]='no-date'; continue
        if a>cfg.get('freshness_override',{}).get(cat,cfg['freshness_hours']) or a<-2: why[url]=f'old({a:.0f}h)'; continue
        if DENY.search(t+' '+desc+' '+url): why[url]='denylist'; continue
        if is_dup(t,url): why[url]='duplicate'; continue
        res.append({'cat':classify(t,url,cat),'entity':entity(t),'title':t,'url':url,'date':date,'age_h':round(a),'site':meta(page,'og:site_name') or ''})
        if len(res)>=n: break
    return res,why
IMPACT=re.compile(r'record|rekor|champion|juara|release|rilis|update|launch|billion|miliar|million|juta|\d+%|viral|fastest|terbesar|new|baru',re.I)
def score(x,pb):
    weak=-30 if any(d in x['url'] for d in cfg.get('weak_image_domains',[])) else 0   # sources whose only image is a text card look poor when cropped
    return weak+max(min(100-x['age_h'],100),-60)+pb.get('cat_weights',{}).get(x['cat'],0)*10+cfg.get('cat_bonus',{}).get(x['cat'],0)+(8 if IMPACT.search(x['title']) else 0)
def select(pool,pb,k,maxc):
    """greedy, diversity-aware: each pick of a category lowers the next pick of the same category; hard cap per category"""
    chosen=[]; cnt={}; ents=set()
    while pool and len(chosen)<k:
        best=max((x for x in pool if cnt.get(x['cat'],0)<maxc and (x.get('entity') is None or x['entity'] not in ents)),key=lambda x:score(x,pb)-25*cnt.get(x['cat'],0)-(15 if chosen and chosen[-1]['cat']==x['cat'] else 0),default=None)
        if not best: break
        chosen.append(best); cnt[best['cat']]=cnt.get(best['cat'],0)+1
        if best.get('entity'): ents.add(best['entity'])
        pool=[x for x in pool if x['url']!=best['url'] and not (difflib.SequenceMatcher(None,x['title'].lower(),best['title'].lower()).ratio()>=0.6)]
    return chosen
def daily_pick(n=6,verbose=False):
    pb=json.loads((ST/'playbook.json').read_text()); pool=[]
    for c in cfg['categories']:
        r,w=scout(c,n); pool+=r
        if verbose: print(f"  scout {c}: {len(r)} kandidat")
    pool=list({x['url']:x for x in pool}.values())
    pick=select(list(pool),pb,cfg['per_day'],cfg['max_per_cat_per_day'])
    return pick,pool
if __name__=='__main__':
    a=sys.argv[1:]; n=int(a[a.index('--n')+1]) if '--n' in a else 6
    pb=json.loads((ST/'playbook.json').read_text()); pool=[]; summary=[]
    for c in cfg['categories']:
        r,w=scout(c,n); pool+=r; summary.append(f"{c}: {len(r)} kandidat"+(f" (ditolak: {', '.join(sorted(set(w.values())))})" if w else ''))
    pool=list({x['url']:x for x in pool}.values())
    pick=select(list(pool),pb,cfg['per_day'],cfg['max_per_cat_per_day'])
    for i,x in enumerate(pick): x['slot']=cfg['slots'][i]['time'] if i<len(cfg['slots']) else None
    (ST/'candidates.json').write_text(json.dumps(pool,ensure_ascii=False,indent=1)); (ST/'today.json').write_text(json.dumps(pick,ensure_ascii=False,indent=1))
    print('POOL  '+' | '.join(summary)); print(f"PILIHAN HARI INI ({len(pick)}/{cfg['per_day']}):")
    for x in pick: print(f"  {x['slot']} [{x['cat']}/{x.get('entity')}] {x['age_h']}h | {x['title'][:78]} | {x['url']}")
    if len(pick)<cfg['per_day']: print(f"! hanya {len(pick)} berita layak: slot sisa dilewati (tidak dipaksa).")

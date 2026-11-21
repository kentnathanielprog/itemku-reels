#!/usr/bin/env python3
"""Learning collector (deterministic, READ-ONLY toward Instagram): pulls Insights (reach + plays/views) of every published Reel
and appends one snapshot row per Reel to data/performance.jsonl.
usage: python3 learning/collect.py [--dry-run] [--limit N]    env: IG_ACCESS_TOKEN (never printed), GRAPH_HOST (graph.facebook.com), GRAPH_VERSION (v21.0)
Metric note: Meta replaced `plays` with `views` on newer API versions; we request reach,views first, and fall back to reach,plays. The value is stored as `plays`
(+ `plays_metric` says which API metric it came from). A Reel with no readable metric is skipped and logged, never written with guesses."""
import json,os,re,sys,subprocess,pathlib,datetime as dt,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent.parent; ST=ROOT/'auto'/'state'; OUT=ROOT/'data'/'performance.jsonl'
DRY='--dry-run' in sys.argv; LIMIT=int(sys.argv[sys.argv.index('--limit')+1]) if '--limit' in sys.argv else 10**6
HOST=os.environ.get('GRAPH_HOST','graph.facebook.com'); VER=os.environ.get('GRAPH_VERSION','v21.0'); TOK=os.environ.get('IG_ACCESS_TOKEN','')
WIB=dt.timezone(dt.timedelta(hours=7))
def scrub(s): return re.sub(r'access_token=[^&\s"\']+','access_token=***',str(s)).replace(TOK,'***') if TOK else re.sub(r'access_token=[^&\s"\']+','access_token=***',str(s))
def get_insights(media_id):
    last=None
    for pm in ('views','plays'):
        u=f"https://{HOST}/{VER}/{media_id}/insights?metric=reach,{pm}&access_token={TOK}"
        try: r=json.loads(urllib.request.urlopen(u,timeout=60).read())
        except urllib.error.HTTPError as e: last=f'HTTP {e.code} {scrub(e.read().decode()[:160])}'; continue
        except Exception as e: last=f'{type(e).__name__}'; continue
        v={d['name']:(d.get('values') or [{}])[0].get('value') for d in r.get('data',[])}
        if v.get('reach') is not None and v.get(pm) is not None: return {'reach':v['reach'],'plays':v[pm],'plays_metric':pm},None
        last=f'metric kosong ({pm})'
    return None,last
def duration_s(p):
    f=ROOT/(p.get('video') or '')
    if p.get('video') and f.exists():
        try: return round(float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(f)],capture_output=True,text=True,timeout=30).stdout.strip()),1)
        except Exception: pass
    return None
def main():
    posts=json.loads((ST/'posts.json').read_text()); now=dt.datetime.now(dt.timezone.utc); rows=[]; skipped=[]
    for p in [x for x in posts if x.get('media_id') and x.get('posted_at')][:LIMIT]:
        pa=dt.datetime.fromisoformat(p['posted_at']); age=round((now-pa).total_seconds()/3600,1)
        base={'at':now.isoformat(timespec='seconds'),'media_id':p['media_id'],'id':p.get('id'),'posted_at':p['posted_at'],'age_h':age,'format':'reel',
              'cat':p.get('cat'),'hook_type':p.get('hook_type'),'topic':p.get('topic'),'n_images':p.get('n_images'),'music':bool(p.get('music')),
              'duration_s':duration_s(p),'hour_wib':pa.astimezone(WIB).hour,'scheduled_slot':p.get('posted_slot')}
        if DRY: print(f"[dry-run] insights {p['media_id']} age={age}h reach,views|plays (tidak ada panggilan jaringan)"); continue
        if not TOK: skipped.append((p['media_id'],'IG_ACCESS_TOKEN not set')); continue
        m,err=get_insights(p['media_id'])
        if m is None: skipped.append((p['media_id'],err)); continue
        rows.append({**base,**m})
    if rows:
        OUT.parent.mkdir(exist_ok=True)
        with OUT.open('a') as f:
            for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'snapshot ditulis: {len(rows)} | dilewati: {len(skipped)}'+(' (dry-run)' if DRY else ''))
    for mid,e in skipped: print(f'  skip {mid}: {e}')
    return 0 if (rows or DRY or not skipped) else 1
sys.exit(main())

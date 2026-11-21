#!/usr/bin/env python3
"""Insights collector (deterministic): pulls Reels metrics 24h+ after posting into state/metrics.json for the Learner agent.
usage: python3 insights.py [--dry-run]   env: IG_ACCESS_TOKEN, GRAPH_HOST, GRAPH_VERSION
Metric names change between API versions -> verify against current docs; list lives in METRICS."""
import json,os,sys,pathlib,datetime as dt,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent; ST=ROOT/'state'; DRY='--dry-run' in sys.argv
HOST=os.environ.get('GRAPH_HOST','graph.instagram.com'); VER=os.environ.get('GRAPH_VERSION','v21.0'); TOK=os.environ.get('IG_ACCESS_TOKEN','')
METRICS='views,reach,likes,comments,shares,saved,total_interactions,ig_reels_avg_watch_time'
posts=json.loads((ST/'posts.json').read_text()); met=json.loads((ST/'metrics.json').read_text()); now=dt.datetime.now(dt.timezone.utc)
for p in posts:
    if not p.get('media_id'): continue
    age=(now-dt.datetime.fromisoformat(p['posted_at'])).total_seconds()/3600
    for tag,lo in (('24h',24),('72h',72),('7d',168)):
        if age<lo or any(m['media_id']==p['media_id'] and m['stage']==tag for m in met): continue
        if DRY: print(f"[dry-run] insights {p['media_id']} stage={tag}"); continue
        r=json.loads(urllib.request.urlopen(f"https://{HOST}/{VER}/{p['media_id']}/insights?metric={METRICS}&access_token={TOK}",timeout=60).read())
        vals={d['name']:d['values'][0]['value'] for d in r.get('data',[])}
        met.append({'media_id':p['media_id'],'id':p['id'],'stage':tag,'at':now.isoformat(),**vals})
(ST/'metrics.json').write_text(json.dumps(met,ensure_ascii=False,indent=1)); print(f'metrics: {len(met)} rows')

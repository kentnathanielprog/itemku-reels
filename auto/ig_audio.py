"""Pick a trending / mood-matched track from Instagram's own Audio API (rights are handled by Instagram; only tracks 'authorized for third party use' are returned).
Docs: https://developers.facebook.com/documentation/instagram-platform/content-publishing/audio-api  (read 2026-11-21, page updated 2026-06-16)
  GET  /ig_audio?audio_type=music&user_id=..&[search_query=..]&access_token=..   (no search_query = trending)
  POST /{ig-user-id}/media  ... audio_configuration={"audio_id":..,"audio_volume":1-100,"video_volume":1-100}
Needs the Instagram API with Facebook Login (or Unified Login), NOT Instagram Login: IG Business/Creator account + connected Facebook Page,
permissions instagram_basic + instagram_content_publish. Not verified live (no token yet): Indonesian availability, resumable upload + audio_configuration.
Pure selection logic here so it is testable offline; publish.py supplies the HTTP search function."""
import json,random,re,time,pathlib
ROOT=pathlib.Path(__file__).resolve().parent; ST=ROOT/'state'
def recent_ids(posts,days=14,now=None):
    now=now or time.time(); out=set()
    for p in posts:
        m=p.get('music') or {}
        if isinstance(m,dict) and m.get('audio_id'): out.add(str(m['audio_id']))
    return out
def denied(x,cfg):
    """titles/artists that look like game theme songs, covers or fan imitations are not brand-safe (copyright look-alikes, wrong game)"""
    pats=cfg.get('audio',{}).get('deny',[])
    hay=(str(x.get('title',''))+' '+str(x.get('display_artist',''))).lower()
    return any(re.search(p if '\\' in p else r'\b'+re.escape(p)+r'\b',hay) for p in pats)
def pick(search,cat,cfg,posts,min_ms=20000,rng=random):
    """search(query|None) -> list of audio dicts. Tries mood queries for the category, then trending. Skips recently used / too short / unknown ids.
    Returns {'audio_id','title','artist','audio_volume','video_volume'} or None (then the Reel is posted silent)."""
    a=cfg.get('audio',{}); qs=list(a.get('queries',{}).get(cat) or a.get('queries',{}).get('default') or []); rng.shuffle(qs); used=recent_ids(posts)
    for q in qs[:3]+[None]:
        try: res=search(q) or []
        except Exception: continue
        ok=[x for x in res if x.get('audio_id') and str(x['audio_id']) not in used and (x.get('duration_in_ms') or 0)>=min_ms and x.get('audio_type','music')=='music' and not denied(x,cfg)]
        if ok:
            ok.sort(key=lambda x:0 if x.get('is_ads_eligible') else 1)       # prefer tracks that can also be boosted as ads
            x=rng.choice(ok[:5])
            return {'audio_id':str(x['audio_id']),'title':x.get('title',''),'artist':x.get('display_artist',''),'audio_volume':int(a.get('audio_volume',70)),'video_volume':100}
    return None
def config_param(sel): return json.dumps({'audio_id':sel['audio_id'],'audio_volume':sel['audio_volume'],'video_volume':sel['video_volume']})

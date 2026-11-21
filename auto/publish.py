#!/usr/bin/env python3
"""Uploader (deterministic, no LLM): posts the next due video from state/queue.json to Instagram Reels via the official Graph API.
usage: python3 publish.py [--dry-run] [--force]
env: IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_HOST (default graph.instagram.com), GRAPH_VERSION (default v21.0)
Idempotent: a half-finished post (container created) is resumed, never duplicated. Kill switch: file auto/STOP or env STOP=1.
!! Endpoint/field names follow Meta's public docs at time of writing - verify against the current Reels publishing docs. !!"""
import json,os,sys,time,pathlib,datetime as dt,urllib.request,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; ST=ROOT/'state'
DRY='--dry-run' in sys.argv; FORCE='--force' in sys.argv
HOST=os.environ.get('GRAPH_HOST','graph.facebook.com')   # Audio API needs Facebook Login host (not Instagram Login); VER=os.environ.get('GRAPH_VERSION','v21.0')
UID=os.environ.get('IG_USER_ID','<IG_USER_ID>'); TOK=os.environ.get('IG_ACCESS_TOKEN','')
def rj(f): return json.loads((ST/f).read_text())
def wj(f,d): (ST/f).write_text(json.dumps(d,ensure_ascii=False,indent=1))
def call(method,url,data=None,headers=None,raw=None):
    if DRY: print(f'  [dry-run] {method} {url.split("?")[0]}  {json.dumps(data)[:140] if data else ""}'); return {'id':'DRY','uri':'https://rupload.example/DRY','status_code':'FINISHED','permalink':'https://instagram.com/reel/DRY'}
    body=raw if raw is not None else (urllib.parse.urlencode(data).encode() if data else None)
    req=urllib.request.Request(url,data=body,method=method,headers=headers or {}); 
    try: return json.loads(urllib.request.urlopen(req,timeout=120).read().decode())
    except urllib.error.HTTPError as e: raise SystemExit(f'HTTP {e.code}: {e.read().decode()[:300]}')
def main():
    if (ROOT/'STOP').exists() or os.environ.get('STOP')=='1': print('STOP aktif: tidak ada posting.'); return 0
    q=rj('queue.json'); now=dt.datetime.now(dt.timezone.utc)
    due=[x for x in q if x['status'] in ('ready','publishing') and (FORCE or dt.datetime.fromisoformat(x['not_before'])<=now)]
    if not due: print('Tidak ada video jatuh tempo.'); return 0
    it=sorted(due,key=lambda x:x['not_before'])[0]; vid=BASE/it['video']; caption=it['caption']
    print(f"posting: {it['id']} ({vid.name}, {vid.stat().st_size/1e6:.1f}MB)")
    base=f'https://{HOST}/{VER}/{UID}'
    if not it.get('container'):
        body={'media_type':'REELS','upload_type':'resumable','caption':caption,'share_to_feed':'true','access_token':TOK}
        cfg=json.loads((ROOT/'config.json').read_text())
        if cfg.get('audio',{}).get('enabled'):                                          # trending/mood track from Instagram's Audio API (opt-in until proven live)
            import ig_audio
            def search(q):
                if DRY: return [{'audio_id':'DRY','title':'(dry-run)','display_artist':'','duration_in_ms':60000}]
                u=f"https://{HOST}/{VER}/ig_audio?audio_type=music&user_id={UID}&access_token={TOK}"+(f"&search_query={urllib.parse.quote(q)}" if q else '')
                return call('GET',u).get('audio',[])
            sel=ig_audio.pick(search,it.get('cat'),cfg,rj('posts.json'))
            if sel: body['audio_configuration']=ig_audio.config_param(sel); it['music']={k:sel[k] for k in ('audio_id','title','artist')}; print(f"  musik: {sel['title']} - {sel['artist']}")
            else: print('  musik: tidak ada yang cocok, diposting senyap')
        r=call('POST',base+'/media',body)
        it['container']=r['id']; it['status']='publishing'
        if not DRY: wj('queue.json',q)                      # dry-run must never touch state
        size=vid.stat().st_size
        call('POST',r['uri'],headers={'Authorization':f'OAuth {TOK}','offset':'0','file_size':str(size)},raw=None if DRY else vid.read_bytes())
    for _ in range(60):                                                          # wait until Meta finished processing the video
        s=call('GET',f"https://{HOST}/{VER}/{it['container']}?fields=status_code&access_token={TOK}")
        if s.get('status_code')=='FINISHED': break
        if s.get('status_code') in ('ERROR','EXPIRED'): it['status']='failed'; wj('queue.json',q); raise SystemExit(f'processing {s}')
        time.sleep(5)
    pub=call('POST',base+'/media_publish',{'creation_id':it['container'],'access_token':TOK})
    info=call('GET',f"https://{HOST}/{VER}/{pub['id']}?fields=permalink,timestamp&access_token={TOK}")
    if DRY: print('  [dry-run] selesai, antrean TIDAK diubah.'); return 0
    it.update(status='posted',media_id=pub['id'],permalink=info.get('permalink'),posted_at=now.isoformat()); wj('queue.json',q)
    posts=rj('posts.json'); posts.append({k:it.get(k) for k in ('id','media_id','permalink','posted_at','cat','topic','hook_type','music','experiment','n_images','posted_slot','video')}); wj('posts.json',posts)
    h=rj('history.json'); h.append({'url':it.get('source_url'),'title':it.get('topic'),'date':now.isoformat(),'cat':it.get('cat')}); wj('history.json',h)
    print('terkirim:',it['permalink']); return 0
sys.exit(main())

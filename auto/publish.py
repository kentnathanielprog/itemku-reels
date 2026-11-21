#!/usr/bin/env python3
"""Uploader (deterministic, no LLM): posts the next due video from state/queue.json to Instagram Reels via the official Graph API.
usage: python3 publish.py [--dry-run] [--force]
env: IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_HOST (default graph.facebook.com), GRAPH_VERSION (default v21.0)
Idempotent: a half-finished post (container created) is resumed, never duplicated. Kill switch: file auto/STOP or env STOP=1.
!! Endpoint/field names follow Meta's public docs at time of writing - verify against the current Reels publishing docs. !!"""
import json,os,sys,time,re,pathlib,datetime as dt,urllib.request,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; ST=ROOT/'state'
DRY='--dry-run' in sys.argv; FORCE='--force' in sys.argv
HOST=os.environ.get('GRAPH_HOST','graph.facebook.com'); VER=os.environ.get('GRAPH_VERSION','v21.0')
UID=os.environ.get('IG_USER_ID','<IG_USER_ID>'); TOK=os.environ.get('IG_ACCESS_TOKEN','')
def rj(f): return json.loads((ST/f).read_text())
def wj(f,d): (ST/f).write_text(json.dumps(d,ensure_ascii=False,indent=1))
def call(method,url,data=None,headers=None,raw=None):
    if DRY: print(f'  [dry-run] {method} {url.split("?")[0]}  {json.dumps({k:("***" if k=="access_token" else (str(v)[:24]+"..." if k=="caption" else v)) for k,v in data.items()}) if data else ""}'); return {'id':'DRY','uri':'https://rupload.example/DRY','status_code':'FINISHED','permalink':'https://instagram.com/reel/DRY'}
    body=raw if raw is not None else (urllib.parse.urlencode(data).encode() if data else None)
    req=urllib.request.Request(url,data=body,method=method,headers=headers or {}); 
    try: return json.loads(urllib.request.urlopen(req,timeout=120).read().decode())
    except urllib.error.HTTPError as e: raise SystemExit(f'HTTP {e.code}: {e.read().decode()[:300]}')
def _norm(s): return re.sub(r'\s+',' ',s or '').strip()
def already_on_instagram(it):
    """Idempotency against Instagram itself. If an earlier run posted live but its state push failed, the item is still 'ready' in a fresh container;
    without this check it would be posted twice. Fails CLOSED: if the account cannot be read, nothing is posted."""
    try: r=call('GET',f"https://{HOST}/{VER}/{UID}/media?fields=id,caption,permalink,timestamp&limit=30&access_token={TOK}")
    except SystemExit as e: raise SystemExit(f'ABORT: akun IG tidak bisa diperiksa ({e}); tidak memposting.')
    except Exception as e: raise SystemExit(f'ABORT: akun IG tidak bisa diperiksa ({type(e).__name__}); tidak memposting.')
    want=_norm(it['caption'])
    for m in r.get('data',[]):
        if _norm(m.get('caption'))==want: return m
    return None
def record_posted(q,it,media_id,permalink,when):
    it.update(status='posted',media_id=media_id,permalink=permalink,posted_at=when.isoformat()); wj('queue.json',q)
    posts=rj('posts.json')
    if media_id not in {x.get('media_id') for x in posts}: posts.append({k:it.get(k) for k in ('id','media_id','permalink','posted_at','cat','topic','hook_type','music','experiment','n_images','posted_slot','video')}); wj('posts.json',posts)
    h=rj('history.json'); h.append({'url':it.get('source_url'),'title':it.get('topic'),'date':when.isoformat(),'cat':it.get('cat')}); wj('history.json',h)
def main():
    if (ROOT/'STOP').exists() or os.environ.get('STOP')=='1': print('STOP aktif: tidak ada posting.'); return 0
    q=rj('queue.json'); now=dt.datetime.now(dt.timezone.utc)
    due=[x for x in q if x['status'] in ('ready','publishing') and (FORCE or dt.datetime.fromisoformat(x['not_before'])<=now)]
    if not due: print('Tidak ada video jatuh tempo.'); return 0
    if '--id' in sys.argv: due=[x for x in due if x['id']==sys.argv[sys.argv.index('--id')+1]]       # post one specific queued item
    if not due: print('Tidak ada video jatuh tempo.'); return 0
    it=sorted(due,key=lambda x:x['not_before'])[0]; vid=BASE/it['video']; caption=it['caption']
    print(f"posting: {it['id']} ({vid.name}, {vid.stat().st_size/1e6:.1f}MB)")
    if not DRY:
        m=already_on_instagram(it)
        if m:                                                                    # already live (earlier state push failed): record it, never post again
            try: when=dt.datetime.fromisoformat(m['timestamp'])
            except Exception: when=now
            record_posted(q,it,m['id'],m.get('permalink'),when); print(f"sudah tayang di Instagram, status dipulihkan tanpa posting ulang: {it['id']} {m.get('permalink')}"); return 0
    base=f'https://{HOST}/{VER}/{UID}'
    if not it.get('container'):
        cfg=json.loads((ROOT/'config.json').read_text())
        body={'media_type':'REELS','upload_type':'resumable','caption':caption,'share_to_feed':'true','thumb_offset':str(int(cfg.get('cover_offset_ms',2000))),'access_token':TOK}   # RULE: cover = frame at second 2 (thumb_offset, ms)
        use_url=False
        if cfg.get('audio',{}).get('enabled'):                                          # trending/mood track from Instagram's Audio API (opt-in until proven live)
            import ig_audio
            def search(q):
                if DRY and not TOK: return [{'audio_id':'DRY','title':'(dry-run, tanpa token)','display_artist':'','duration_in_ms':60000}]
                u=f"https://{HOST}/{VER}/ig_audio?audio_type=music&user_id={UID}&access_token={TOK}"+(f"&search_query={urllib.parse.quote(q)}" if q else '')
                if DRY:                                                                  # read-only GET is safe in dry-run
                    try: return json.loads(urllib.request.urlopen(u,timeout=30).read()).get('audio',[])
                    except Exception as e: print(f'  (cari lagu gagal: {type(e).__name__})'); return []
                return call('GET',u).get('audio',[])
            sel=ig_audio.pick(search,it.get('cat'),cfg,rj('posts.json'))
            if sel:
                vb=cfg['audio'].get('video_url_base','').rstrip('/'); url=f"{vb}/{it['video']}" if vb else ''
                ok_url=False
                if url:                                                                  # Meta fetches video_url itself: it must be public and really serve the file
                    try: h=urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30); ok_url=h.status==200 and int(h.headers.get('Content-Length','0'))>100000
                    except Exception as e: print(f'  (video_url tidak bisa diambil: {type(e).__name__})')
                if ok_url:     # audio_configuration is only documented with video_url, NOT with upload_type=resumable (it was silently ignored there, tested 2026-11-21)
                    body.pop('upload_type'); body['video_url']=url; body['audio_configuration']=ig_audio.config_param(sel); use_url=True
                    it['music']={k:sel[k] for k in ('audio_id','title','artist')}; print(f"  musik: {sel['title']} - {sel['artist']} (via video_url)")
                else: print('  musik: video_url tidak tersedia, diposting senyap lewat unggah bertahap')
            else: print('  musik: tidak ada yang cocok, diposting senyap')
        r=call('POST',base+'/media',body)
        it['container']=r['id']; it['status']='publishing'
        if not DRY: wj('queue.json',q)                      # dry-run must never touch state
        if not use_url:
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
    record_posted(q,it,pub['id'],info.get('permalink'),now)
    print('terkirim:',it['permalink']); return 0
sys.exit(main())

#!/usr/bin/env python3
"""Uploader (deterministic, no LLM): posts the next due video from state/queue.json to Instagram Reels via the official Graph API.
usage: python3 publish.py [--dry-run] [--force] [--ignore-burst] [--allow-duplicate --id <queue id>] [--id <queue id>]
  --allow-duplicate = MANUAL, ONE ITEM ONLY: skip the 'caption already live on Instagram' check for the item named by --id (a deliberate replacement repost). Requires env ALLOW_FORCE=1 and --id;
    it does NOT lift the burst guard or not_before. Scheduled routines cannot use it (scripts/session_run.sh refuses it).
  --force = MANUAL ONLY: also post an item whose not_before has not arrived. --ignore-burst = MANUAL ONLY: skip the burst guard.
  Burst guard (always on otherwise; config.json -> publish_guard, defaults 3/day, 60 min): max 3 posts per WIB day and >= 60 min since the last post.
env: IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_HOST (default graph.facebook.com), GRAPH_VERSION (default v21.0)
Idempotent: a half-finished post (container created) is resumed, never duplicated. Kill switch: file auto/STOP or env STOP=1.
!! Endpoint/field names follow Meta's public docs at time of writing - verify against the current Reels publishing docs. !!"""
import json,os,sys,time,re,pathlib,datetime as dt,urllib.request,urllib.parse
import ig_audio
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; ST=ROOT/'state'
DRY='--dry-run' in sys.argv; FORCE='--force' in sys.argv; IGNORE_BURST='--ignore-burst' in sys.argv; ALLOW_DUP='--allow-duplicate' in sys.argv
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
def burst_block(q,now):
    """Reason string if posting now would break the burst guard (max per WIB day, min gap since the last post), else None."""
    g=json.loads((ROOT/'config.json').read_text()).get('publish_guard',{}); mx=int(g.get('max_per_day',3)); gap=int(g.get('min_gap_minutes',60))
    wib=dt.timezone(dt.timedelta(hours=7)); seen=[]
    for src in (rj('posts.json'),q):
        for p in src:
            if p.get('posted_at') and (src is not q or p.get('status')=='posted'):
                try: seen.append(dt.datetime.fromisoformat(p['posted_at']))
                except Exception: pass
    seen=sorted(set(seen)); today=[x for x in seen if x.astimezone(wib).date()==now.astimezone(wib).date()]
    if len(today)>=mx: return f'batas {mx} posting per hari (WIB) tercapai: {len(today)} sudah terbit hari ini'
    if seen and now-seen[-1]<dt.timedelta(minutes=gap): return f'jarak minimal {gap} menit antar posting belum terpenuhi: posting terakhir {int((now-seen[-1]).total_seconds()//60)} menit lalu'
    return None
def choose_ig_song(it,cfg,vid):
    """Pick a song from Instagram's Audio API for this Reel and make sure Meta can fetch the video by URL. Returns the selection (with 'url') or None -> caller uses our own track."""
    import hashlib
    def search(q):
        if DRY and not TOK: return [{'audio_id':'DRY','title':'(dry-run, tanpa token)','display_artist':'','duration_in_ms':60000}]
        u=f"https://{HOST}/{VER}/ig_audio?audio_type=music&user_id={UID}&access_token={TOK}"+(f"&search_query={urllib.parse.quote(q)}" if q else '')
        try: return (json.loads(urllib.request.urlopen(u,timeout=30).read()) if DRY else call('GET',u)).get('audio',[])
        except SystemExit as e: print(f'  (cari lagu Instagram gagal: {str(e)[:100]})'); return []
        except Exception as e: print(f'  (cari lagu Instagram gagal: {type(e).__name__})'); return []
    sel=ig_audio.pick(search,it.get('cat'),cfg,rj('posts.json'))
    if not sel: print('  musik Instagram: tidak ada lagu yang cocok: pakai lagu buatan sendiri'); return None
    vb=cfg['audio'].get('video_url_base','').rstrip('/')
    if not vb or not vid.exists(): print('  musik Instagram: video_url tidak tersedia: pakai lagu buatan sendiri'); return None
    data=vid.read_bytes(); url=f"{vb}/{it['video']}?v={hashlib.sha1(data).hexdigest()[:12]}"           # cache-bust: raw.githubusercontent caches ~5 min and the path was reused
    if DRY and not TOK: print('  [dry-run, tanpa token] video_url tidak diperiksa'); sel['url']=url; return sel               # offline self-test must not touch the network
    try: h=urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30); ok=h.status==200 and int(h.headers.get('Content-Length','0'))==len(data)    # Meta fetches it itself: must be public AND be exactly this file
    except Exception as e: print(f'  (video_url tidak bisa diambil: {type(e).__name__})'); ok=False
    if not ok: print('  musik Instagram: video_url belum menyajikan berkas yang benar: pakai lagu buatan sendiri'); return None
    sel['url']=url; return sel
def main():
    if (ROOT/'STOP').exists() or os.environ.get('STOP')=='1': print('STOP aktif: tidak ada posting.'); return 0
    if ALLOW_DUP and (os.environ.get('ALLOW_FORCE')!='1' or '--id' not in sys.argv): print('ABORT: --allow-duplicate hanya untuk panggilan manual: butuh env ALLOW_FORCE=1 dan --id <id item>. Tidak ada yang diposting.'); return 2
    q=rj('queue.json'); now=dt.datetime.now(dt.timezone.utc)
    due=[x for x in q if x['status'] in ('ready','publishing') and (FORCE or dt.datetime.fromisoformat(x['not_before'])<=now)]
    if not due:
        nxt=sorted((x for x in q if x['status']=='ready'),key=lambda x:x['not_before'])
        print('Tidak ada video jatuh tempo.'+(f" Berikutnya: {nxt[0]['id']} pada {nxt[0]['not_before']} (belum tiba; --force hanya untuk panggilan manual)." if nxt else '')); return 0
    if '--id' in sys.argv: due=[x for x in due if x['id']==sys.argv[sys.argv.index('--id')+1]]       # post one specific queued item
    if not due: print('Tidak ada video jatuh tempo.'); return 0
    it=None; skipped=[]
    for x in sorted(due,key=lambda x:x['not_before']):                           # oldest first, but an item whose video is missing must not block the queue
        if (BASE/x['video']).exists() or x.get('container'): it=x; break         # (a resumed 'publishing' item with a container needs no upload)
        skipped.append(x['id']); print(f"  ! video tidak ada, item dilewati: {x['id']} ({x['video']})")
    if it is None: print(f'Semua {len(skipped)} item jatuh tempo kehilangan videonya: tidak ada yang diposting. Jalankan media_sync.sh pull atau render ulang.'); return 3
    vid=BASE/it['video']; caption=it['caption']
    why=None if IGNORE_BURST else burst_block(q,now)
    if why: print(f"DITAHAN (guard burst): {why}. Tidak ada yang diposting: {it['id']} tetap di antrean."); return 0
    print(f"posting: {it['id']} ({vid.name}, {(vid.stat().st_size/1e6 if vid.exists() else 0):.1f}MB)")
    if ALLOW_DUP: print(f"  ! cek duplikat caption DILEWATI untuk {it['id']} (--allow-duplicate, repost pengganti manual)")
    if not DRY and not ALLOW_DUP:
        m=already_on_instagram(it)
        if m:                                                                    # already live (earlier state push failed): record it, never post again
            try: when=dt.datetime.fromisoformat(m['timestamp'])
            except Exception: when=now
            record_posted(q,it,m['id'],m.get('permalink'),when); print(f"sudah tayang di Instagram, status dipulihkan tanpa posting ulang: {it['id']} {m.get('permalink')}"); return 0
    base=f'https://{HOST}/{VER}/{UID}'; cfg=json.loads((ROOT/'config.json').read_text())
    def poll(cid):                                                               # wait until Meta finished processing the video
        for _ in range(60):
            st=call('GET',f"https://{HOST}/{VER}/{cid}?fields=status_code&access_token={TOK}").get('status_code')
            if st=='FINISHED' or st in ('ERROR','EXPIRED'): return st
            time.sleep(5)
        return 'TIMEOUT'
    def make_container(sel):
        body={'media_type':'REELS','upload_type':'resumable','caption':caption,'share_to_feed':'true','thumb_offset':str(int(cfg.get('cover_offset_ms',2000))),'access_token':TOK}   # RULE: cover = frame at second 2 (thumb_offset, ms)
        if sel: body.pop('upload_type'); body['video_url']=sel['url']; body['audio_configuration']=ig_audio.config_param(sel)    # Instagram song: only documented together with video_url
        r=call('POST',base+'/media',body)
        it['container']=r['id']; it['status']='publishing'
        if not DRY: wj('queue.json',q)                                           # dry-run must never touch state
        if not sel: call('POST',r['uri'],headers={'Authorization':f'OAuth {TOK}','offset':'0','file_size':str(vid.stat().st_size)},raw=None if DRY else vid.read_bytes())   # video carries our own synthesized music
        return r['id']
    if it.get('container'):                                                      # resume a half-finished post (container already exists): never create another
        res=poll(it['container'])
        if res in ('ERROR','EXPIRED'): it['status']='failed'; wj('queue.json',q); raise SystemExit(f'processing {res}')
    else:
        sel=choose_ig_song(it,cfg,vid) if cfg.get('audio',{}).get('enabled') else None     # PRIMARY: a song picked from Instagram's own catalog
        for mode in (['ig'] if sel else [])+['own']:                             # FALLBACK: the video's own synthesized track (resumable upload). Both happen strictly BEFORE media_publish, so a failed attempt can never double-post.
            try: cid=make_container(sel if mode=='ig' else None)
            except SystemExit as e:
                if mode=='ig': print(f"  musik Instagram GAGAL saat membuat container ({str(e)[:140]}): pakai lagu buatan sendiri"); it['container']=None; continue
                raise
            res=poll(cid)
            if mode=='ig':
                if res=='FINISHED': it['music']={k:sel[k] for k in ('audio_id','title','artist')}; print(f"  musik: {sel['title']} - {sel['artist']} (lagu Instagram, via video_url)"); break
                print(f'  musik Instagram GAGAL (container {res}): pakai lagu buatan sendiri'); it['container']=None; continue
            if res in ('ERROR','EXPIRED'): it['status']='failed'; wj('queue.json',q); raise SystemExit(f'processing {res}')
            print('  musik: lagu buatan sendiri (trek sintesis di dalam video)')
    pub=call('POST',base+'/media_publish',{'creation_id':it['container'],'access_token':TOK})
    info=call('GET',f"https://{HOST}/{VER}/{pub['id']}?fields=permalink,timestamp&access_token={TOK}")
    if DRY: print('  [dry-run] selesai, antrean TIDAK diubah.'); return 0
    record_posted(q,it,pub['id'],info.get('permalink'),now)
    print('terkirim:',it['permalink']); return 0
sys.exit(main())

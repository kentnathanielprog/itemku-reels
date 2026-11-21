#!/usr/bin/env python3
"""Offline tests for auto/publish.py using a fake Graph API (urllib.request.urlopen is patched; no network, no real token).
Every case runs in a throw-away copy of auto/ so the real state is never touched.   usage: python3 tests/publish_test.py"""
import sys,os,io,json,shutil,pathlib,tempfile,runpy,urllib.request,urllib.error,datetime as dt,contextlib
REPO=pathlib.Path(__file__).resolve().parent.parent
NOW=dt.datetime.now(dt.timezone.utc)
def iso(d): return d.isoformat()
def make_tree(queue,posts=(),videos=True):
    tmp=pathlib.Path(tempfile.mkdtemp(prefix='pubtest_')); a=tmp/'auto'; (a/'state').mkdir(parents=True)
    for f in ('publish.py','config.json','ig_audio.py'): shutil.copy(REPO/'auto'/f,a/f)
    (a/'state'/'queue.json').write_text(json.dumps(queue)); (a/'state'/'posts.json').write_text(json.dumps(list(posts)))
    (a/'state'/'history.json').write_text('[]')
    if videos:
        for it in queue:
            v=tmp/it['video']; v.parent.mkdir(parents=True,exist_ok=True); v.write_bytes(b'x'*2048)
    return tmp
def item(i,not_before=None,status='ready',video=None,caption=None,**kw):
    return {'id':i,'status':status,'not_before':iso(not_before or NOW-dt.timedelta(hours=1)),'video':video or f'out/short-{i}/short.mp4','caption':caption or f'Caption {i}\n\n#itemku','cat':'mlbb','topic':i,**kw}
class Fake:
    """fake Graph API. songs: what GET /ig_audio returns; head: 'ok'|'missing'|'size' for the video_url HEAD; statuses: container id -> status_code; ig_create_error: POST /media with video_url fails"""
    def __init__(s,recent=None,media_list_error=False,songs=None,head='ok',statuses=None,ig_create_error=False,audio_search_error=False):
        s.calls=[]; s.bodies=[]; s.recent=recent or []; s.err=media_list_error; s.songs=songs or []; s.head=head; s.statuses=statuses or {}; s.ig_err=ig_create_error; s.aud_err=audio_search_error; s.vid_len=2048
    def __call__(s,req,timeout=0):
        url=req.full_url if hasattr(req,'full_url') else req; m=getattr(req,'method',None) or 'GET'; s.calls.append((m,url.split('?')[0]))
        import urllib.parse as up
        body={k:v[0] for k,v in up.parse_qs(req.data.decode()).items()} if getattr(req,'data',None) and b'=' in req.data[:200] and m=='POST' and 'rupload' not in url else {}
        s.bodies.append((m,url.split('?')[0],body))
        def out(d): return io.BytesIO(json.dumps(d).encode())
        if m=='HEAD':
            if s.head=='missing': raise urllib.error.HTTPError(url,404,'nf',{},io.BytesIO(b''))
            return types_ns(status=200,headers={'Content-Length':str(s.vid_len if s.head=='ok' else 999)})
        if '/ig_audio' in url:
            if s.aud_err: raise urllib.error.HTTPError(url,400,'bad',{},io.BytesIO(b'{"error":"x"}'))
            return out({'audio':s.songs})
        if '/media?' in url and m=='GET':
            if s.err: raise urllib.error.HTTPError(url,400,'bad',{},io.BytesIO(b'{"error":"x"}'))
            return out({'data':s.recent})
        if url.split('?')[0].endswith('/media') and m=='POST':
            if 'video_url' in body:
                if s.ig_err: raise urllib.error.HTTPError(url,400,'bad',{},io.BytesIO(b'{"error":"audio"}'))
                return out({'id':'C_IG','uri':'https://rupload.test/unused'})
            return out({'id':'C_OWN','uri':'https://rupload.test/C_OWN'})
        if 'rupload.test' in url: return out({'success':True})
        if 'fields=status_code' in url:
            cid=url.split('/')[-1].split('?')[0]; return out({'status_code':s.statuses.get(cid,'FINISHED')})
        if url.split('?')[0].endswith('/media_publish'): return out({'id':'M1'})
        if 'fields=permalink,timestamp' in url: return out({'permalink':'https://instagram.com/reel/TEST/','timestamp':iso(NOW)})
        raise AssertionError('unexpected URL '+url)
import types
types_ns=lambda **k: types.SimpleNamespace(**k)
def run(tmp,argv=(),fake=None,env=None):
    fake=fake or Fake(); real=urllib.request.urlopen; urllib.request.urlopen=fake
    env_old=dict(os.environ); os.environ.update(IG_USER_ID='123',IG_ACCESS_TOKEN='fake-token'); os.environ.pop('STOP',None); os.environ.pop('ALLOW_FORCE',None); os.environ.update(env or {})
    sys.argv=['publish.py',*argv]; buf=io.StringIO(); code=0
    import time as _t; sl=_t.sleep; _t.sleep=lambda *_:None
    sys.path.insert(0,str(tmp/'auto')); sys.modules.pop('ig_audio',None)     # like `python3 auto/publish.py`: the script's folder is on sys.path
    try:
        with contextlib.redirect_stdout(buf):
            try: runpy.run_path(str(tmp/'auto'/'publish.py'),run_name='__main__')
            except SystemExit as e:
                code=0 if e.code in (None,0) else (e.code if isinstance(e.code,int) else 1)
                if isinstance(e.code,str): buf.write(e.code)
    finally: urllib.request.urlopen=real; _t.sleep=sl; sys.path.remove(str(tmp/'auto')); sys.modules.pop('ig_audio',None); os.environ.clear(); os.environ.update(env_old)
    return code,buf.getvalue(),fake
def state(tmp,f): return json.loads((tmp/'auto'/'state'/f).read_text())
def posted_calls(fake): return [c for c in fake.calls if c[1].endswith('/media_publish')]
RES=[]
def case(name):
    def deco(fn):
        try: fn(); RES.append((name,True,''))
        except AssertionError as e: RES.append((name,False,str(e)[:300]))
        except Exception as e: RES.append((name,False,f'{type(e).__name__}: {e}'[:300]))
        return fn
    return deco

# ---- (b) no double posting -------------------------------------------------------------------------------------------------------------
@case('baseline: due item is posted and recorded')
def _():
    t=make_tree([item('a')]); code,out,f=run(t); assert code==0,out; assert len(posted_calls(f))==1,f.calls
    assert state(t,'queue.json')[0]['status']=='posted' and state(t,'posts.json')[0]['media_id']=='M1'
@case('already on Instagram (state push of an earlier run failed): recorded as posted, NOT posted again')
def _():
    it=item('a',caption='Caption a\n\n#itemku'); t=make_tree([it])
    code,out,f=run(t,fake=Fake(recent=[{'id':'777','caption':'Caption a  \n\n#itemku','permalink':'https://instagram.com/reel/OLD/','timestamp':iso(NOW-dt.timedelta(hours=2))}]))
    assert code==0,out; assert not [c for c in f.calls if c[0]=='POST'],f.calls
    q=state(t,'queue.json')[0]; assert q['status']=='posted' and q['media_id']=='777',q; assert state(t,'posts.json')[0]['media_id']=='777'
@case('Instagram account unreadable -> fail closed: non-zero exit, nothing posted, state untouched')
def _():
    t=make_tree([item('a')]); code,out,f=run(t,fake=Fake(media_list_error=True))
    assert code!=0,out; assert not [c for c in f.calls if c[0]=='POST'],f.calls; assert state(t,'queue.json')[0]['status']=='ready'
@case('dry-run never writes state and never POSTs (only read-only GETs of the song catalog)')
def _():
    t=make_tree([item('a')]); before=(t/'auto'/'state'/'queue.json').read_text(); code,out,f=run(t,['--dry-run']); assert code==0,out
    assert not [c for c in f.calls if c[0]!='GET'],f.calls; assert not [c for c in f.calls if c[1].endswith('/media_publish')]; assert (t/'auto'/'state'/'queue.json').read_text()==before

# ---- (c) burst guard + not_before ---------------------------------------------------------------------------------------------------------
WIB=dt.timezone(dt.timedelta(hours=7))
def day_start(): return NOW.astimezone(WIB).replace(hour=0,minute=0,second=0,microsecond=0)
def today_posts(n):
    ds=day_start(); return [{'id':f'p{i}','media_id':f'm{i}','posted_at':iso(ds+dt.timedelta(seconds=5*(i+1)))} for i in range(n)]
@case('burst: 3 posts already today (WIB) -> 4th is held, even with --force')
def _():
    if (NOW-day_start()).total_seconds()<30: return
    t=make_tree([item('a')],posts=today_posts(3)); code,out,f=run(t,['--force']); assert code==0 and 'DITAHAN' in out and 'per hari' in out,out
    assert not f.calls,f.calls; assert state(t,'queue.json')[0]['status']=='ready'
@case('burst: --ignore-burst (manual) bypasses the daily cap')
def _():
    if (NOW-day_start()).total_seconds()<30: return
    t=make_tree([item('a')],posts=today_posts(3)); code,out,f=run(t,['--ignore-burst']); assert code==0 and len(posted_calls(f))==1,out
@case('burst: 2 posts today is still allowed (cap is 3)')
def _():
    if (NOW-day_start()).total_seconds()<3700: return      # right after WIB midnight the 60-min gap rule would apply instead
    t=make_tree([item('a')],posts=today_posts(2)); code,out,f=run(t); assert code==0 and len(posted_calls(f))==1,out
@case('burst: last post 30 min ago -> held (min gap 60 min)')
def _():
    t=make_tree([item('a')],posts=[{'id':'p','media_id':'m','posted_at':iso(NOW-dt.timedelta(minutes=30))}]); code,out,f=run(t); assert 'DITAHAN' in out and 'jarak minimal' in out,out
    assert not f.calls,f.calls
@case('burst: last post 61 min ago -> allowed')
def _():
    t=make_tree([item('a')],posts=[{'id':'p','media_id':'m','posted_at':iso(NOW-dt.timedelta(minutes=61))}]); code,out,f=run(t); assert len(posted_calls(f))==1,out
@case('burst: dry-run reports the hold and makes no calls')
def _():
    t=make_tree([item('a')],posts=[{'id':'p','media_id':'m','posted_at':iso(NOW-dt.timedelta(minutes=5))}]); code,out,f=run(t,['--dry-run']); assert 'DITAHAN' in out and not f.calls,out
@case('not_before in the future: refused without --force')
def _():
    t=make_tree([item('a',not_before=NOW+dt.timedelta(hours=5))]); code,out,f=run(t); assert code==0 and 'belum tiba' in out and not f.calls,out
    assert state(t,'queue.json')[0]['status']=='ready'
@case('not_before in the future: posted with --force (manual)')
def _():
    t=make_tree([item('a',not_before=NOW+dt.timedelta(hours=5))]); code,out,f=run(t,['--force']); assert len(posted_calls(f))==1,out
@case('the 4-posts-in-43-minutes incident cannot repeat: with --force the 2nd post is held by the gap rule')
def _():
    t=make_tree([item('a',not_before=NOW+dt.timedelta(days=1)),item('b',not_before=NOW+dt.timedelta(days=1,minutes=1))])
    c1,o1,f1=run(t,['--force']); assert len(posted_calls(f1))==1,o1
    c2,o2,f2=run(t,['--force']); assert 'DITAHAN' in o2 and not f2.calls,o2

# ---- (d) missing video must not block the queue ---------------------------------------------------------------------------------------------
@case('missing video: oldest item skipped, next item is posted, exit 0, skipped item stays ready')
def _():
    t=make_tree([item('old',not_before=NOW-dt.timedelta(hours=9)),item('new',not_before=NOW-dt.timedelta(hours=1))])
    (t/'out'/'short-old'/'short.mp4').unlink()
    code,out,f=run(t); assert code==0 and 'dilewati: old' in out,out; assert len(posted_calls(f))==1
    st={x['id']:x['status'] for x in state(t,'queue.json')}; assert st=={'old':'ready','new':'posted'},st
@case('missing video: every due item without a file -> non-zero exit, nothing posted, state unchanged')
def _():
    t=make_tree([item('a'),item('b')],videos=False); before=(t/'auto'/'state'/'queue.json').read_text(); code,out,f=run(t)
    assert code==3,(code,out); assert not [c for c in f.calls if c[0]=='POST'],f.calls; assert (t/'auto'/'state'/'queue.json').read_text()==before
@case('missing video: dry-run also skips instead of crashing (FileNotFoundError)')
def _():
    t=make_tree([item('old',not_before=NOW-dt.timedelta(hours=9)),item('new')]); (t/'out'/'short-old'/'short.mp4').unlink()
    code,out,f=run(t,['--dry-run']); assert code==0 and 'dilewati: old' in out and 'posting: new' in out,out

# ---- --allow-duplicate: deliberate one-item replacement repost ----------------------------------------------------------------------------------
LIVE=lambda: Fake(recent=[{'id':'777','caption':'Caption a\n\n#itemku','permalink':'https://instagram.com/reel/OLD/','timestamp':iso(NOW-dt.timedelta(hours=1))}])
OLD=[{'id':'a','media_id':'777','posted_at':iso(NOW-dt.timedelta(hours=1))}]
@case('allow-duplicate: caption already live + ALLOW_FORCE=1 + --id -> posted ONCE as a new Reel, old record kept')
def _():
    t=make_tree([item('a',caption='Caption a\n\n#itemku')],posts=OLD); code,out,f=run(t,['--allow-duplicate','--ignore-burst','--id','a'],fake=LIVE(),env={'ALLOW_FORCE':'1'})
    assert code==0 and len(posted_calls(f))==1 and 'DILEWATI' in out,(code,out); assert not [c for c in f.calls if c[1].endswith('/media') and c[0]=='GET'],'media list must not be read'
    q=state(t,'queue.json')[0]; assert q['status']=='posted' and q['media_id']=='M1',q; ids=[x['media_id'] for x in state(t,'posts.json')]; assert ids==['777','M1'],ids
@case('allow-duplicate without ALLOW_FORCE=1 -> refused (exit 2), nothing called')
def _():
    t=make_tree([item('a',caption='Caption a\n\n#itemku')],posts=OLD); code,out,f=run(t,['--allow-duplicate','--ignore-burst','--id','a'],fake=LIVE()); assert code==2 and 'ALLOW_FORCE=1' in out and not f.calls,(code,out,f.calls)
@case('allow-duplicate without --id -> refused (cannot be a blanket bypass)')
def _():
    t=make_tree([item('a',caption='Caption a\n\n#itemku')],posts=OLD); code,out,f=run(t,['--allow-duplicate','--ignore-burst'],fake=LIVE(),env={'ALLOW_FORCE':'1'}); assert code==2 and not f.calls,(code,out)
@case('ALLOW_FORCE=1 alone does NOT disable the duplicate check (the explicit flag is required)')
def _():
    t=make_tree([item('a',caption='Caption a\n\n#itemku')],posts=OLD); code,out,f=run(t,['--ignore-burst','--id','a'],fake=LIVE(),env={'ALLOW_FORCE':'1'})
    assert code==0 and not [c for c in f.calls if c[0]=='POST'] and state(t,'queue.json')[0]['media_id']=='777',out
@case('allow-duplicate does not lift the burst guard (needs --ignore-burst separately)')
def _():
    t=make_tree([item('a',caption='Caption a\n\n#itemku')],posts=[{'id':'p','media_id':'m','posted_at':iso(NOW-dt.timedelta(minutes=5))}]); code,out,f=run(t,['--allow-duplicate','--id','a'],fake=LIVE(),env={'ALLOW_FORCE':'1'})
    assert 'DITAHAN' in out and not [c for c in f.calls if c[0]=='POST'],out

# ---- Instagram song as the PRIMARY music, own synthesized track as FALLBACK -------------------------------------------------------------------------
SONG={'audio_id':'s1','title':'Test Song','display_artist':'Test Artist','duration_in_ms':60000,'is_ads_eligible':True}
def creates(f): return [b for b in f.bodies if b[0]=='POST' and b[1].endswith('/media')]
def uploads(f): return [c for c in f.calls if 'rupload.test' in c[1]]
@case('Instagram song: video_url + audio_configuration (song volume 70, video volume 1), no resumable upload, posted once, song recorded')
def _():
    t=make_tree([item('a',music='assets/audio/pulse-arena.m4a')]); code,out,f=run(t,fake=Fake(songs=[SONG])); assert code==0 and len(posted_calls(f))==1,out
    c=creates(f); assert len(c)==1,c; b=c[0][2]; assert b['video_url'].startswith('https://raw.githubusercontent.com/') and '?v=' in b['video_url'] and 'upload_type' not in b,b
    ac=json.loads(b['audio_configuration']); assert ac=={'audio_id':'s1','audio_volume':70,'video_volume':1},ac; assert not uploads(f)
    assert state(t,'queue.json')[0]['music']=={'audio_id':'s1','title':'Test Song','artist':'Test Artist'}
@case('fallback: Instagram returns no song -> own track via resumable upload, no audio_configuration, own music kept in the record')
def _():
    t=make_tree([item('a',music='assets/audio/pulse-arena.m4a')]); code,out,f=run(t,fake=Fake(songs=[])); assert code==0 and len(posted_calls(f))==1,out
    b=creates(f)[0][2]; assert b['upload_type']=='resumable' and 'audio_configuration' not in b and 'video_url' not in b,b; assert len(uploads(f))==1
    assert state(t,'queue.json')[0]['music']=='assets/audio/pulse-arena.m4a'; assert 'lagu buatan sendiri' in out
@case('fallback: song search API error -> own track, no crash')
def _():
    t=make_tree([item('a')]); code,out,f=run(t,fake=Fake(songs=[SONG],audio_search_error=True)); assert code==0 and len(posted_calls(f))==1 and len(uploads(f))==1,out
@case('fallback: video_url not served by GitHub (404) -> own track')
def _():
    t=make_tree([item('a')]); code,out,f=run(t,fake=Fake(songs=[SONG],head='missing')); assert code==0 and len(posted_calls(f))==1 and len(uploads(f))==1 and not [b for b in creates(f) if 'video_url' in b[2]],out
@case('fallback: video_url serves a stale/different file (size mismatch) -> own track, never an old video')
def _():
    t=make_tree([item('a')]); code,out,f=run(t,fake=Fake(songs=[SONG],head='size')); assert code==0 and len(posted_calls(f))==1 and len(uploads(f))==1 and not [b for b in creates(f) if 'video_url' in b[2]],out
@case('fallback: Instagram rejects the audio container (HTTP 400) -> second container with own track, exactly ONE media_publish')
def _():
    t=make_tree([item('a')]); code,out,f=run(t,fake=Fake(songs=[SONG],ig_create_error=True)); assert code==0 and len(posted_calls(f))==1,out
    assert len(creates(f))==2 and len(uploads(f))==1; assert state(t,'queue.json')[0]['status']=='posted'
@case('fallback: audio container ends in ERROR -> second container with own track, exactly ONE media_publish, song not recorded')
def _():
    t=make_tree([item('a',music='own.m4a')]); code,out,f=run(t,fake=Fake(songs=[SONG],statuses={'C_IG':'ERROR'})); assert code==0 and len(posted_calls(f))==1,out
    assert len(creates(f))==2 and len(uploads(f))==1; q=state(t,'queue.json')[0]; assert q['music']=='own.m4a' and q['status']=='posted',q
@case('own track also failing (ERROR) -> run fails, nothing published')
def _():
    t=make_tree([item('a')]); code,out,f=run(t,fake=Fake(songs=[],statuses={'C_OWN':'ERROR'})); assert code!=0 and not posted_calls(f),out
@case('dry-run with Instagram audio: no state written, no media_publish')
def _():
    t=make_tree([item('a')]); before=(t/'auto'/'state'/'queue.json').read_text(); code,out,f=run(t,['--dry-run'],fake=Fake(songs=[SONG])); assert code==0,out
    assert (t/'auto'/'state'/'queue.json').read_text()==before

if __name__=='__main__':
    bad=0
    for n,ok,msg in RES:
        print(('  ✓ ' if ok else '  ✗ ')+n+('' if ok else f'\n      {msg}')); bad+=0 if ok else 1
    print(f'passed={len(RES)-bad} failed={bad}'); sys.exit(1 if bad else 0)

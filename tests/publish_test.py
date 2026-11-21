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
    def __init__(s,recent=None,media_list_error=False): s.calls=[]; s.recent=recent or []; s.err=media_list_error
    def __call__(s,req,timeout=0):
        url=req.full_url if hasattr(req,'full_url') else req; m=getattr(req,'method',None) or 'GET'; s.calls.append((m,url.split('?')[0]))
        def out(d): return io.BytesIO(json.dumps(d).encode())
        if '/media?' in url and m=='GET':
            if s.err: raise urllib.error.HTTPError(url,400,'bad',{},io.BytesIO(b'{"error":"x"}'))
            return out({'data':s.recent})
        if url.endswith('/media') or url.split('?')[0].endswith('/media'): return out({'id':'C1','uri':'https://rupload.test/C1'})
        if 'rupload.test' in url: return out({'success':True})
        if 'fields=status_code' in url: return out({'status_code':'FINISHED'})
        if url.split('?')[0].endswith('/media_publish'): return out({'id':'M1'})
        if 'fields=permalink,timestamp' in url: return out({'permalink':'https://instagram.com/reel/TEST/','timestamp':iso(NOW)})
        raise AssertionError('unexpected URL '+url)
def run(tmp,argv=(),fake=None):
    fake=fake or Fake(); real=urllib.request.urlopen; urllib.request.urlopen=fake
    env_old=dict(os.environ); os.environ.update(IG_USER_ID='123',IG_ACCESS_TOKEN='fake-token'); os.environ.pop('STOP',None)
    sys.argv=['publish.py',*argv]; buf=io.StringIO(); code=0
    import time as _t; sl=_t.sleep; _t.sleep=lambda *_:None
    try:
        with contextlib.redirect_stdout(buf):
            try: runpy.run_path(str(tmp/'auto'/'publish.py'),run_name='__main__')
            except SystemExit as e:
                code=0 if e.code in (None,0) else (e.code if isinstance(e.code,int) else 1)
                if isinstance(e.code,str): buf.write(e.code)
    finally: urllib.request.urlopen=real; _t.sleep=sl; os.environ.clear(); os.environ.update(env_old)
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
@case('dry-run never calls Instagram and never writes state')
def _():
    t=make_tree([item('a')]); before=(t/'auto'/'state'/'queue.json').read_text(); code,out,f=run(t,['--dry-run']); assert code==0,out
    assert not f.calls,f.calls; assert (t/'auto'/'state'/'queue.json').read_text()==before

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

if __name__=='__main__':
    bad=0
    for n,ok,msg in RES:
        print(('  ✓ ' if ok else '  ✗ ')+n+('' if ok else f'\n      {msg}')); bad+=0 if ok else 1
    print(f'passed={len(RES)-bad} failed={bad}'); sys.exit(1 if bad else 0)

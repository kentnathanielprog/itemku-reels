#!/usr/bin/env python3
"""Offline tests for the image rules: 1 real image is enough, more images preferred, text-only cards still rejected, varied crops per segment.
No network, no LLM. usage: python3 tests/image_rules_test.py"""
import sys,os,io,json,pathlib,tempfile,subprocess,hashlib,types
REPO=pathlib.Path(__file__).resolve().parent.parent; os.chdir(REPO)
sys.path[:0]=[str(REPO/'auto'),str(REPO/'short')]
import imagesel,imgextra,shots
from PIL import Image,ImageDraw
import numpy as np
RES=[]
def case(name):
    def deco(fn):
        try: fn(); RES.append((name,True,''))
        except AssertionError as e: RES.append((name,False,str(e)[:300]))
        except Exception as e: RES.append((name,False,f'{type(e).__name__}: {e}'[:300]))
        return fn
    return deco
I=lambda f,w,src=None:{'file':f,'w':w,'src':src}

# ---- selection policy --------------------------------------------------------------------------------------------------------------------
@case('ONE real image (1200 px) is accepted, not rejected')
def _(): assert imagesel.select([I('a.jpg',1200)],min_images=1)==['a.jpg']
@case('ONE real image of 850 px is accepted as fallback (used to be rejected: threshold was 1000 px)')
def _(): assert imagesel.select([I('a.jpg',850)],min_images=1)==['a.jpg']
@case('images under 800 px are not usable -> [] (no real picture at 1080 px)')
def _(): assert imagesel.select([I('a.jpg',700),I('b.jpg',640)])==[]
@case('prefers more than one: sharp images first (article order), then 800-999 px, then related-page, capped at 3')
def _():
    r=imagesel.select([I('f1.jpg',900),I('p1.jpg',1400),I('rel.jpg',1000,'related'),I('p2.jpg',1100),I('f2.jpg',820)]); assert r==['p1.jpg','p2.jpg','f1.jpg'],r
@case('related-page image fills the gap when the article has only one picture')
def _(): assert imagesel.select([I('p1.jpg',1300),I('rel.jpg',1000,'related')])==['p1.jpg','rel.jpg']
@case('duplicates are not repeated')
def _(): assert imagesel.select([I('a.jpg',1300),I('a.jpg',1300)])==['a.jpg']

# ---- related-page links ------------------------------------------------------------------------------------------------------------------
PAGE='https://www.pcgamesn.com/world-of-warcraft/forever-patch-notes-dungeon-farming'
HTML='''<p><a href="/world-of-warcraft/forever-dungeon-farming-cap-explained">cap</a></p>
<a href="https://www.pcgamesn.com/elden-ring/new-boss-fight-guide-revealed-today">other game</a>
<a href="https://other.com/world-of-warcraft/forever-patch-notes-dungeon-farming-more">external</a>
<a href="/tag/world-of-warcraft-forever-patch-notes-dungeon-farming/">tag</a>
<a href="/world-of-warcraft/forever-patch-notes-dungeon-farming">self</a>
<a href="/world-of-warcraft/forever-launch-date-and-dungeon-farming-rules?utm=x">query</a>
<a href="/world-of-warcraft/forever-patch-dungeon-farming-nerf-reaction">reaction</a>'''
@case('related_links: only same-site, topical, article-like links (not other games, tags, self, external, tracking links)')
def _():
    r=imgextra.related_links(HTML,PAGE,'New World of Warcraft Forever patch notes put a stricter cap on dungeon farming')
    assert r==['https://www.pcgamesn.com/world-of-warcraft/forever-dungeon-farming-cap-explained','https://www.pcgamesn.com/world-of-warcraft/forever-patch-dungeon-farming-nerf-reaction'] or set(r)=={'https://www.pcgamesn.com/world-of-warcraft/forever-dungeon-farming-cap-explained','https://www.pcgamesn.com/world-of-warcraft/forever-patch-dungeon-farming-nerf-reaction'},r
@case('related_links: sharing only generic words (steam, players, game, update...) is NOT enough (other game = wrong picture)')
def _():
    h='<a href="/gaming/publisher-blames-ai-slop-on-steam-as-their-game-only-gets-15-players-at-launch-3424285/">x</a><a href="/gaming/developer-claims-55000-steam-players-refunded-game-after-beating-it-too-fast-3383390/">y</a>'
    assert imgextra.related_links(h,'https://www.dexerto.com/gaming/devs-of-steam-heist-game-robbed-irl-as-hacker-refunds-players-in-game-purchases-3430127/','Devs of Steam heist game robbed IRL as hacker refunds players in-game purchases')==[]
@case('related_links: at most 3')
def _():
    h=''.join(f'<a href="/world-of-warcraft/forever-patch-dungeon-farming-extra-take-{i}">x</a>' for i in range(8)); assert len(imgextra.related_links(h,PAGE,'Forever patch dungeon farming'))==3

# ---- crop / motion variety for ONE image -----------------------------------------------------------------------------------------------------
@case('one image, 8 shots: every shot differs from the previous (crop variant or zoom direction), >= 6 distinct crops used')
def _():
    segs=[(0,3,[0,0]),(3,6,[0,0]),(6,9.9,[0,0,0]),(9.9,12.2,[0])]; p=shots.shot_plan(1,segs); assert len(p)==8,len(p)
    for x,y in zip(p,p[1:]): assert (x[3],x[4])!=(y[3],y[4]),(x,y)
    assert len({s[3] for s in p})>=6,len({s[3] for s in p}); assert {s[2] for s in p}=={0}
@case('real render from ONE picture: different segments show visibly different frames (crop/zoom), output is 1080x608 and the right length')
def _():
    t=pathlib.Path(tempfile.mkdtemp(prefix='imgtest_')); rng=np.random.default_rng(3)
    a=(rng.random((900,1600,3))*255).astype('uint8'); a[:450,:800]=[200,30,30]; a[450:,800:]=[30,30,200]; a[:300,800:1200]=[240,240,40]   # distinctive regions so crops differ
    Image.fromarray(a).save(t/'one.jpg',quality=95)
    out=t/'o.mp4'; n=shots.build_caps([str(t/'one.jpg')],8.0,[(0,4,[0,0]),(4,8,[0,0])],str(out)); assert n==4
    pr=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=width,height,duration','-of','json',str(out)],capture_output=True,text=True).stdout)['streams'][0]
    assert (pr['width'],pr['height'])==(1080,608) and abs(float(pr['duration'])-8.0)<0.3,pr
    sig=[]
    for ts in (1.0,3.0,5.0,7.0):
        raw=subprocess.run(['ffmpeg','-v','error','-ss',str(ts),'-i',str(out),'-frames:v','1','-vf','scale=32:18,format=rgb24','-f','rawvideo','-'],capture_output=True).stdout
        sig.append(np.frombuffer(raw,np.uint8).astype(float))
    d=[float(np.abs(x-y).mean()) for x,y in zip(sig,sig[1:])]; assert min(d)>3,d      # consecutive shots clearly differ
    assert (REPO/'auto'/'state'/'queue.json').exists()

# ---- text-only cards are still rejected --------------------------------------------------------------------------------------------------------
def photo(path):
    rng=np.random.default_rng(1); im=(rng.random((900,1600,3))*255).astype('uint8'); Image.fromarray(im).save(path,quality=95)
def textcard(path):
    im=Image.new('RGB',(1600,900),(24,26,40)); d=ImageDraw.Draw(im)
    for k in range(6): d.text((80,80+k*40),'PLAYERS ONLINE 1,234,567  PEAK 2,345,678  STATS',fill=(230,230,230))
    im.save(path,quality=95)
@case('layer 1: a real picture is neither dropped nor suspected; a flat text card is only a HINT (vision decides)')
def _():
    import visual as V; t=pathlib.Path(tempfile.mkdtemp(prefix='imgtest_')); photo(t/'p.jpg'); textcard(t/'c.jpg')
    h,s=V.check_images([str(t/'p.jpg')]); assert not h and not s,(h,s)
    h2,s2=V.check_images([str(t/'c.jpg')]); assert 0 in s2 or 0 in h2,(h2,s2)       # flagged (blurry/blank or text-card suspect), never silently accepted
def load_early(verdict=None,raise_err=False):
    src=open('auto/produce.py').read(); seg=src[src.index('def early_screen'):src.index('# ---------------- 2.')]
    class LLMError(Exception): pass
    calls=[]; msgs=[]
    class L_:
        @staticmethod
        def call_json(*a,**k):
            calls.append(1)
            if raise_err: raise LLMError('x')
            return {'reports':[{'id':'s','images':[{'index':0,'verdict':verdict[0],'problem':verdict[1],'note':''}]}]},{'in':0,'out':0,'cache_read':0,'cache_write':0,'usd':0.0}
    L_.LLMError=LLMError
    V_=types.SimpleNamespace(thumb_block=lambda p:{}); ns={'VISION':True,'os':os,'json':json,'V':V_,'llm':L_,'VISP':'','schemas':types.SimpleNamespace(VISUAL={}),'L':{'vision_model':'m','qc_model':'q'},'USAGE':[],'say':msgs.append}
    exec(seg,ns); return ns['early_screen'],calls,msgs
IT={'id':'s','images':['x.jpg'],'art':{'title':'t'}}
os.environ.pop('LLM_MOCK_DIR',None)
@case('single image judged text_card by the vision check -> story rejected (text-only card still refused)')
def _(): f,c,m=load_early(('drop','text_card')); assert f(dict(IT))is False and c
@case('single image judged ad_or_unrelated -> rejected')
def _(): f,c,m=load_early(('drop','ad_or_unrelated')); assert f(dict(IT)) is False
@case('single REAL image (verdict ok) -> accepted, video is made with 1 image')
def _(): f,c,m=load_early(('ok','none')); assert f(dict(IT)) is True
@case('2+ images skip the early single-image check (extra pictures are screened later with the batched vision call)')
def _(): f,c,m=load_early(('drop','text_card')); assert f({'id':'s','images':['a','b'],'art':{}}) is True and not c
@case('vision unavailable -> single image is not rejected for that reason')
def _(): f,c,m=load_early(raise_err=True); assert f(dict(IT)) is True

if __name__=='__main__':
    bad=0
    for n,ok,msg in RES:
        print(('  ✓ ' if ok else '  ✗ ')+n+('' if ok else f'\n      {msg}')); bad+=0 if ok else 1
    print(f'passed={len(RES)-bad} failed={bad}'); sys.exit(1 if bad else 0)

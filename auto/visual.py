"""Visual checker. Layer 1 = free heuristics (no LLM): resolution, blur, flat-background 'text card' score, near-duplicates, blank frames.
Layer 2 = vision call (one batched request, small JPEG thumbnails) -> see visual_call()."""
import sys,json,io,base64,subprocess,pathlib
import numpy as np
from PIL import Image
BASE=pathlib.Path(__file__).resolve().parent.parent
def _gray(im,maxw=640):
    im=im.convert('RGB'); w,h=im.size; s=min(1,maxw/w); im=im.resize((max(8,int(w*s)),max(8,int(h*s)))); return im,np.asarray(im.convert('L'),dtype=float)
def metrics(path):
    im0=Image.open(path); W,H=im0.size; im,g=_gray(im0)
    lap=g[1:-1,1:-1]*4-g[:-2,1:-1]-g[2:,1:-1]-g[1:-1,:-2]-g[1:-1,2:]; blur=float(lap.var())
    q=(np.asarray(im).astype(int)>>4); key=q[...,0]*256+q[...,1]*16+q[...,2]; _,cnt=np.unique(key,return_counts=True); cnt=np.sort(cnt)[::-1]
    flat1=float(cnt[0]/key.size); flat3=float(cnt[:3].sum()/key.size)
    gx=np.abs(np.diff(g,axis=1))[:-1]; gy=np.abs(np.diff(g,axis=0))[:,:-1]; edge=float(((gx+gy)>40).mean())
    return {'w':W,'h':H,'blur':round(blur,1),'flat1':round(flat1,3),'flat3':round(flat3,3),'edge':round(edge,3),'mean':round(float(g.mean()),1),'std':round(float(g.std()),1)}
def ahash(path):
    g=np.asarray(Image.open(path).convert('L').resize((16,9)),dtype=float); return (g>g.mean()).flatten()
TEXT_CARD=0.38; BLURRY=120.0
def check_images(paths):
    """layer 1 (free). returns (hard, suspect): hard = certain problems -> drop automatically (blurry/blank/tiny/duplicate/unreadable);
    suspect = looks like a text card (flat3 high) -> only a HINT for the vision check, because flat illustrated art scores the same (measured)."""
    hard={}; sus={}; hs=[]
    for i,p in enumerate(paths):
        pp=BASE/p if not str(p).startswith('/') else p
        try: m=metrics(pp)
        except Exception: hard[i]=['unreadable']; hs.append(None); continue
        f=[]
        if m['blur']<BLURRY: f.append('blurry')
        if m['std']<12 or m['mean']<18: f.append('blank_or_dark')
        if m['w']<700: f.append('tiny')
        h=ahash(pp); 
        for j,o in enumerate(hs):
            if o is not None and j not in hard and int((o!=h).sum())<=12: f.append(f'duplicate_of_{j}'); break
        hs.append(h)
        if f: hard[i]=f
        elif m['flat3']>=TEXT_CARD: sus[i]=['text_card_suspect']
    return hard,sus
def drop_images(story,idxs):
    """remove images and remap every caption's img list; returns new story (None if no image is left)"""
    keep=[i for i in range(len(story['images'])) if i not in set(idxs)]
    if not keep: return None
    mp={old:new for new,old in enumerate(keep)}; s=json.loads(json.dumps(story)); s['images']=[story['images'][i] for i in keep]
    def fix(c):
        c['img']=[mp[i] for i in c['img'] if i in mp] or [0]
    fix(s['hook']); [fix(m) for m in s['message']]; fix(s['gong']); fix(s['cta'])
    return s
def thumb_block(path,maxw=512,q=70):
    im=Image.open(BASE/path if not str(path).startswith('/') else path).convert('RGB'); w,h=im.size; s=min(1,maxw/w); im=im.resize((int(w*s),int(h*s)))
    b=io.BytesIO(); im.save(b,'JPEG',quality=q); return {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":base64.standard_b64encode(b.getvalue()).decode()}}
def vision_content(items):
    """one request for all stories: text + small thumbnails (about 200 tokens per image)"""
    blocks=[]
    for it in items:
        st=it['story']; shots=[('hook',st['hook']),('msg1',st['message'][0]),('msg2',st['message'][1]),('gong',st['gong'])]
        blocks.append({"type":"text","text":json.dumps({'id':it['id'],'heuristic_suspects':it.get('suspect',[]),'title':it['art'].get('title',''),'topic':st.get('topic',''),'shots':[{'caption':c['text'].replace('\n',' '),'img':c['img']} for _,c in shots]},ensure_ascii=False)})
        for i,p in enumerate(st['images']):
            blocks.append({"type":"text","text":f"{it['id']} image {i}:"}); blocks.append(thumb_block(p))
    return blocks
def frames_ok(video,n=6):
    """rendered video: sampled frames of the footage slot must not be blank/black"""
    W,H=108,114
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vf',f'fps=1/2.5,crop=1080:1135:0:0,scale={W}:{H},format=gray','-f','rawvideo','-'],capture_output=True).stdout
    a=np.frombuffer(raw,np.uint8).reshape(-1,H,W); bad=[i for i,f in enumerate(a) if f.std()<5 or f.mean()<8 or f.mean()>248]
    return bad,len(a)
if __name__=='__main__':
    for p in sys.argv[1:]: print(f"{pathlib.Path(p).name[:34]:34}",metrics(p))

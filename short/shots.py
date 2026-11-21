"""Build a multi-shot footage clip (1080x608) from several images: a cut at every caption change and extra cuts so no shot lasts > max_shot s.
Each shot alternates zoom in/out and uses a different crop (wide / close-up / left / right / top) so the same image never looks repeated."""
import subprocess
FPS=30
VARIANTS=[(1.0,.5,.5),(.62,.5,.42),(.62,.12,.45),(.62,.88,.45),(.75,.5,.15),(.55,.5,.7)]  # (zoom factor, x pos, y pos)
def plan(dur,cuts,max_shot=2.6):
    pts=[0]+[c for c in cuts if 0<c<dur]+[dur]; segs=[]
    for a,b in zip(pts,pts[1:]):
        n=max(1,int(-(-(b-a)//max_shot))); step=(b-a)/n
        segs+= [(a+i*step,a+(i+1)*step) for i in range(n)]
    return segs
def build(images,dur,cuts,out,max_shot=2.6):
    segs=plan(dur,cuts,max_shot); n=len(images); inputs=[]; flt=[]; labels=[]
    for i in range(n): inputs+=['-i',images[i]]
    frames=[round((b-a)*FPS) for a,b in segs]; diff=round(dur*FPS)-sum(frames); frames[-1]+=diff
    for k,fr in enumerate(frames):
        img=k%n; f,px,py=VARIANTS[(k//n+ (k%n>0 and k//n==0 and 0))%len(VARIANTS)] if k>=n else VARIANTS[0]
        zin=(k%2==0)
        z=f"min(1+0.0012*on,1.12)" if zin else f"max(1.12-0.0012*on,1.0)"
        flt.append(f"[{img}:v]crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',crop=w=iw*{f}:h=ih*{f}:x=(iw-ow)*{px}:y=(ih-oh)*{py},scale=1620:-2,"
                   f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s=1080x608:fps={FPS},setsar=1[s{k}]")
        labels.append(f'[s{k}]')
    flt.append(''.join(labels)+f"concat=n={len(labels)}:v=1:a=0")
    subprocess.run(['ffmpeg','-y','-loglevel','error']+inputs+['-filter_complex',';'.join(flt),'-c:v','libx264','-pix_fmt','yuv420p','-crf','17',out],check=True)
    return len(segs)


def shot_plan(n_images,segments,max_shot=2.6):
    """Pure planning step of build_caps (unit-tested). segments: [(start,end,[image indices] or None)].
    Returns [(start,end,image_index,(zoom,x,y),'in'|'out')]: the Nth use of the SAME image gets the Nth crop variant (wide / close-up / left / right / top ...),
    and the zoom direction alternates every shot, so one picture still looks different in every segment."""
    usage={}; auto=0; plan_=[]
    for a,b,idx in segments:
        if not idx:
            n=max(1,int(-(-(b-a)//max_shot))); idx=[(auto+j)%n_images for j in range(n)]; auto+=n
        step=(b-a)/len(idx); plan_+=[(a+j*step,a+(j+1)*step,i) for j,i in enumerate(idx)]
    out=[]
    for k,(a,b,i) in enumerate(plan_):
        u=usage.get(i,0); usage[i]=u+1; out.append((a,b,i,VARIANTS[u%len(VARIANTS)],'in' if k%2==0 else 'out'))
    return out
def build_caps(images,dur,segments,out,max_shot=2.6):
    """segments: list of (start,end,[image indices] or None). One shot per listed image (equal split); None -> auto cycle. See shot_plan for the crop/zoom rules."""
    inputs=[];flt=[];labels=[]
    for p in images: inputs+=['-i',p]
    plan_=shot_plan(len(images),segments,max_shot)
    frames=[round((b-a)*FPS) for a,b,*_ in plan_]; frames[-1]+=round(dur*FPS)-sum(frames)
    for k,((a,b,i,(f,px,py),zd),fr) in enumerate(zip(plan_,frames)):
        z="min(1+0.0012*on,1.12)" if zd=='in' else "max(1.12-0.0012*on,1.0)"
        flt.append(f"[{i}:v]crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',crop=w=iw*{f}:h=ih*{f}:x=(iw-ow)*{px}:y=(ih-oh)*{py},scale=1620:-2,"
                   f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s=1080x608:fps={FPS},setsar=1[s{k}]"); labels.append(f'[s{k}]')
    flt.append(''.join(labels)+f"concat=n={len(labels)}:v=1:a=0")
    subprocess.run(['ffmpeg','-y','-loglevel','error']+inputs+['-filter_complex',';'.join(flt),'-c:v','libx264','-pix_fmt','yuv420p','-crf','17',out],check=True)
    return len(plan_)

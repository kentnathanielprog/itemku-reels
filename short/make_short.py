#!/usr/bin/env python3
"""itemku 9:16 short (1080x1920): blurred bg + clip + official template (animates once) + animated caption text.
usage: python3 make_short.py config.json
config: {"video":"clip.mp4","out":"name","start":0,"duration":null,
 "captions":[{"text":"Line 1\\nLine 2","start":0,"end":null}],
 "audio":"keep"|"none"|"music/song.mp3","music_start":0,"mode":"blur"|"cover","center_y":940,"font_size":62,"source":"..."}
Speed: ONE browser for all overlays, screenshots only the moving region, results cached in out/_cache (unchanged captions are free)."""
import json,sys,os,subprocess,html,shutil,pathlib,re,hashlib,time
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; OUT=BASE/'out'; CACHE=OUT/'_cache'
FPS=30; FRAME_IN=1.6; OUTA=0.3
def sh(*a): subprocess.run(a,check=True)
def probe(v):
    return float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',v],capture_output=True,text=True,check=True).stdout.strip())
def p(x): x=str(x); return x if os.path.isabs(x) else str(BASE/x)
cfg=json.loads(pathlib.Path(sys.argv[1]).read_text()); T0=time.time()
name=cfg['out']; d=OUT/name; d.mkdir(parents=True,exist_ok=True); CACHE.mkdir(parents=True,exist_ok=True)
vid=p(cfg['video']); ss=float(cfg.get('start',0)); dur=float(cfg.get('duration') or (probe(vid)-ss))
FG=ROOT/'assets'/'frame_fg.png'; caps=cfg['captions']
TEXT_CLIP={'x':60,'y':1200,'width':960,'height':470}; FRAME_CLIP={'x':0,'y':1100,'width':1080,'height':820}

# ---------- overlay jobs (cached) ----------
jobs=[]; handles=[]
def job(htmlname,repl,isec,st,osec,clip):
    t=(ROOT/htmlname).read_text()
    for k,v in repl.items(): t=t.replace('{{%s}}'%k,v)
    key=hashlib.sha1((t+json.dumps([isec,st,osec,clip,FPS])+str(FG.stat().st_mtime)).encode()).hexdigest()[:16]
    cd=CACHE/key
    if not cd.exists():
        hp=CACHE/f'{key}.html'; hp.write_text(t)
        jobs.append({'html':str(hp),'dir':str(CACHE/(key+'.tmp')),'fps':FPS,'isec':isec,'st':st,'outAt':5,'osec':osec,'clip':clip,'key':key})
    handles.append(cd); return cd
frame=job('overlay_frame.html',{'FG':str(FG)},FRAME_IN,FRAME_IN+0.2,0,FRAME_CLIP)
plan=[]
def fmt(l):
    l=html.escape(l); l=re.sub(r'\(\((.+?)\)\)',lambda m:f'<span class="hl">{m.group(1)}</span>',l)
    return re.sub(r'\[\[(.+?)\]\]',lambda m:f'<span class="num" data-v="{m.group(1)}">{m.group(1)}</span>',l)
for k,c in enumerate(caps):
    a=float(c.get('start',0)); b=float(c['end']) if c.get('end') else dur
    last=(k==len(caps)-1) or not c.get('end'); first=(k==0)
    has_num='[[' in c['text']; has_hl='((' in c['text']
    IN=1.6 if first else (2.7 if (has_num or has_hl) else 0.9); o=0 if last else OUTA
    big=(lambda x: re.sub(r'(?i)\bitemku\b',lambda m:f'<span class="big">{m.group(0)}</span>',x)) if False else (lambda x:x)
    lines=''.join(f'<div class="line"><i style="--i:{i}">{big(fmt(l))}</i></div>' for i,l in enumerate(c['text'].split('\n')))
    srctxt=re.sub(r'\s*[,;]?\s*(data\s+)?\d{1,2}\s+(jan|feb|mar|apr|mei|jun|jul|agu|aug|sep|okt|oct|nov|des|dec)\w*\s+\d{4}','',cfg.get('source',''),flags=re.I).strip(' ,;')
    src=f'<div class="src">Sumber: {html.escape(srctxt)}</div>' if (last and srctxt) else ''
    cd=job('overlay_text.html',{'LINES':lines,'FS':str(cfg.get('font_size',62)),'DELAY':'.25' if first else '.05','FLASH':'','SRC':src},IN,IN+0.3,o,TEXT_CLIP)
    ae=a if first else max(a-0.2,0)
    plan.append(dict(cd=cd,a=a,b=b,ae=ae,IN=IN,o=o,flash=has_num))
t_job=time.time()
if jobs:
    (CACHE/'jobs.json').write_text(json.dumps(jobs)); sh('node',str(ROOT/'render_jobs.js'),str(CACHE/'jobs.json'))
    for j in jobs: os.rename(j['dir'],str(CACHE/j['key']))
t_job=time.time()-t_job

# ---------- video composition ----------
mode=cfg.get('mode','blur'); cy=int(cfg.get('center_y',940))
if mode=='cover': base=f"[0:v]fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v0]"
else: base=(f"[0:v]fps={FPS},split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,gblur=sigma=11,scale=1080:1920:flags=bicubic,eq=brightness=-0.15:saturation=1.2[bg];"
            f"[b]scale=1080:-2[fg];[bg][fg]overlay=0:{cy}-h/2[v0]")
cmd=['ffmpeg','-y','-loglevel','error','-ss',str(ss),'-t',str(dur),'-i',vid]; filt=[base,'[v0]split=2[vf][vr];[vr]crop=1080:820:0:1100[r0]']; n=1; cur='r0'   # overlays are chained on the bottom region only (2x cheaper)
def seq(path,start,length,label,loop=False,x=0,y=0):
    global n,cmd,cur
    if loop:   # decode the PNG ONCE and repeat it in memory (re-reading the file every frame was the slow part)
        cmd+=['-framerate',str(FPS),'-i',str(path)]; i=n; n+=1
        filt.append(f"[{i}:v]format=rgba,loop=loop=-1:size=1:start=0,setpts=N/({FPS}*TB),trim=end_frame={int(dur*FPS)+2}[{label}]")
    else:
        cmd+=['-framerate',str(FPS),'-i',str(path/'%04d.png')]; i=n; n+=1
        filt.append(f"[{i}:v]format=rgba,setpts=PTS-STARTPTS+{start}/TB[{label}]")
    filt.append(f"[{cur}][{label}]overlay={x}:{y}:eof_action=pass:enable='between(t,{start:.3f},{start+length:.3f})'[{label}o]"); cur=f'{label}o'
seq(frame/'in',0,FRAME_IN,'fin',x=0,y=0); seq(frame/'static.png',FRAME_IN-0.02,dur,'fst',loop=True,x=0,y=0)   # template animates once
flashes=[]
for k,q in enumerate(plan):
    cd,a,b,ae,IN,o=q['cd'],q['a'],q['b'],q['ae'],q['IN'],q['o']
    seq(cd/'in',ae,IN,f'ti{k}',x=60,y=100)
    seq(cd/'static.png',ae+IN-0.02,(b-o)-(ae+IN)+0.04,f'ts{k}',loop=True,x=60,y=100)    # 0.02s overlap = no blank frame
    if o: seq(cd/'out',b-o,o,f'to{k}',x=60,y=100)
    if q['flash']: flashes.append(ae+1.9)
filt.append(f"[vf][{cur}]overlay=0:1100[m0]"); cur='m0'      # put the region back once
for k,ft in enumerate(flashes):                                       # white flash when the number lands
    cmd+=['-f','lavfi','-i',f'color=c=white:s=1080x1920:r={FPS}:d=0.4']
    filt.append(f"[{n}:v]format=rgba,colorchannelmixer=aa=0.5,fade=t=out:st=0:d=0.3:alpha=1,setpts=PTS-STARTPTS+{ft:.3f}/TB[fl{k}]")
    filt.append(f"[{cur}][fl{k}]overlay=0:0:eof_action=pass:enable='between(t,{ft:.3f},{ft+0.31:.3f})'[fl{k}o]"); cur=f'fl{k}o'; n+=1
if cfg.get('progress',True):
    cmd+=['-f','lavfi','-i',f'color=c=0xffd23f:s=1080x8:r={FPS}']
    filt.append(f"[{cur}][{n}:v]overlay=x='-1080+1080*t/{dur}':y=110:eof_action=pass[vp]"); cur='vp'; n+=1
aud=cfg.get('audio','keep'); amap=[]
if aud not in('keep','none'):
    cmd+=['-ss',str(cfg.get('music_start',0)),'-t',str(dur),'-i',p(aud)]
    filt.append(f"[{n}:a]afade=t=in:d=0.2,afade=t=out:st={max(dur-0.6,0)}:d=0.6,loudnorm=I=-14:TP=-1.5[am]"); amap=['-map','[am]']
elif aud=='keep': amap=['-map','0:a?']
if aud=='none':
    cmd+=['-f','lavfi','-t',str(dur),'-i','anullsrc=r=44100:cl=stereo']; amap=['-map',f'{n}:a']; n+=1   # silent AAC track (Instagram expects an audio stream)
t_enc=time.time()
cmd+=['-filter_complex',';'.join(filt),'-map',f'[{cur}]']+amap+['-c:v','libx264','-pix_fmt','yuv420p','-crf','19','-preset','veryfast','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(d/'short.mp4')]
sh(*cmd)
print(f"OK {d/'short.mp4'} | overlays {t_job:.0f}s ({len(jobs)} new, {len(handles)-len(jobs)} cached) | encode {time.time()-t_enc:.0f}s | total {time.time()-T0:.0f}s")

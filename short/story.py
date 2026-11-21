#!/usr/bin/env python3
"""Story template -> short video.  Hook -> Message -> Hype/Gong -> CTA
usage: python3 story.py story.json
story.json: {"video":"clip.mp4","out":"name","audio":"none|keep|music/x.mp3","mode":"blur",
  "hook":"...","message":["beat 1","beat 2"],"gong":"...","cta":"...",
  "timing":{"hook":3,"message":3,"gong":3.5,"cta":2.3}}   (seconds; message is per beat)
Use \\n for line breaks (max 3 lines, ~22 chars per line)."""
import json,sys,subprocess,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
s=json.loads(pathlib.Path(sys.argv[1]).read_text())
T={'hook':3.0,'message':3.0,'gong':3.5,'cta':2.3,**s.get('timing',{})}
caps=[];t=0.1;imgs_by_cap=[]
def add(item,dur,part):
    global t
    txt=item['text'] if isinstance(item,dict) else item
    imgs_by_cap.append(item.get('img') if isinstance(item,dict) else None)
    lines=txt.split('\n')
    if len(lines)>3 or max(len(l) for l in lines)>26: print(f'! {part}: >3 lines or line >26 chars -> font will shrink: {txt!r}')
    caps.append({'text':txt,'start':round(t,2),'end':round(t+dur,2)}); t+=dur
add(s['hook'],T['hook'],'HOOK')
for i,m in enumerate(s['message']): add(m,T['message'],f'MESSAGE{i+1}')
add(s['gong'],T['gong'],'GONG')
if s.get('cta'): add(s['cta'],T['cta'],'CTA')
caps[-1]['end']=None
if s.get('images') and not s.get('video'):      # auto multi-shot footage from several images
    sys.path.insert(0,str(ROOT)); import shots
    imgs=[x if x.startswith('/') else str(ROOT.parent/x) for x in s['images']]
    od0=ROOT.parent/'out'/s['out']; od0.mkdir(parents=True,exist_ok=True)
    if any(imgs_by_cap):
        bounds=[0]+[c['start'] for c in caps[1:]]+[round(t,2)]
        nshots=shots.build_caps(imgs,round(t,2),[(bounds[i],bounds[i+1],imgs_by_cap[i]) for i in range(len(caps))],str(od0/'footage.mp4'),float(s.get('max_shot',2.6)))
    else:
        nshots=shots.build(imgs,round(t,2),[c['start'] for c in caps[1:]],str(od0/'footage.mp4'),float(s.get('max_shot',2.6)))
    s['video']=str(od0/'footage.mp4'); print(f'footage: {len(imgs)} images -> {nshots} shots')
cfg={k:s[k] for k in('video','out','audio','mode','start','font_size','center_y','source','progress') if k in s}
cfg['duration']=round(t,2); cfg['captions']=caps
if s.get('audio')=='sfx' and not s.get('sfx_full'): cfg['audio']='none'      # no sound effects at all (also no CTA chime)
elif s.get('audio')=='sfx':     # synthesized SFX; optional licensed music mixed underneath via "music"
    sys.path.insert(0,str(ROOT)); import sfx_gen
    od=ROOT.parent/'out'/s['out']; od.mkdir(parents=True,exist_ok=True)
    gi=next((i for i,c in enumerate(caps) if ('[[' in c['text'] or '((' in c['text'])),None)
    sfx_gen.gen(str(od/'sfx.wav'),cfg['duration'],[c['start'] for c in caps],gi,cta_idx=len(caps)-1 if s.get('cta') else None,full=bool(s.get('sfx_full',False)))
    cfg['audio']=str(od/'sfx.wav')
    if s.get('music'):
        mix=od/'mix.wav'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(od/'sfx.wav'),'-ss',str(s.get('music_start',0)),'-i',s['music'] if s['music'].startswith('/') else str(ROOT.parent/s['music']),
          '-filter_complex','[1:a]volume=0.45[m];[0:a][m]amix=inputs=2:duration=first:normalize=0','-t',str(cfg['duration']),str(mix)],check=True)
        cfg['audio']=str(mix)
(ROOT.parent/'out').mkdir(exist_ok=True); out=ROOT.parent/'out'/f"_{s['out']}.cfg.json"; out.write_text(json.dumps(cfg,ensure_ascii=False,indent=1))
print(f'total {t:.1f}s | hook 0-{0.2+T["hook"]:.1f}s | gong at {t-T["gong"]-(T["cta"] if s.get("cta") else 0):.1f}s')
subprocess.run(['python3',str(ROOT/'make_short.py'),str(out)],check=True)

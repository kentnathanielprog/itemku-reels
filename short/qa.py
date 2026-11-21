"""Video QA without opening images: resolution, duration, size, text dropouts (blink), audio plan."""
import subprocess,json,re,numpy as np
def run(path,story=None):
    I=[];ok=[]
    pr=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height,duration','-of','json',path],capture_output=True,text=True).stdout)['streams']
    v=[x for x in pr if x['codec_type']=='video'][0]; dur=float(v['duration'])
    if (v['width'],v['height'])!=(1080,1920): I.append(f"resolusi {v['width']}x{v['height']} (harus 1080x1920)")
    size=__import__('os').path.getsize(path)/1e6
    if size>50: I.append(f'ukuran {size:.0f}MB (>50MB)')
    # text-region blink check on raw gray frames (no PNG files)
    W,H=300,134
    raw=subprocess.run(['ffmpeg','-v','error','-i',path,'-vf',f'crop=900:400:100:1280,scale={W}:{H},format=gray','-f','rawvideo','-'],capture_output=True).stdout
    a=np.frombuffer(raw,np.uint8).reshape(-1,H,W); c=(a>235).sum((1,2))
    drops=[i for i in range(2,len(c)-2) if c[i]<0.6*min(c[i-1],c[i+1]) and min(c[i-1],c[i+1])>60]
    if drops: I.append('teks berkedip di frame '+','.join(f'{i}({i/30:.2f}s)' for i in drops[:5]))
    live=c[50:-3]; 
    if len(live) and (live<40).sum()>3: I.append(f'kotak teks kosong {int((live<40).sum())} frame setelah intro')
    try:
        import sys as _s,pathlib as _p; _s.path.insert(0,str(_p.Path(__file__).resolve().parent.parent/'auto')); import visual as _v
        _bad,_n=_v.frames_ok(path)
        if _bad: I.append(f'frame footage kosong/gelap: {_bad} dari {_n}')
    except Exception: pass
    # audio: every video MUST have an audible track (a silent AAC stream shows up on Instagram as "original audio" with no sound)
    def volumes():
        o=subprocess.run(['ffmpeg','-hide_banner','-i',path,'-af','volumedetect','-vn','-f','null','-'],capture_output=True,text=True).stderr
        m=re.search(r'mean_volume: (-?[\d.]+)',o); x=re.search(r'max_volume: (-?[\d.]+)',o); return (float(m.group(1)) if m else -99.0),(float(x.group(1)) if x else -99.0)
    if not any(x['codec_type']=='audio' for x in pr): I.append('tidak ada stream audio')
    else:
        mean_v,max_v=volumes()
        if mean_v<=-50: I.append(f'audio senyap (mean_volume {mean_v} dB, harus > -50 dB)')
        elif max_v>-0.5: I.append(f'audio clipping (max_volume {max_v} dB)')
    return I,f'{dur:.1f}s {size:.1f}MB'

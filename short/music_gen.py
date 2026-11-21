#!/usr/bin/env python3
"""Synthesizes the 5 background tracks in assets/audio/ from scratch (numpy + ffmpeg only): no samples, no recordings, no third-party material.
Deterministic (fixed seeds): the same code always yields the same notes. The audible result is then loudness-normalised to -18 LUFS (two-pass loudnorm)
and encoded as AAC 44.1 kHz stereo (.m4a). Chord progressions are generic (i-VI-III-VII, I-V-vi-IV ...); rhythms and melodies come from the seeded RNG.
usage: python3 short/music_gen.py [outdir=assets/audio] [name ...]"""
import sys,json,math,subprocess,tempfile,wave,pathlib
import numpy as np
SR=44100; LEN=60.0; N=int(SR*LEN)
def mtof(m): return 440.0*2**((m-69)/12)
def _env(n,a,d,s,r):
    """ADSR as a piecewise-linear curve over n samples"""
    tot=n/SR; rs=max(tot-r,a+0.002); ad=min(a+d,rs-0.001); x=np.arange(n)/SR
    return np.interp(x,[0,a,ad,rs,max(tot,rs+0.001)],[0,1,s,s,0])
def osc(f,n,kind,duty=0.5,harm=14):
    t=np.arange(n)/SR; ph=2*math.pi*f*t
    if kind=='sine': return np.sin(ph)
    if kind=='tri': return 2/math.pi*np.arcsin(np.sin(ph))
    if kind=='square': return np.where((f*t)%1.0<duty,1.0,-1.0)
    if kind=='saw':
        k=min(harm,int(SR/2/f)); return sum(np.sin(h*ph)/h for h in range(1,max(k,1)+1))*(2/math.pi)
    raise ValueError(kind)
def tone(f,dur,kind,amp=0.2,a=0.004,d=0.12,s=0.6,r=0.08,det=0.0,duty=0.5):
    n=int((dur+r)*SR); y=osc(f,n,kind,duty)
    if det: y=(y+osc(f*(1+det),n,kind,duty)+osc(f*(1-det),n,kind,duty))/3
    return amp*y*_env(n,a,d,s,r)
def pluck(f,dur,amp=0.25,decay=0.996):
    """Karplus-Strong string (vectorised per period)"""
    n=int(dur*SR); p=max(2,int(SR/f)); rng=np.random.default_rng(int(f*100)); buf=rng.uniform(-1,1,p); out=np.empty(n+p); out[:p]=buf
    for i in range(p,n+p,p): buf=decay*0.5*(buf+np.roll(buf,-1)); out[i:i+p]=buf[:len(out[i:i+p])]
    y=out[:n]; return amp*y*np.linspace(1,0.0,n)**0.6
def fm_bell(f,dur,amp=0.15):
    n=int(dur*SR); t=np.arange(n)/SR; idx=3.0*np.exp(-t*4); y=np.sin(2*math.pi*f*t+idx*np.sin(2*math.pi*f*3.5*t)); return amp*y*np.exp(-t*3.2)
def kick(amp=0.9,dur=0.28):
    n=int(dur*SR); t=np.arange(n)/SR; fr=45+95*np.exp(-t*28); ph=2*math.pi*np.cumsum(fr)/SR; return amp*np.sin(ph)*np.exp(-t*11)
def noise(n,seed): return np.random.default_rng(seed).uniform(-1,1,n)
def snare(amp=0.5,dur=0.2,seed=1,tone_hz=190):
    n=int(dur*SR); t=np.arange(n)/SR; return amp*(0.7*noise(n,seed)*np.exp(-t*22)+0.5*np.sin(2*math.pi*tone_hz*t)*np.exp(-t*30))
def clap(amp=0.45,seed=2):
    n=int(0.22*SR); t=np.arange(n)/SR; env=sum(np.exp(-(t-o)*60)*(t>=o) for o in (0,0.012,0.024))*0.5+np.exp(-t*18)*0.4; return amp*noise(n,seed)*env
def hat(amp=0.2,dur=0.05,seed=3):
    n=int(dur*SR); t=np.arange(n)/SR; x=noise(n,seed); x=np.diff(x,prepend=0); return amp*x*np.exp(-t*90)
def chip_noise(amp=0.18,dur=0.08,seed=4):
    n=int(dur*SR); t=np.arange(n)/SR; x=np.sign(noise(n,seed)); return amp*x*np.exp(-t*40)
def lowpass1(x,fc):
    a=math.exp(-2*math.pi*fc/SR); y=np.empty_like(x); acc=0.0; b=1-a
    for i in range(len(x)): acc=b*x[i]+a*acc; y[i]=acc
    return y
class Mix:
    def __init__(s): s.L=np.zeros(N+SR); s.R=np.zeros(N+SR)
    def add(s,x,t,gain=1.0,pan=0.0):
        i=int(t*SR)
        if i>=N: return
        x=x[:N+SR-i]; gl=gain*math.cos((pan+1)*math.pi/4); gr=gain*math.sin((pan+1)*math.pi/4); s.L[i:i+len(x)]+=x*gl; s.R[i:i+len(x)]+=x*gr
    def out(s): return np.tanh(np.stack([s.L[:N],s.R[:N]],1)*0.9)
def duck_env(bpm,depth=0.7,rel=0.14):
    beat=60/bpm; t=np.arange(N)/SR; ph=(t%beat); return 1-depth*np.exp(-ph/rel)
def chords(root,quality_list): return [[root+i for i in q] for q in quality_list]
# ---- tracks ---------------------------------------------------------------------------------------------------------------------------------------
def t_pulse_arena():      # EDM, 128 BPM, F minor: Fm Db Ab Eb
    bpm=128; b=60/bpm; m=Mix(); prog=[(41,[0,3,7]),(37,[0,4,7]),(44,[0,4,7]),(39,[0,4,7])]
    duck=duck_env(bpm); sc=np.zeros(N+SR)            # pad + bass go through a sidechain-style duck on every kick
    for bar in range(int(LEN/(4*b))+1):
        t0=bar*4*b; root,ch=prog[bar%4]
        if t0>=LEN: break
        for iv in ch:
            y=tone(mtof(root+12+iv),4*b,'saw',amp=0.06,a=0.03,d=0.2,s=0.8,r=0.2,det=0.006); i=int(t0*SR); sc[i:i+len(y)]+=y[:len(sc)-i]
        for k in (1,3,5,7):                           # off-beat eighth bass
            ts=t0+k*b/2
            if ts<LEN: y=tone(mtof(root-12),b*0.42,'saw',amp=0.16,a=0.004,d=0.08,s=0.5,r=0.05); i=int(ts*SR); sc[i:i+len(y)]+=y[:len(sc)-i]
        pat=[0,1,2,1] if bar%2==0 else [2,1,0,1]
        for s in range(16):
            ts=t0+s*b/4
            if ts>=LEN: break
            f=mtof(root+24+ch[pat[s%4]%3]+(12 if (s//4)%2 and bar>=2 else 0)); m.add(tone(f,b/4*0.9,'square',amp=0.05,a=0.002,d=0.05,s=0.3,r=0.03,duty=0.4),ts,1.0,-0.4+0.8*((s%4)/3))
        for beat in range(4):
            tb=t0+beat*b
            if tb>=LEN: break
            m.add(kick(),tb,1.0,0.0)
            if beat in (1,3): m.add(clap(seed=bar*4+beat),tb,0.9,0.1)
            m.add(hat(seed=bar*8+beat),tb+b/2,0.8,0.35)
    mixed=sc[:N]*duck*0.9; m.L[:N]+=mixed; m.R[:N]+=mixed
    return m.out()
def t_pixel_jump():       # chiptune, 120 BPM, C major: C G Am F
    bpm=120; b=60/bpm; m=Mix(); rng=np.random.default_rng(202); prog=[(48,[0,4,7]),(43,[0,4,7]),(45,[0,3,7]),(41,[0,4,7])]; pent=[0,2,4,7,9]
    motif=[int(x) for x in rng.integers(0,5,8)]
    for bar in range(int(LEN/(4*b))+1):
        t0=bar*4*b; root,ch=prog[bar%4]
        if t0>=LEN: break
        for s in range(16):
            ts=t0+s*b/4
            if ts>=LEN: break
            f=mtof(root+24+ch[[0,1,2,1][s%4]]); m.add(tone(f,b/4*0.85,'square',amp=0.07,a=0.002,d=0.04,s=0.5,r=0.02,duty=0.25),ts,1.0,-0.3)
        for k in range(8):
            ts=t0+k*b/2
            if ts>=LEN: break
            note=root-12+(0 if k%2==0 else ch[2]); m.add(tone(mtof(note),b/2*0.9,'tri',amp=0.28,a=0.003,d=0.05,s=0.8,r=0.03),ts,1.0,0.0)
            m.add(chip_noise(seed=bar*8+k,amp=0.14 if k%2 else 0.1),ts,0.8,0.3)
        for beat in range(4):
            tb=t0+beat*b
            if tb>=LEN: break
            if beat in (0,2): m.add(kick(amp=0.7,dur=0.2),tb,1.0,0.0)
            if beat in (1,3): m.add(snare(amp=0.38,seed=bar*4+beat,dur=0.14),tb,1.0,0.0)
        if bar%2==1:
            for j in range(4):
                ts=t0+(j*2+0)*b/2; f=mtof(72+pent[motif[(bar//2*4+j)%8]]); m.add(tone(f,b*0.9,'square',amp=0.06,a=0.003,d=0.1,s=0.5,r=0.05,duty=0.5),ts,1.0,0.5)
    return m.out()
def t_low_tide():         # lo-fi, 84 BPM swung, A minor: Am7 Fmaj7 Cmaj7 G6
    bpm=84; b=60/bpm; m=Mix(); rng=np.random.default_rng(303); prog=[(57,[0,3,7,10]),(53,[0,4,7,11]),(48,[0,4,7,11]),(43,[0,4,7,9])]; pent=[0,3,5,7,10]
    def ep(f,dur,amp):
        n=int((dur+0.1)*SR); t=np.arange(n)/SR; y=(np.sin(2*math.pi*f*t)+0.3*np.sin(2*math.pi*2*f*t)+0.1*np.sin(2*math.pi*3*f*t)); return amp*y*np.exp(-t*2.4)*np.minimum(1,t*200)
    for bar in range(int(LEN/(4*b))+1):
        t0=bar*4*b; root,ch=prog[bar%4]
        if t0>=LEN: break
        for hit in (0.0,2.5):
            for j,iv in enumerate(ch):
                m.add(ep(mtof(root+12+iv),b*1.6,0.075),t0+(hit+0.015*j)*b+(0.08*b if hit else 0),1.0,-0.3+0.2*j/3)
        m.add(tone(mtof(root-12),b*1.8,'sine',amp=0.3,a=0.01,d=0.3,s=0.6,r=0.2),t0,1.0,0.0); m.add(tone(mtof(root-12+7),b*1.2,'sine',amp=0.22,a=0.01,d=0.3,s=0.5,r=0.2),t0+2*b,1.0,0.0)
        m.add(kick(amp=0.55,dur=0.3),t0,1.0,0.0); m.add(kick(amp=0.45,dur=0.3),t0+2.5*b+0.08*b,1.0,0.0)
        for beat in (1,3): m.add(lowpass1(snare(amp=0.4,seed=bar*4+beat,dur=0.25),3500),t0+beat*b,1.0,0.0)
        for k in range(8): m.add(hat(amp=0.1,seed=bar*8+k),t0+k*b/2+(0.1*b if k%2 else 0),0.7,0.3)
        for j in range(3):
            if rng.random()<0.65: m.add(tone(mtof(72+pent[int(rng.integers(0,5))]),b*rng.choice([0.5,1.0,1.5]),'tri',amp=0.08,a=0.01,d=0.2,s=0.4,r=0.15),t0+(1+j*1.1)*b,1.0,0.4)
    return m.out()
def t_sunny_lane():       # upbeat plucked pop, 110 BPM, G major: G D Em C
    bpm=110; b=60/bpm; m=Mix(); rng=np.random.default_rng(404); prog=[(55,[0,4,7]),(50,[0,4,7]),(52,[0,3,7]),(48,[0,4,7])]; pent=[0,2,4,7,9]
    for bar in range(int(LEN/(4*b))+1):
        t0=bar*4*b; root,ch=prog[bar%4]
        if t0>=LEN: break
        for k in range(8):
            ts=t0+k*b/2
            if ts>=LEN: break
            acc=1.0 if k in (0,3,4,6) else 0.55
            for j,iv in enumerate([0,7,12,16] if k%2==0 else [12,16,19]):
                m.add(pluck(mtof(root+12+iv),b*0.9,amp=0.2*acc),ts+0.012*j,1.0,-0.35+0.15*j)
        m.add(tone(mtof(root-12),b*0.9,'sine',amp=0.3,a=0.005,d=0.12,s=0.6,r=0.06),t0,1.0,0.0); m.add(tone(mtof(root-12+7),b*0.9,'tri',amp=0.2,a=0.005,d=0.12,s=0.6,r=0.06),t0+2.5*b,1.0,0.0)
        for beat in range(4):
            tb=t0+beat*b
            if tb>=LEN: break
            if beat in (0,2): m.add(kick(amp=0.65,dur=0.25),tb,1.0,0.0)
            if beat in (1,3): m.add(snare(amp=0.3,seed=bar*4+beat,dur=0.16),tb,1.0,0.0); m.add(clap(amp=0.25,seed=bar*4+beat+50),tb,0.8,0.2)
            m.add(hat(amp=0.13,seed=bar*8+beat),tb+b/2,0.8,0.3)
        for j in range(4):
            if rng.random()<0.7: m.add(pluck(mtof(79+pent[int(rng.integers(0,5))]),b*0.8,amp=0.15),t0+j*b+(0.5*b if rng.random()<0.4 else 0),1.0,0.45)
    return m.out()
def t_dark_alley():       # dark trap, 140 BPM (half-time snare), D minor: Dm Bb Gm A
    bpm=140; b=60/bpm; m=Mix(); rng=np.random.default_rng(505); prog=[(38,[0,3,7]),(34,[0,4,7]),(43,[0,3,7]),(45,[0,4,7])]; pent=[0,3,5,7,10]
    for bar in range(int(LEN/(4*b))+1):
        t0=bar*4*b; root,ch=prog[bar%4]
        if t0>=LEN: break
        for iv in ch:
            y=lowpass1(tone(mtof(root+12+iv),4*b,'saw',amp=0.07,a=0.08,d=0.3,s=0.7,r=0.3,det=0.004),1400); m.add(y,t0,1.0,0.0)
        for hit in (0.0,1.75,3.0):
            n=int(b*1.6*SR); t=np.arange(n)/SR; fr=mtof(root-12)*(1+0.4*np.exp(-t*30)); y=0.55*np.sin(2*math.pi*np.cumsum(fr)/SR)*np.exp(-t*2.2); m.add(y,t0+hit*b,1.0,0.0)
        m.add(snare(amp=0.5,seed=bar+9,dur=0.25,tone_hz=175),t0+2*b,1.0,0.0); m.add(clap(amp=0.3,seed=bar+70),t0+2*b,0.8,0.15)
        for k in range(8):
            ts=t0+k*b/2; roll=rng.random()<0.25
            m.add(hat(amp=0.17,seed=bar*16+k),ts,0.8,0.35+0.1*(k%2))
            if roll: m.add(hat(amp=0.13,seed=bar*16+k+8),ts+b/4,0.7,-0.3); m.add(hat(amp=0.1,seed=bar*16+k+9),ts+b/8,0.7,0.3)
        for j in range(3):
            if rng.random()<0.6: m.add(fm_bell(mtof(74+pent[int(rng.integers(0,5))]),b*1.5,amp=0.13),t0+(0.5+j*1.3)*b,1.0,0.4)
    return m.out()
TRACKS={'pulse-arena':t_pulse_arena,'pixel-jump':t_pixel_jump,'low-tide':t_low_tide,'sunny-lane':t_sunny_lane,'dark-alley':t_dark_alley}
def encode(stereo,out):
    """float stereo -> wav -> ffmpeg: gentle low-pass + echo, two-pass loudnorm to -18 LUFS (TP -2), AAC 44.1 kHz stereo .m4a"""
    tmp=pathlib.Path(tempfile.mkdtemp(prefix='musicgen_')); wav=tmp/'raw.wav'; pcm=(np.clip(stereo,-1,1)*32767).astype('<i2')
    with wave.open(str(wav),'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    fx='lowpass=f=11000,aecho=0.7:0.4:170|250:0.16|0.1'; ln='loudnorm=I=-18:TP=-2:LRA=7'
    r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(wav),'-af',f'{fx},{ln}:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
    j=json.loads(r[r.rindex('{'):r.rindex('}')+1])
    af=f"{fx},{ln}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=44100"
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(wav),'-af',af,'-ar','44100','-ac','2','-c:a','aac','-b:a','128k','-movflags','+faststart',str(out)],check=True)
if __name__=='__main__':
    a=sys.argv[1:]; od=pathlib.Path(a[0] if a and not a[0] in TRACKS else 'assets/audio'); names=[x for x in a if x in TRACKS] or list(TRACKS); od.mkdir(parents=True,exist_ok=True)
    for n in names: encode(TRACKS[n](),od/f'{n}.m4a'); print('ok',od/f'{n}.m4a')

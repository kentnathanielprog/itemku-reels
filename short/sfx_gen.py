"""Sound effects only (royalty-free, synthesized): whoosh per caption, count ticks + impact on gong, pop on CTA."""
import numpy as np, wave
sr=44100
def gen(path,dur,starts,gong_idx=None,count_start=.9,count_dur=1.0,cta_idx=None,full=False):
    N=int(sr*dur); L=np.zeros(N); R=np.zeros(N); rng=np.random.default_rng(5)
    def add(sig,at,g=1.):
        i=int(at*sr)
        if i<0 or i>=N: return
        n=min(len(sig),N-i); L[i:i+n]+=sig[:n]*g; R[i:i+n]+=sig[:n]*g
    def tt(d): return np.arange(int(sr*d))/sr
    def lp(x,k): return np.convolve(x,np.ones(k)/k,'same')
    def whoosh(d=.45,v=.5):
        x=tt(d); n=rng.standard_normal(len(x)); env=np.sin(np.pi*np.clip(x/d,0,1))**2
        f=300+4000*(x/d); tone=np.sin(2*np.pi*np.cumsum(f)/sr)*.25
        return (lp(n,6)*.8+tone)*env*v
    if full: add(whoosh(.7,.55),0.0)           # template rise
    for i,s in enumerate(starts):
        if full: add(whoosh(.4,.4),max(s-.05,0))
    if full and gong_idx is not None:
        g=starts[gong_idx]; t0=g+count_start; n=int(count_dur*30)
        for k in range(n):                      # rising ticks while counting
            x=tt(.05); f=900+900*k/n; add(np.sin(2*np.pi*f*x)*np.exp(-x*70)*.35,t0+k/30)
        e=g+count_start+count_dur
        x=tt(.5); kick=np.sin(2*np.pi*np.cumsum(45+120*np.exp(-x*30))/sr)*np.exp(-x*7)
        add(kick*1.0,e); add(np.sin(2*np.pi*55*tt(1.2))*np.exp(-tt(1.2)*3.5)*.7,e)
        x=tt(1.4); add(lp(rng.standard_normal(len(x)),3)*np.exp(-x*4)*.45,e)   # air burst / tail
        add(whoosh(.9,.35),e-.95)
    if cta_idx is not None:
        s=starts[cta_idx]
        for j,f in enumerate((784,1175,1568)):
            x=tt(.7); add((np.sin(2*np.pi*f*x)+.3*np.sin(2*np.pi*2*f*x))*np.exp(-x*6)*.5,s+.1+j*.1)
    fade=np.minimum(1,(dur-np.arange(N)/sr)/.3)
    st=np.stack([np.tanh(L*1.2)*fade,np.tanh(R*1.2)*fade],1); st=st/max(np.abs(st).max(),1e-6)*.85
    w=wave.open(path,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes((st*32767).astype('<i2').tobytes()); w.close()

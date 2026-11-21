#!/usr/bin/env python3
"""One entry point per video.
  python3 make_video.py find <mlbb|roblox|gta|general> [n]      -> headlines (no web-search tokens)
  python3 make_video.py new <url> <name> [mlbb|roblox|gta]      -> fetch article + images, write stories/<name>.json draft (+ prints facts)
  python3 make_video.py build stories/a.json [b.json ...] [--sheet]   -> lint -> render -> QA -> caption.txt   (batch = several files)
Edit hook/message/gong in the draft between `new` and `build`."""
import sys,json,subprocess,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; sys.path.insert(0,str(ROOT))
CTA={'mlbb':'Cek Itemku buat\nkebutuhan MLBB kamu','roblox':'Cek Itemku buat\nkebutuhan Roblox kamu','general':'Cek Itemku buat\nkebutuhan game kamu'}
TAGS={'mlbb':['MLBB','MobileLegends','esports','itemku'],'roblox':['Roblox','RobloxIndonesia','gamingnews','itemku'],'gta':['GTA6','GTAVI','gamingnews','itemku']}
def sh(*a,**k): return subprocess.run(list(a),**k)
def cmd_new(url,name,cat='general'):
    r=sh('python3','-W','ignore',str(ROOT/'fetch_news.py'),url,name,'6',capture_output=True,text=True); print(r.stdout.strip()[:1800]); 
    if r.returncode: print(r.stderr[-400:]); return
    art=json.loads((BASE/'out'/name/'article.json').read_text()); imgs=[str(pathlib.Path(i['file']).relative_to(BASE)) for i in art['images']]
    d={"images":imgs,"out":f"short-{name}","audio":"none","mode":"blur","center_y":800,
       "source":art['site']+(f", data {art['date'][:10]}" if art['date'] else ''),"credit":"TODO: kredit gambar",
       "hook":"TODO hook: bikin penasaran, tutup dengan janji (tunggu angkanya)","message":["TODO fakta utama","TODO konteks"],
       "gong":"TODO [[angka]] atau ((kata kunci))","cta":CTA.get(cat,CTA["general"]),"timing":{"hook":3,"message":3,"gong":3.9,"cta":2.3},
       "hashtags":TAGS.get(cat,['gamingnews','itemku'])}
    (ROOT/'stories').mkdir(exist_ok=True); f=ROOT/'stories'/f'{name}.json'; f.write_text(json.dumps(d,ensure_ascii=False,indent=1)); print(f'\nDRAFT: {f}')
def cmd_build(files,sheet=False,lint_only=False):
    from lint import lint; import qa
    for f in files:
        f=pathlib.Path(f); s=json.loads(f.read_text()); P,W=lint(s,BASE)
        print(f'--- {f.name}'); [print('  ✗',x) for x in P]; [print('  !',x) for x in W]
        if P: print('  -> perbaiki dulu (tidak dirender)'); continue
        if lint_only: print('  lint OK ✓ (--lint-only: tidak dirender)'); continue
        r=sh('python3',str(ROOT/'story.py'),str(f),capture_output=True,text=True)
        if r.returncode: print(r.stderr[-600:]); continue
        print('  '+r.stdout.strip().splitlines()[-1])
        out=BASE/'out'/s['out']/'short.mp4'; I,info=qa.run(str(out),s); print(f'  QA {info}: '+('OK ✓' if not I else ''))
        for x in I: print('  ✗ QA:',x)
        hook=re.sub(r'\[\[|\]\]|\(\(|\)\)','',(s['hook']['text'] if isinstance(s['hook'],dict) else s['hook'])).replace('\n',' ')
        cap=f"{hook}\n\nSumber: {s['source']}"+(f"\nKredit gambar: {s['credit']}" if s.get('credit') else '')+"\n\nFollow @itemku untuk berita game lainnya!\n\n"+' '.join('#'+h for h in s.get('hashtags',['itemku']))+'\n'
        (out.parent/'caption.txt').write_text(cap)
        if sheet:
            tmp=out.parent/'sheet.png'; sh('bash','-c',f'cd {out.parent} && for n in 25 120 200 300 340 440; do ffmpeg -y -loglevel error -i short.mp4 -vf "select=eq(n\\,$n),crop=1080:1100:0:420,scale=240:-2" -vsync 0 _s$n.png; done; ffmpeg -y -loglevel error -i _s25.png -i _s120.png -i _s200.png -i _s300.png -i _s340.png -i _s440.png -filter_complex "[0][1][2]hstack=3[a];[3][4][5]hstack=3[b];[a][b]vstack" sheet.png'); print('  sheet:',tmp)
        print(f'  FILES: {out}  +  caption.txt')
if __name__=='__main__':
    a=sys.argv[1:]
    if not a: print(__doc__)
    elif a[0]=='find': sh('python3',str(ROOT/'find_news.py'),*a[1:])
    elif a[0]=='new': cmd_new(a[1],a[2],a[3] if len(a)>3 else 'general')
    elif a[0]=='build': cmd_build([x for x in a[1:] if not x.startswith('--')],'--sheet' in a,'--lint-only' in a)

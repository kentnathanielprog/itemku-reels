"""Story lint: catches the mistakes that used to cost a re-render (runs in <1s, before any rendering)."""
import re,json,pathlib
STIFF={'merupakan':'itu / jadi','tersebut':'itu','dinobatkan':'dapat gelar / jadi juara','menyatakan':'bilang','mengumumkan':'ngumumin','sangat':'banget','tidak ':'nggak ','sudah':'udah','bagaimana':'gimana','namun':'tapi','kemudian':'terus','sebagaimana':'kayak','mengungkapkan':'bocorin','berhasil meraih':'dapet','penghargaan':'award','diperkirakan':'katanya'}
OPEN=re.compile(r'tunggu|sampai (akhir|habis)|ternyata|rahasia|jangan|kenapa|\?|bocoran|heboh',re.I)
HEDGE=re.compile(r'estimasi|tercatat|menurut|katanya|data|jika|bilang|nyebut|versi',re.I)
SUPER=re.compile(r'rekor|terbesar|tertinggi|pertama dalam|paling|sejarah',re.I)
def strip(t): return re.sub(r'\[\[|\]\]|\(\(|\)\)','',t)
def caption_items(s):
    out=[('hook',s['hook'])]+[(f'pesan{i+1}',m) for i,m in enumerate(s['message'])]+[('gong',s['gong'])]
    if s.get('cta'): out.append(('cta',s['cta']))
    return [(n,(i['text'] if isinstance(i,dict) else i)) for n,i in out]
def lint(s,base):
    P=[]; W=[]
    for k in ('hook','message','gong'):
        if k not in s: P.append(f'field "{k}" missing')
    if P: return P,W
    if not s.get('source'): P.append('"source" kosong (wajib: tampil di slide akhir)')
    for name,txt in caption_items(s):
        lines=txt.split('\n'); plain=[strip(l) for l in lines]
        if 'TODO' in txt: P.append(f'{name}: masih TODO'); continue
        if len(lines)>3: P.append(f'{name}: {len(lines)} baris (maks 3)')
        for ln in lines:
            if ln.count('((')!=ln.count('))') or ln.count('[[')!=ln.count(']]'): P.append(f'{name}: tanda (( )) atau [[ ]] harus buka-tutup di BARIS yang sama: {ln!r}')
        for l in plain:
            if len(l)>26: W.append(f'{name}: "{l}" {len(l)} huruf (>26, font mengecil)')
            letters=[c for c in l if c.isalpha()]
            if len(letters)>8 and sum(c.isupper() for c in letters)/len(letters)>0.8 and not re.fullmatch(r'[A-Z0-9 &+.\-]+',l) is None and False: pass
        full=' '.join(plain)
        letters=[c for c in full if c.isalpha()]
        if len(letters)>12 and sum(c.isupper() for c in letters)/len(letters)>0.7: P.append(f'{name}: KAPITAL SEMUA -> pakai huruf kapital di awal saja')
        if plain[0] and plain[0][0].isalpha() and plain[0][0].islower(): P.append(f'{name}: huruf pertama harus kapital')
        for w,alt in STIFF.items():
            if re.search(r'\b'+re.escape(w.strip()),full,re.I): W.append(f'{name}: kaku "{w.strip()}" -> {alt}')
        for m in re.finditer(r'\[\[(.+?)\]\]',txt):
            if not re.fullmatch(r'\d+(,\d+)?',m.group(1)): P.append(f'{name}: [[{m.group(1)}]] harus angka (contoh 9,7)')
    hook=strip(caption_items(s)[0][1]); gong=caption_items(s)[-2 if s.get('cta') else -1][1]
    if not OPEN.search(hook): W.append('hook: belum ada janji/open-loop (mis. "tunggu angkanya")')
    if '[[' not in gong and '((' not in gong: W.append('gong: belum ada sorotan ([[angka]] atau ((kata kunci)))')
    alltxt=' '.join(t for _,t in caption_items(s))
    if SUPER.search(alltxt) and not (HEDGE.search(alltxt) or HEDGE.search(s.get('source',''))): W.append('klaim superlatif (rekor/terbesar...) tanpa kata penahan (estimasi/tercatat/menurut)')
    T=s.get('timing',{}); total=0.1+T.get('hook',3)+T.get('message',3)*len(s['message'])+T.get('gong',3.5)+(T.get('cta',2.3) if s.get('cta') else 0)
    if total>18: W.append(f'durasi {total:.0f}s (>18s: retensi turun)')
    if 0<len(s.get('images',[]))<3: W.append(f"gambar cuma {len(s['images'])}: kurang variasi (tambah dari artikel terkait)")
    for im in s.get('images',[]):
        pth=pathlib.Path(im if im.startswith('/') else base/im)
        if not pth.exists(): P.append(f'gambar tidak ada: {im}')
        else:
            try:
                from PIL import Image; w,_=Image.open(pth).size
                if w<1000: W.append(f'gambar {pth.name} cuma {w}px (agak buram)')
            except Exception: pass
    for name,it in [('hook',s['hook']),('gong',s['gong'])]+[(f'pesan{i+1}',m) for i,m in enumerate(s['message'])]:
        if isinstance(it,dict) and it.get('img') and s.get('images'):
            bad=[i for i in it['img'] if i>=len(s['images'])]
            if bad: P.append(f'{name}: img {bad} di luar daftar images')
    return P,W

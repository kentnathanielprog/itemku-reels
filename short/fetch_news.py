#!/usr/bin/env python3
"""Fetch a news article: title/date/short summary (printed compactly) + best images saved to out/<name>/imgs.
usage: python3 fetch_news.py <url> <name> [max_images=6]
Prints only what is needed to write the hook/message (keeps token use low)."""
import sys,re,html,json,urllib.request,urllib.parse,pathlib,io
from PIL import Image
url,name=sys.argv[1],sys.argv[2]; MAXI=int(sys.argv[3]) if len(sys.argv)>3 else 6
BASE=pathlib.Path(__file__).resolve().parent.parent; D=BASE/'out'/name/'imgs'; D.mkdir(parents=True,exist_ok=True)
UA={'User-Agent':'Mozilla/5.0'}
def get(u,binary=False):
    r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30).read()
    return r if binary else r.decode('utf-8','ignore')
page=get(url)
def meta(*keys):
    for k in keys:
        m=re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"'%k,page) or re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"'%k,page)
        if m: return html.unescape(m.group(1))
title=meta('og:title','twitter:title') or ''; desc=meta('og:description','description') or ''
date=meta('article:published_time','og:updated_time') or ''; site=meta('og:site_name') or urllib.parse.urlparse(url).netloc
body=re.sub(r'<script.*?</script>|<style.*?</style>|<nav.*?</nav>|<footer.*?</footer>','',page,flags=re.S)
art=re.search(r'<article.*?</article>',body,flags=re.S); scope=art.group(0) if art else body
paras=[re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',p))).strip() for p in re.findall(r'<p[^>]*>(.*?)</p>',scope,flags=re.S)]
paras=[p for p in paras if len(p)>70][:8]; summary=' '.join(paras)[:900]
if len(summary)<200:    # sites that don't use <p>: take the plain text after the headline / 'Ringkasnya'
    flat=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',body)))
    i=flat.find('Ringkasnya'); i=i if i>=0 else max(flat.find(title[:40]),0)
    summary=flat[i:i+1400]
flat_all=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',body)))
# 'clean' = article paragraphs only (no menus/sidebars/'Baca juga'); used for LLM input to save tokens. fulltext stays for evidence checks.
_pp=[re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',x))).strip() for x in re.findall(r'<(?:p|li|h2|h3)[^>]*>(.*?)</(?:p|li|h2|h3)>',scope,flags=re.S)]
_seen=set(); _cl=[]
for x in _pp:
    if len(x)>=40 and x not in _seen and not re.search(r'baca juga|read more|related|share|bagikan|advertisement|iklan|cookie|subscribe|newsletter',x[:60],re.I): _seen.add(x); _cl.append(x)
clean_text=' '.join(_cl)[:12000]
# ---- images
cands=[]
for k in ('og:image','twitter:image'):
    v=meta(k); 
    if v: cands.append(v)
for tag in re.findall(r'<img[^>]+>',scope):
    srcs=[]
    ss=re.search(r'(?:srcset|data-srcset)="([^"]+)"',tag)
    if ss:
        parts=[p.strip().split() for p in ss.group(1).split(',') if p.strip()]
        parts=[(int(re.sub(r'\D','',p[1]) or 0) if len(p)>1 else 0,p[0]) for p in parts]; 
        if parts: srcs.append(max(parts)[1])
    s=re.search(r'(?:data-src|data-lazy-src|src)="([^"]+)"',tag)
    if s: srcs.append(s.group(1))
    cands+=srcs
bad=re.compile(r'logo|icon|avatar|sprite|pixel|badge|button|banner-ad|adserver|gravatar|placeholder|\.svg|\.gif|data:image|emoji|author|profile',re.I)
# fallback: article body had <3 images -> also scan the whole page for images that share a keyword with the title
if len(cands)<3:
    toks=[w for w in re.findall(r'[a-z0-9]{4,}',title.lower()) if w not in ('games','game','best','this','that','with','from','2026','2025')]
    for tag in re.findall(r'<(?:img|source)[^>]+>',page):
        for m in re.finditer(r'(?:src|data-src|srcset)="([^"\s,]+)',tag):
            if any(w in m.group(1).lower() for w in toks): cands.append(m.group(1))
def upgrade(u):   # ask CDNs that resize on the fly for a bigger image
    u=re.sub(r'([?&])width=\d+',r'\1width=1280',u); u=re.sub(r'([?&])height=\d+&?','\\1',u); return re.sub(r'&?format=webp','',u)
STOP={'the','and','for','with','from','this','that','yang','dan','untuk','dengan','dari','game','games','gaming','news','new','baru','2026','2025'}
_tt={w for w in re.findall(r'[a-z]{3,}',(title+' '+urllib.parse.urlparse(url).path).lower()) if w not in STOP}
_og={u for u in [meta('og:image'),meta('twitter:image')] if u}
def relevant(u):
    stem=re.sub(r'[-_]\d+x\d+|-scaled','',u.split('?')[0].rsplit('/',1)[-1].rsplit('.',1)[0]).lower()
    ws={w for w in re.findall(r'[a-z]{3,}',stem) if w not in STOP}
    if u in _og or len(ws)<2: return True            # og:image, or an opaque/hash-like filename -> keep
    return bool(ws&_tt)                              # descriptive filename must share a word with the article title/url
seen=set();out=[]
for c in cands:
    u=upgrade(urllib.parse.urljoin(url,html.unescape(c).strip()))
    if bad.search(u) or not re.search(r'\.(jpe?g|png|webp)',u,re.I): continue
    key=re.sub(r'[-_]\d+x\d+|\?.*','',u)
    if not relevant(u): continue
    if key in seen: continue
    seen.add(key); out.append(u)
saved=[]; hashes=[]
def ahash(im):
    g=im.convert('L').resize((16,9)); a=list(g.getdata()); m=sum(a)/len(a); return [x>m for x in a]
for u in out[:MAXI*5]:
    try:
        b=get(u,True); im=Image.open(io.BytesIO(b)).convert('RGB')
    except Exception: continue
    w,h=im.size
    if w<700 or not .5<w/h<2.6: continue
    hh=ahash(im)
    if any(sum(x!=y for x,y in zip(hh,o))<=12 for o in hashes): continue   # skip near-duplicate artwork
    hashes.append(hh)
    f=D/f'img{len(saved)+1}.jpg'; im.save(f,quality=92); saved.append({'file':str(f),'w':w,'h':h,'url':u})
    if len(saved)>=MAXI: break
json.dump({'url':url,'title':title,'date':date,'site':site,'desc':desc,'summary':summary,'fulltext':flat_all[:40000],'clean':clean_text,'images':saved},open(D.parent/'article.json','w'),ensure_ascii=False,indent=1)
print(f'TITLE: {title}\nSITE: {site} | DATE: {date[:10]}\nDESC: {desc}\nTEXT: {summary[:700]}\nIMAGES({len(saved)}): '+', '.join(f"{pathlib.Path(s["file"]).name}={s["w"]}x{s["h"]}" for s in saved)+f'\nDIR: {D}')

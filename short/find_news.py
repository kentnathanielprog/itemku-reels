#!/usr/bin/env python3
"""Compact headline finder (no web-search tokens). usage: python3 find_news.py <mlbb|roblox|gta|general> [n=8]
Reads curated pages in sources.json, keeps links that match the category keywords, prints 'title | url' (newest first as listed)."""
import sys,re,json,html,urllib.request,urllib.parse,pathlib
cat=sys.argv[1]; N=int(sys.argv[2]) if len(sys.argv)>2 else 8
S=json.loads((pathlib.Path(__file__).resolve().parent/'sources.json').read_text())[cat]
seen=set();per=[]
for pg in S['pages']:
    page=pg['url'] if isinstance(pg,dict) else pg; trusted=isinstance(pg,dict) and pg.get('trusted'); rows=[]
    try: t=urllib.request.urlopen(urllib.request.Request(page,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read().decode('utf-8','ignore')
    except Exception as e: print(f'# skip {urllib.parse.urlparse(page).netloc} ({str(e)[:30]})'); continue
    host=urllib.parse.urlparse(page).netloc
    for m in re.finditer(r'<a[^>]+href=["\']?([^"\'\s>#]+)["\']?[^>]*>(.*?)</a>',t,flags=re.S):
        u=urllib.parse.urljoin(page,html.unescape(m.group(1))); path=urllib.parse.urlparse(u).path
        if urllib.parse.urlparse(u).netloc.replace('www.','')!=host.replace('www.','') or u in seen: continue
        slug=path.rstrip('/').split('/')[-1]
        if slug.count('-')<3 or re.search(r'/(tag|category|author|page|about|contact)/|/guide/|guideline|pitching|/wikis?/|cheats|upcoming|-releases|walkthrough|tier-list|opinion|how-to|-guide|best-|ultimate',path): continue      # article-like only
        text=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',m.group(2)))).strip()
        title=text if 25<len(text)<160 else re.sub(r'^[A-Za-z0-9]{6,10}-','',slug).replace('-',' ')
        hay=(slug+' '+title).lower()
        if S['keywords'] and not trusted and not any(k in hay for k in S['keywords']): continue
        seen.add(u); rows.append((title,u))
    per.append(rows[:6])
rows=[]
for i in range(6):                                   # round-robin across sites so no single site dominates
    for r in per:
        if i<len(r): rows.append(r[i])
for title,u in rows[:N]: print(f'{title[:90]} | {u}')
if not rows: print('# nothing matched - widen keywords or add pages in sources.json')

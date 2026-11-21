"""Extra-image helpers for fetch_news.py (pure, no network): pick topical same-site links from an article so their og:image can add variety."""
import re,html,urllib.parse
STOP={'the','and','for','with','from','this','that','yang','dan','untuk','dengan','dari','game','games','gaming','news','new','baru','2026','2025','how','what','why','steam','players','player','update','updates','patch','notes','release','released','launch','season','event','free','play','plays','played','mobile','android','official','review','trailer','gameplay','best','top','list','guide','after','amid','over','into','more','about','their','will','gets','get','now','says','just','first'}
SKIP_PATH=re.compile(r'/(tag|tags|category|author|page|about|contact|search|login|wp-content)/|/guide/|guideline|pitching|/wikis?/|cheats|walkthrough|tier-list|opinion|how-to|best-|ultimate|/deals?/|giveaway|redeem',re.I)
def toks(t): return {w for w in re.findall(r'[a-z0-9]{3,}',t.lower()) if w not in STOP}
def related_links(scope_html,page_url,title,max_n=3,min_shared=3):
    """Same-host, article-like links inside the article that share >= min_shared (default 3) meaningful, non-generic words with the title/URL of THIS article (so a 'Baca juga' link
    to another game never qualifies). Ranked by overlap, never the page itself. Returns absolute URLs."""
    host=urllib.parse.urlparse(page_url).netloc.replace('www.',''); mine=toks(title+' '+urllib.parse.urlparse(page_url).path.replace('-',' '))
    selfp=urllib.parse.urlparse(page_url).path.rstrip('/'); out=[]
    for m in re.finditer(r'<a\b[^>]*\bhref="([^"#]+)"[^>]*>(.*?)</a>',scope_html,flags=re.S|re.I):
        u=urllib.parse.urljoin(page_url,html.unescape(m.group(1)).strip()); p=urllib.parse.urlparse(u)
        if p.scheme not in ('http','https') or p.netloc.replace('www.','')!=host or p.query: continue
        path=p.path.rstrip('/'); slug=path.split('/')[-1]
        if path==selfp or slug.count('-')<3 or SKIP_PATH.search(path): continue
        shared=len(toks(slug.replace('-',' '))&mine)
        if shared>=min_shared and u not in [x[1] for x in out]: out.append((shared,u))
    out.sort(key=lambda x:-x[0]); return [u for _,u in out[:max_n]]

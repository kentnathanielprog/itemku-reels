"""Image selection rules for a story (pure functions, unit-tested in tests/image_rules_test.py).
Policy (owner decision 2026-11-21):
- ONE real image is enough: a story is never rejected just because the article has a single usable picture.
- Prefer MORE than one image so the video is not boring: article images >= PRIMARY_W px first (article order), then fallback images
  FALLBACK_W..PRIMARY_W-1 px (widest first), then related-page / franchise-pool images, up to TARGET.
- A card that is only text with no real picture is still rejected - that is decided by auto/visual.py (layer 1 hint) + the vision check, not here."""
PRIMARY_W=1000; FALLBACK_W=800; TARGET=3
def select(art_images,min_images=1,target=TARGET):
    """art_images: [{'file': rel_path, 'w': int, 'src': 'article'|'related'|None}] in article order -> list of rel paths (may be shorter than target, may be 1).
    Returns [] only when NO image reaches FALLBACK_W (then the story has no real picture usable at 1080 px)."""
    ok=lambda i:i.get('w',0)>=PRIMARY_W
    primary=[i for i in art_images if ok(i) and i.get('src')!='related']
    fallback=sorted([i for i in art_images if FALLBACK_W<=i.get('w',0)<PRIMARY_W and i.get('src')!='related'],key=lambda i:-i['w'])
    related=sorted([i for i in art_images if i.get('src')=='related' and i.get('w',0)>=FALLBACK_W],key=lambda i:-i['w'])
    out=[]
    for i in primary+fallback+related:
        if i['file'] not in out: out.append(i['file'])
    out=out[:max(target,1)] if len(out)>target else out
    return out if len(out)>=min_images else []

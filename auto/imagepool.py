#!/usr/bin/env python3
"""Extra on-topic images for franchise-level stories (gta, pokemon, ...). NOT for game-/event-specific topics (roblox, mlbb) to avoid showing the wrong game.
usage: python3 imagepool.py <entity> [n=3]  -> prints relative paths of previously fetched images tagged with that entity"""
import json,sys,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; cfg=json.loads((ROOT/'config.json').read_text())
def pool(entity,n=3,exclude=()):
    if entity not in cfg.get('imagepool_entities',[]): return []
    out=[]
    for f in sorted((BASE/'out').glob('*/article.json'),key=lambda p:-p.stat().st_mtime):
        a=json.loads(f.read_text()); hay=(a.get('title','')+' '+a.get('url','')).lower()
        if entity=='gta' and not re.search(r'gta|grand.theft',hay): continue
        if entity!='gta' and entity not in hay: continue
        for im in a.get('images',[]):
            rel=str(pathlib.Path(im['file']).relative_to(BASE))
            if rel not in out and rel not in exclude and im['w']>=1000: out.append(rel)
    return out[:n]
if __name__=='__main__': print('\n'.join(pool(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 3)))

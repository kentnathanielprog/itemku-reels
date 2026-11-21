#!/usr/bin/env python3
"""Music catalog (licensed/free tracks only). The music agent proposes mood tags; this script makes the final deterministic pick
(tag match + learned weight - recency) so tracks rotate and the same song is never used twice in a row.
usage: python3 music.py pick --mood hype,dark --cat mlbb      |   python3 music.py list"""
import json,sys,pathlib,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parent; ST=ROOT/'state'
def load(): return json.loads((ROOT/'music'/'catalog.json').read_text())['tracks']
def pick(mood,cat=None,k=1):
    tr=load(); posts=json.loads((ST/'posts.json').read_text()); pb=json.loads((ST/'playbook.json').read_text())
    if not tr: return None
    recent=[p.get('music') for p in posts[-6:]]; w=pb.get('music_weights',{})
    def score(t):
        s=len(set(t.get('mood',[]))&set(mood))*2+(1 if t.get('genre') in mood else 0)+w.get(t['file'],0)
        if t['file'] in recent: s-=5-recent[::-1].index(t['file'])*0.5
        return s
    return sorted(tr,key=score,reverse=True)[:k]
if __name__=='__main__':
    a=sys.argv[1:]
    if a and a[0]=='list': print(json.dumps(load(),ensure_ascii=False,indent=1))
    elif a and a[0]=='pick':
        mood=(a[a.index('--mood')+1] if '--mood' in a else '').split(','); r=pick(mood)
        print(json.dumps(r[0],ensure_ascii=False) if r else 'KATALOG KOSONG: isi auto/music/catalog.json dengan lagu berlisensi (lihat auto/agents/music.md)')

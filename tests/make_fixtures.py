#!/usr/bin/env python3
"""Builds a fully synthetic story (no network, no API): fake article + 2 generated images + canned writer/QC/vision answers."""
import json,pathlib,random
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
B=pathlib.Path(__file__).resolve().parent.parent; D=B/'out'/'test-story'; (D/'imgs').mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(7)
def art(path,seed,hues,rev=False):
    r=np.random.default_rng(seed); w,h=1280,720
    base=np.zeros((h,w,3),float)
    for c,hu in enumerate(hues): base[...,c]=(np.linspace(hu,40,w) if rev else np.linspace(40,hu,w))[None,:]+(np.linspace(60,0,h) if rev else np.linspace(0,60,h))[:,None]*(c+1)/3
    im=Image.fromarray(np.clip(base+r.normal(0,28,(h,w,3)),0,255).astype('uint8')); d=ImageDraw.Draw(im)
    if rev:
        for k in range(6): d.rectangle([k*220,60+k*90,k*220+200,60+k*90+160],fill=(235,235,235) if k%2 else (15,15,15))
    for _ in range(40): x,y=r.integers(0,w),r.integers(0,h); s=r.integers(30,160); d.ellipse([x,y,x+s,y+s],outline=tuple(int(v) for v in r.integers(40,255,3)),width=int(r.integers(2,7)))
    im.save(path,quality=92)
art(D/'imgs'/'img1.jpg',1,(220,120,90)); art(D/'imgs'/'img2.jpg',2,(90,160,230),rev=True)
P=["Nova Games merilis update besar bernama Starlight untuk game Nova Arena pada hari Jumat.",
   "Dalam minggu pertama, 2,5 juta pemain mencoba mode baru bernama Arena Bintang, menurut data resmi studio.",
   "Update ini membawa 3 map baru: Pantai Senja, Kota Neon, dan Hutan Kristal.",
   "Studio juga menyebut rata-rata sesi bermain naik dibanding bulan lalu."]
txt=' '.join(P)
art_json={"url":"https://example.invalid/nova-arena-starlight","title":"Nova Arena rilis update Starlight, 2,5 juta pemain coba di minggu pertama","date":"2026-11-20T10:00:00+00:00","site":"TestSite","desc":P[1],
  "summary":txt[:900],"fulltext":"Menu Beranda Berita "+txt+" Baca juga artikel lain","clean":txt,
  "images":[{"file":str(D/'imgs'/f'img{i}.jpg'),"w":1280,"h":720,"url":f"https://example.invalid/img{i}.jpg"} for i in (1,2)]}
(D/'article.json').write_text(json.dumps(art_json,ensure_ascii=False,indent=1))
M=B/'tests'/'fixtures'/'mock'; M.mkdir(parents=True,exist_ok=True)
cap=lambda t,i:{"text":t,"img":i}
sid="test-story"
writer={"stories":[{"id":sid,"hook":cap("Update baru Nova Arena\nbikin heboh minggu ini!\nTunggu angkanya",[0,1]),
  "message":[cap("Nova Games rilis update\nStarlight buat Nova Arena\nhari Jumat",[1]),cap("Ada 3 map baru: Pantai\nSenja, Kota Neon, dan\nHutan Kristal",[0,1])],
  "gong":cap("[[2,5]] juta pemain nyoba\nmode Arena Bintang\ndi minggu pertama",[1,0]),"credit":"Nova Games","hashtags":["NovaArena","gaming","itemku","update"],
  "topic":"Nova Arena Starlight update draws 2.5 million players","hook_type":"number",
  "caption_text":"Nova Arena baru rilis update Starlight dan 2,5 juta pemain langsung nyoba mode barunya. Kamu udah coba belum? Cerita di komentar ya!"}]}
qc={"reports":[{"id":sid,"verdict":"PASS","issues":[],"fixes":[],"claims":[
  {"text":"Nova Games merilis update Starlight untuk Nova Arena hari Jumat","evidence":P[0],"calc_expr":"","count_items":[],"count_value":0},
  {"text":"2,5 juta pemain mencoba mode Arena Bintang di minggu pertama","evidence":P[1],"calc_expr":"","count_items":[],"count_value":0},
  {"text":"Ada 3 map baru","evidence":P[2],"calc_expr":"","count_items":["Pantai Senja","Kota Neon","Hutan Kristal"],"count_value":3}]}]}
vis={"reports":[{"id":sid,"images":[{"index":i,"verdict":"ok","problem":"none","note":""} for i in (0,1)]}]}
for n,d in (('writer_1',writer),('qc_1',qc),('visual_1',vis)): (M/f'{n}.json').write_text(json.dumps(d,ensure_ascii=False,indent=1))
(B/'tests'/'fixtures'/'picks.json').write_text(json.dumps([{"id":sid,"cat":"general","entity":None,"article_dir":"out/test-story","images":["out/test-story/imgs/img1.jpg","out/test-story/imgs/img2.jpg"]}]))
print('fixtures ok')

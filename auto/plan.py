#!/usr/bin/env python3
"""Day plan: slot -> category -> experiment variant (20% of posts run the experiment). usage: python3 plan.py  -> prints JSON"""
import json,random,pathlib,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parent; cfg=json.loads((ROOT/'config.json').read_text()); pb=json.loads((ROOT/'state'/'playbook.json').read_text())
rng=random.Random(dt.date.today().isoformat()); plan=[]
for s in cfg['slots']:
    exp=None
    if rng.random()<pb['experiments']['share'] and pb['experiments']['active']:
        e=pb['experiments']['active'][0]; exp={'id':e['id'],'variant':rng.choice(list(e['variants']))}
    plan.append({'slot':s['time'],'experiment':exp})   # category comes from scout (today.json), not from the slot
print(json.dumps(plan,ensure_ascii=False,indent=1))

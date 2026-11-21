#!/usr/bin/env python3
"""Put a QC-passed, rendered story into state/queue.json. Refuses to enqueue unless: QC verdict PASS + evidence verified + video QA files exist.
usage: python3 enqueue.py <story.json> <slot HH:MM> [--day YYYY-MM-DD]   (slot time is Asia/Jakarta)"""
import json,sys,subprocess,pathlib,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parent; BASE=ROOT.parent; ST=ROOT/'state'
def enqueue(story_path,slot,day=None):
    sp=pathlib.Path(story_path); s=json.loads(sp.read_text()); name=sp.stem
    qcp=BASE/'out'/name/'qc_report.json'; art=BASE/'out'/name/'article.json'
    if not qcp.exists(): raise SystemExit('ditolak: belum ada qc_report.json')
    if json.loads(qcp.read_text()).get('verdict')!='PASS': raise SystemExit('ditolak: QC bukan PASS')
    r=subprocess.run(['python3',str(ROOT/'verify_evidence.py'),str(sp),str(qcp),str(art)],capture_output=True,text=True)
    if r.returncode: raise SystemExit('ditolak: bukti tidak terverifikasi\n'+r.stdout)
    vid=pathlib.Path('out')/s['out']/'short.mp4'
    if not (BASE/vid).exists(): raise SystemExit('ditolak: video belum dirender')
    hh,mm=map(int,slot.split(':')); wib=dt.timezone(dt.timedelta(hours=7))
    d=dt.date.fromisoformat(day) if day else dt.datetime.now(wib).date()
    nb=dt.datetime(d.year,d.month,d.day,hh,mm,tzinfo=wib).astimezone(dt.timezone.utc)
    tags=' '.join('#'+h.lstrip('#') for h in s.get('hashtags',[]))
    cap=f"{s['caption_text']}\n\nSumber: {s['source']}"+(f" | Gambar: {s['credit']}" if s.get('credit') else '')+f"\n\n{tags}"
    q=json.loads((ST/'queue.json').read_text()); q=[x for x in q if x['id']!=name]
    q.append({'id':name,'status':'ready','not_before':nb.isoformat(),'video':str(vid),'caption':cap,'cat':s.get('cat'),'topic':s.get('topic'),
      'source_url':json.loads(art.read_text()).get('url'),'hook_type':s.get('hook_type'),'music':s.get('music'),'experiment':s.get('experiment'),
      'n_images':len(s.get('images',[])),'posted_slot':slot})
    (ST/'queue.json').write_text(json.dumps(q,ensure_ascii=False,indent=1)); print(f'antrean: {name} -> {slot} WIB ({nb.isoformat()})')
if __name__=='__main__':
    a=sys.argv[1:]; enqueue(a[0],a[1],a[a.index('--day')+1] if '--day' in a else None)

#!/usr/bin/env python3
"""Learning analyzer (deterministic, offline): reads data/performance.jsonl and prints a markdown comparison for the agent.
usage: python3 learning/analyze.py [--file data/performance.jsonl] [--json]
Uses the LATEST snapshot per Reel, only Reels >= min_age_hours old. Dimensions: category(topic), hook_type, format(n_images + music), duration bucket, hour bucket (WIB).
A group with n < per_group is printed as 'sampel kurang' and gets no verdict. Verdicts need n >= per_group_for_change on both sides and a median-reach gap >= min_effect."""
import json,sys,statistics as S,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent; POL=json.loads((ROOT/'learning'/'policy.json').read_text())
F=pathlib.Path(sys.argv[sys.argv.index('--file')+1]) if '--file' in sys.argv else ROOT/'data'/'performance.jsonl'
N1=POL['min_sample']['per_group']; N2=POL['min_sample']['per_group_for_change']; GAP=POL['min_effect']['median_reach_gap_pct']; MINAGE=POL['min_sample']['min_age_hours']
def load():
    last={}
    if F.exists():
        for l in F.read_text().splitlines():
            if l.strip():
                try: r=json.loads(l)
                except Exception: continue
                if r.get('reach') is None or r.get('age_h',0)<MINAGE: continue
                if r['media_id'] not in last or r['at']>last[r['media_id']]['at']: last[r['media_id']]=r
    return list(last.values())
def dur_b(r):
    d=r.get('duration_s'); return None if d is None else ('<20s' if d<20 else '20-30s' if d<30 else '30s+')
def hour_b(r):
    h=r['hour_wib']; return 'pagi 05-10' if 5<=h<11 else 'siang 11-14' if 11<=h<15 else 'sore 15-19' if 15<=h<20 else 'malam 20-04'
DIMS={'topik (cat)':lambda r:r.get('cat'),'hook_type':lambda r:r.get('hook_type'),
      'format (gambar/musik)':lambda r:None if r.get('n_images') is None else f"{'1' if r['n_images']<=1 else '2+'} gambar, {'musik' if r.get('music') else 'senyap'}",
      'durasi':dur_b,'jam posting (WIB)':hour_b}
def main():
    rows=load(); out=[]; verdicts=[]
    out.append(f'# Analisis performa | Reel dianalisis: {len(rows)} (umur >= {MINAGE} jam, snapshot terbaru per Reel)')
    if len(rows)<POL['min_sample']['min_reels_total']: out.append(f"\n**TOTAL SAMPEL KURANG**: {len(rows)} < {POL['min_sample']['min_reels_total']}. Hanya kumpulkan data; jangan ubah konfigurasi.")
    for name,fn in DIMS.items():
        g={}
        for r in rows:
            k=fn(r)
            if k is not None: g.setdefault(k,[]).append(r)
        out.append(f'\n## {name}\n| grup | n | median reach | median plays | status |\n|---|---|---|---|---|')
        stat=[]
        for k,v in sorted(g.items(),key=lambda x:-len(x[1])):
            mr=S.median(x['reach'] for x in v); mp=S.median(x['plays'] for x in v); ok1=len(v)>=N1; ok2=len(v)>=N2
            out.append(f"| {k} | {len(v)} | {mr:.0f} | {mp:.0f} | {'cukup' if ok2 else ('minimal (belum cukup untuk ubah config)' if ok1 else 'sampel kurang')} |")
            if ok2: stat.append((k,mr,len(v)))
        if len(g)<2: out.append(f'_Hanya {len(g)} grup: tidak ada pembanding._')
        if len(stat)>=2:
            stat.sort(key=lambda x:-x[1]); b,w=stat[0],stat[-1]; gap=(b[1]-w[1])/max(w[1],1)*100
            v={'dimension':name,'best':b[0],'worst':w[0],'best_median_reach':b[1],'worst_median_reach':w[1],'n_best':b[2],'n_worst':w[2],'gap_pct':round(gap,1),'passes_effect_threshold':gap>=GAP}
            verdicts.append(v); out.append(f"_Kandidat: {b[0]} vs {w[0]}: selisih median reach {gap:.0f}% -> {'LOLOS' if gap>=GAP else 'di bawah ambang'} (ambang {GAP}%)._")
        elif len(g)>=2: out.append(f'_Tidak ada dua grup dengan n >= {N2}: belum boleh membuat kesimpulan atau mengubah config._')
    hrs={r['hour_wib'] for r in rows}
    if rows and len(hrs)<=2: out.append(f"\n**Catatan perancu**: semua Reel terbit di {len(hrs)} jam berbeda saja ({sorted(hrs)} WIB). Perbandingan jam posting belum bermakna.")
    if '--json' in sys.argv: print(json.dumps({'n':len(rows),'verdicts':verdicts},ensure_ascii=False,indent=1))
    else: print('\n'.join(out))
main()

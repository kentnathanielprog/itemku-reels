#!/usr/bin/env python3
"""Offline tests for the bundled background music (assets/audio + auto/music/catalog.json). No network. usage: python3 tests/audio_test.py"""
import sys,os,re,json,pathlib,tempfile,subprocess
REPO=pathlib.Path(__file__).resolve().parent.parent; os.chdir(REPO); sys.path.insert(0,str(REPO/'auto'))
import music
RES=[]
def case(name):
    def deco(fn):
        try: fn(); RES.append((name,True,''))
        except AssertionError as e: RES.append((name,False,str(e)[:300]))
        except Exception as e: RES.append((name,False,f'{type(e).__name__}: {e}'[:300]))
        return fn
    return deco
TR=music.load()
def probe(f): return json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,sample_rate,channels,duration','-of','json',f],capture_output=True,text=True).stdout)['streams'][0]
def lufs(f):
    o=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',f,'-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr; return float(re.findall(r'I:\s+(-?[\d.]+) LUFS',o)[-1])
def mean_db(f):
    o=subprocess.run(['ffmpeg','-hide_banner','-i',f,'-af','volumedetect','-f','null','-'],capture_output=True,text=True).stderr; return float(re.search(r'mean_volume: (-?[\d.]+)',o).group(1))
@case('catalog has 3-5+ tracks, every file exists')
def _(): assert len(TR)>=3,len(TR); assert all((REPO/t['file']).exists() for t in TR),[t['file'] for t in TR if not (REPO/t['file']).exists()]
@case('every track: AAC, 44.1 kHz, stereo, 45-65 s')
def _():
    for t in TR:
        p=probe(t['file']); assert (p['codec_name'],p['sample_rate'],p['channels'])==('aac','44100',2),(t['file'],p); assert 45<=float(p['duration'])<=65,(t['file'],p['duration'])
@case('every track is audible (mean_volume > -50 dB) and about -18 LUFS (-19.5..-16.5)')
def _():
    for t in TR: m=mean_db(t['file']); l=lufs(t['file']); assert m>-50,(t['file'],m); assert -19.5<=l<=-16.5,(t['file'],l)
@case('licensing: every track has license + source in the catalog, is listed in assets/audio/LICENSES.md, and is original (no third-party attribution)')
def _():
    doc=(REPO/'assets/audio/LICENSES.md').read_text()
    for t in TR:
        assert t['license'] in ('CC0-1.0','public-domain') and t.get('source_url'),t; assert pathlib.Path(t['file']).name in doc,t['file']; assert not t.get('attribution'),t
    assert 'No samples' in doc.replace('**No samples','No samples') or 'No samples' in doc
@case('every category mood maps to at least one track (mlbb, roblox, gta, general)')
def _():
    cfg=json.load(open('auto/config.json'))['music_mood']
    for cat,mood in cfg.items(): assert any(set(t['mood'])&set(mood) for t in TR),(cat,mood)
@case('deterministic rotation: 12 picks in a row never repeat the previous track and use >= 4 different tracks')
def _():
    tmp=pathlib.Path(tempfile.mkdtemp(prefix='musictest_')); (tmp/'posts.json').write_text('[]'); (tmp/'playbook.json').write_text('{}'); music.ST=tmp
    posts=[]; seq=[]
    for i in range(12):
        t=music.pick([])[0]['file']; seq.append(t); posts.append({'music':t}); (tmp/'posts.json').write_text(json.dumps(posts))
    assert all(a!=b for a,b in zip(seq,seq[1:])),seq; assert len(set(seq))>=4,seq
    music.ST=pathlib.Path(REPO/'auto'/'state')
    seq2=[]; (tmp/'posts.json').write_text('[]'); music.ST=tmp; posts=[]
    for i in range(12):
        t=music.pick([])[0]['file']; seq2.append(t); posts.append({'music':t}); (tmp/'posts.json').write_text(json.dumps(posts))
    assert seq==seq2,'not deterministic'
@case('mood routing: mlbb -> pulse-arena, gta -> dark-alley (first pick, empty history)')
def _():
    tmp=pathlib.Path(tempfile.mkdtemp(prefix='musictest_')); (tmp/'posts.json').write_text('[]'); (tmp/'playbook.json').write_text('{}'); music.ST=tmp
    assert music.pick(['hype','edm'])[0]['file'].endswith('pulse-arena.m4a'); assert music.pick(['dark','trap'])[0]['file'].endswith('dark-alley.m4a')
if __name__=='__main__':
    bad=0
    for n,ok,msg in RES: print(('  ✓ ' if ok else '  ✗ ')+n+('' if ok else f'\n      {msg}')); bad+=0 if ok else 1
    print(f'passed={len(RES)-bad} failed={bad}'); sys.exit(1 if bad else 0)

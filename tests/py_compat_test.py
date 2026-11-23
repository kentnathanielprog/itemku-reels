#!/usr/bin/env python3
"""The cloud routines run Python 3.11; the dev sandbox runs 3.13. Syntax that only exists on >= 3.12 (PEP 701 f-strings) must never reach main again.
Offline. usage: python3 tests/py_compat_test.py"""
import sys,os,io,shutil,tokenize,pathlib,subprocess,tempfile
R=pathlib.Path(__file__).resolve().parent.parent; os.chdir(R)
RES=[]
def case(name):
    def deco(fn):
        try:
            r=fn(); RES.append((name,True,r or ''))
        except AssertionError as e: RES.append((name,False,str(e)[:500]))
        except Exception as e: RES.append((name,False,f'{type(e).__name__}: {e}'[:500]))
        return fn
    return deco
def scan(src):
    """>= 3.12 only: f-string constructs that are a SyntaxError on 3.11 (same quote reused inside {...}, backslash or '#' inside {...})"""
    out=[]; stack=[]; FS=getattr(tokenize,'FSTRING_START',-1); FE=getattr(tokenize,'FSTRING_END',-1)
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type==FS: stack.append([t.string.lstrip('rbfuRBFU')[0],0])
        elif t.type==FE and stack: stack.pop()
        elif stack and t.type==tokenize.OP and t.string=='{': stack[-1][1]+=1
        elif stack and t.type==tokenize.OP and t.string=='}': stack[-1][1]=max(0,stack[-1][1]-1)
        elif stack and stack[-1][1]>0:
            if t.type==tokenize.STRING and t.string.lstrip('rbfuRBFU')[:1]==stack[-1][0]: out.append((t.start[0],'quote reused inside f-string'))
    return out
tracked=[f for f in subprocess.run(['git','ls-files','*.py'],capture_output=True,text=True).stdout.split() if (R/f).exists()]
NEW=sys.version_info>=(3,12)
@case('scanner self-check: it flags the exact pattern that broke production (needs Python >= 3.12 to run)')
def _():
    if not NEW: return 'skipped (this interpreter itself rejects such code)'
    bad="print(', '.join(f\"{d['k']}={s[\"file\"]}\" for s in x))\n"; assert scan(bad),'scanner missed the bad pattern'; assert not scan("print(', '.join(f\"{s['file']}\" for s in x))\n"),'false positive'
@case('no tracked .py file uses 3.12-only f-string syntax (token scan)')
def _():
    if not NEW: return 'skipped (older interpreter: ast.parse in the next case covers it)'
    hits=[(f,l,m) for f in tracked for l,m in scan((R/f).read_text(encoding='utf-8'))]; assert not hits,hits
@case('every tracked .py compiles under a real Python 3.11 (the cloud interpreter)')
def _():
    py=shutil.which('python3.11') or ('/usr/bin/python3.11' if os.path.exists('/usr/bin/python3.11') else None)
    if not py: return 'skipped (python3.11 not installed here)'
    bad=[]
    for f in tracked:
        p=subprocess.run([py,'-c','import ast,sys;ast.parse(open(sys.argv[1],encoding="utf-8").read(),sys.argv[1])',f],capture_output=True,text=True)
        if p.returncode: bad.append(f+': '+p.stderr.strip().splitlines()[-1][:80])
    assert not bad,bad
@case('scripts/syntax_check.py passes on the repo')
def _():
    p=subprocess.run([sys.executable,'scripts/syntax_check.py'],capture_output=True,text=True); assert p.returncode==0 and 'SYNTAX: ok' in p.stdout,(p.stdout,p.stderr)
@case('scripts/syntax_check.py fails loudly (exit 1, file:line) on a file the interpreter cannot compile')
def _():
    t=pathlib.Path(tempfile.mkdtemp(prefix='syn_')); (t/'scripts').mkdir(); (t/'auto').mkdir(); shutil.copy('scripts/syntax_check.py',t/'scripts'/'syntax_check.py'); (t/'auto'/'ok.py').write_text('x=1\n'); (t/'auto'/'bad.py').write_text('def (:\n  pass\n')
    p=subprocess.run([sys.executable,str(t/'scripts'/'syntax_check.py')],capture_output=True,text=True); assert p.returncode==1 and 'auto/bad.py:1' in p.stdout and 'SYNTAX GAGAL' in p.stdout,(p.returncode,p.stdout)
@case('session_run.sh runs the syntax check before anything else and aborts with exit 6')
def _():
    s=open('scripts/session_run.sh').read(); assert 'syntax_check.py' in s and 'exit 6' in s and s.index('syntax_check.py')<s.index('case "$MODE" in'),'wiring'
if __name__=='__main__':
    bad=0
    for n,ok,msg in RES: print(('  ✓ ' if ok else '  ✗ ')+n+(f'  [{msg}]' if ok and msg else '')+('' if ok else f'\n      {msg}')); bad+=0 if ok else 1
    print(f'passed={len(RES)-bad} failed={bad}'); sys.exit(1 if bad else 0)

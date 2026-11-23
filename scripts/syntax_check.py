#!/usr/bin/env python3
"""Fail fast: compile every runtime .py with THE interpreter that is about to run the pipeline (called by scripts/session_run.sh).
The cloud routines run an older Python than the dev sandbox (3.11 vs 3.13); on 2026-11-22/23 one 3.12-only f-string silently killed every produce run.
exit 0 = all files compile; exit 1 = lists file:line and the error."""
import sys,ast,pathlib
R=pathlib.Path(__file__).resolve().parent.parent; bad=[]; n=0
for pat in ('auto/*.py','short/*.py','learning/*.py','scripts/*.py'):
    for f in sorted(R.glob(pat)):
        n+=1
        try: ast.parse(f.read_text(encoding='utf-8'),str(f))
        except SyntaxError as e: bad.append(f'{f.relative_to(R)}:{e.lineno}: {e.msg}')
v=sys.version.split()[0]
if bad: print(f'SYNTAX GAGAL di Python {v}:'); [print('  ',b) for b in bad]; sys.exit(1)
print(f'SYNTAX: ok (Python {v}, {n} berkas)')

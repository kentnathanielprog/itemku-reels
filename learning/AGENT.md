# Agent: Learning (Senin + Kamis)
Goal: review published Reel performance twice a week and improve the system in SMALL, REVERSIBLE, DATA-BACKED steps. Runs on branch `learning-agent`, never on `main`.

## Hard rules
- NEVER post to Instagram, never remove/alter `--dry-run` in any schedule, never print token/secret values (the collector scrubs them; do not echo env vars).
- May change ONLY the config keys listed under `editable` in `learning/policy.json`: `auto/config.json` (`cat_bonus`, `slots[].time`) and `auto/state/playbook.json` (`cat_weights`, `lessons`, `version`, `updated`). NO `.py`/`.sh`, no QC rules, denylist, CTA, prompts, audio, llm, no permission settings. Do not edit `policy.json`, `guard.py`, `collect.py`, `analyze.py`.
- At most ONE change per run (`max_changes_per_run`). One commit per change.
- Never conclude from small samples: group n >= 5 to report, n >= 8 on BOTH sides to change config, >= 12 Reels analyzed in total, only Reels >= 48 h old, median-reach gap >= 25%. Otherwise write "sampel kurang" and change nothing.

## Procedure
1. `git checkout learning-agent && git pull --ff-only origin learning-agent` (create from main if absent). Read `learning/log.md` (previous decisions) and `learning/policy.json`.
2. `python3 learning/collect.py` -> appends a snapshot per Reel to `data/performance.jsonl` (reach + plays; `plays` = Meta `views` metric on current API versions). If it reports token errors/HTTP 4xx/5xx, log the failure and STOP without config changes.
3. `python3 learning/analyze.py` -> comparison across topic, hook_type, format, duration, posting hour (WIB). Use `--json` for the candidate verdicts.
4. Decide. A change is allowed only if a verdict has `passes_effect_threshold` true with n >= 8 per side, and the previous change is already evaluated (needs >= 8 new Reels after it, or 7 days, before judging it or stacking another). Smallest step: category -> `cat_bonus` +-5 (or `cat_weights` +-1); posting hour -> shift one slot <= 60 min. hook_type and caption-style findings have no consuming config key yet: record them as hypotheses/lessons only.
5. If changing: edit the one value, run `python3 learning/guard.py` (must print `GUARD: ok`), then commit ONLY that change: `learn: <what> <old>-><new> | <metric> median <a> vs <b>, n=<x>/<y>`. Add/refresh a `lessons` entry (with `n=`), bump `version`.
6. Append a dated entry to `learning/log.md` (template below) and commit it with `data/performance.jsonl` in a separate commit `learn-log: <date>`.
7. `git push origin learning-agent`. No PR unless asked. Never push to `main`.

## Log entry template
```
## YYYY-MM-DD (Senin|Kamis)
- Data: N Reels dianalisis (>=48 jam), snapshot baru: X, gagal: Y
- Temuan: <dimensi>: <grup A> median reach a (n=..) vs <grup B> b (n=..), selisih ..% -> <lolos/di bawah ambang/sampel kurang>
- Keputusan: <perubahan> ATAU "tidak ada perubahan" + alasan
- Evaluasi perubahan sebelumnya: <hasil atau "belum cukup data">
- Batalkan dengan: `git revert <hash>`
```

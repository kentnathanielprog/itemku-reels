# itemku Reels automation

Daily pipeline that turns fresh gaming news into three 15-second Instagram Reels (1080x1920, official itemku template, casual Indonesian copy), with automatic QC, fact verification and a kill switch.

```
scout (scripts) -> fetch article+images -> WRITER (1 API call, all stories) -> lint
   -> QC (1 API call, independent, verbatim evidence) + verify_evidence.py (deterministic)
   -> <= 1 batched revision -> VISION check (1 call, thumbnails) -> render + QA -> queue
publish.py (cron x3, no LLM) -> Instagram Graph API -> insights.py -> (weekly learner, planned)
```

**Tutorial server GitHub (tanpa laptop):** `TUTORIAL_GITHUB.md`.

**Quick start** (needs Python 3.10+, Node 18+): `bash scripts/setup.sh && bash tests/offline_test.sh`, then read `SETUP.md` (Meta developer app, secrets, scheduling) and `CLAUDE.md` (rules for working in this repo with Claude Code).

**Safety design:** no post without QC PASS and a verified quote for every claim/number; topic cooldown and dedupe; denylist (leaks, adult/sensor, gambling, politics, layoffs, other stores' deals); `auto/STOP` kill switch; dry-run never touches state. The Graph API cannot delete a post, so everything is checked before it goes out.

**Cost:** API only, about US$0.1-0.4 per day depending on models and thinking (measure with `python3 scripts/status.py`; the usage log is `auto/state/llm_usage.jsonl`). Running the daily jobs from cron/GitHub Actions uses no Claude Code session tokens.

Status and open work: see the last section of `CLAUDE.md`.

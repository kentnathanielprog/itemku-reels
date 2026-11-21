# Daily run (Claude cloud scheduled tasks, Asia/Jakarta)

## Task 1 - Producer (about 05:27). ONE command, no sub-agents:
    python3 auto/produce.py
What it does (all stateless API calls; only article text + draft go into each call):
1. scout (scripts): fresh, safe, non-duplicate candidates from all categories -> best 3 with diversity caps (max 2 per category, 1 per entity).
2. fetch article + images (scripts); franchise topics (gta, pokemon...) get extra on-topic images from `imagepool`.
3. **ONE writer call for all stories** (`prompts/writer.md`, schema-enforced JSON).
4. lint (script) -> stories with lint errors go straight to revision (no QC call wasted).
5. **ONE QC call for all stories** (`prompts/qc.md`, independent, verbatim evidence) + `verify_evidence.py` (deterministic: quotes must exist in the article; numbers must be inside quotes). Final = QC PASS **and** verifier OK.
6. failed stories: at most `max_rewrite_rounds` (default 1, hard cap 2) batched revision (writer call + QC call for the failed ones only), then dropped. Optional replacement batch (`max_replacements`) from spare candidates.
6b. **visual check**: layer 1 (free) at load time drops certainly-bad images (blurry/blank/tiny/duplicate) and marks 'text-card suspects'; layer 2 = ONE batched vision call (512px thumbnails, ~200 tokens each) after QC pass: drops text cards / ads / unrelated / off-topic / graphic images, remaps every caption's img list; a story with no image left is dropped. Skipped with a warning when the API is unavailable. `--no-vision` disables it.
7. render (make_video: lint + render + QA incl. blank-frame check) -> `enqueue.py` (refuses without QC PASS) -> `state/queue.json`.
8. cost log: `state/llm_usage.jsonl`, run summary: `state/runlog/<day>.json`.
Env: ANTHROPIC_API_KEY (environment variable, entered by the owner). `--dry-run` prints the estimated cost without calling the API. Commit + push `auto/state`, stories, logs afterwards (container is ephemeral).
Models/effort are in `config.json` -> `llm` (default claude-opus-5-5 for both roles; claude-sonnet-5-5 is a cheaper option for the writer).

## Tasks 2-4 - Publisher (about 07:33, 12:07, 17:03). Minimal prompt, no judgment:
"cd the repo, run `python3 auto/publish.py`, then `python3 auto/insights.py`, commit+push `auto/state`, report the permalink or the error."
(publish.py always takes the oldest due item, so a missed run is caught by the next one.)

## Task 5 - Learner (weekly). One batched API call over `metrics.json`/`posts.json` -> updates `playbook.json` (see `agents/learner.md`).

## Legacy
`auto/agents/copywriter.md` and `qc.md` are the long-form rules (kept for reference / manual sub-agent use). The API prompts in `auto/prompts/` are the compact versions actually used.

## Token saving notes (see also the review in the chat)
- LLM input uses `article.json -> clean` (paragraphs only) when substantial, else full text: ~33% fewer article tokens on average.
- Daily ops (`produce.py`, `publish.py`) need NO Claude session: run them from cron / GitHub Actions to spend zero subscription tokens; use Claude cloud scheduled tasks only for supervised/rare jobs.
- Measure real usage first: `state/llm_usage.jsonl` (input/output/cache tokens + USD per call).

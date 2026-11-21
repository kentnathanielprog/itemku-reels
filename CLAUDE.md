# itemku Reels automation - project guide for Claude Code

Automated pipeline: finds fresh gaming news -> writes casual Indonesian copy -> QC + fact-check -> renders 1080x1920 videos with the official itemku template -> queues -> posts to Instagram Reels (3 per day, WIB morning/noon/afternoon).

## Golden rules (do not break)
1. **Nothing is queued or posted without QC PASS + `verify_evidence.py` OK.** `auto/enqueue.py` refuses otherwise. Never bypass it, never hand-edit `auto/state/queue.json` (only set `status` to `archived`).
2. **Secrets only as environment variables** (`ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`, `IG_USER_ID`, `IG_ACCESS_TOKEN`). Never print, log, commit or ask for them in chat. `.env` is git-ignored and unreadable here.
3. **Kill switch:** `touch auto/STOP` (commit it for CI) or set the repo variable `STOP=1` stops all posting (publish.py checks both). Remove to resume.
4. **After changing pipeline code run `bash tests/offline_test.sh`** (about 40 s, no network, no API key). All checks must pass before you finish.
5. **No unreviewed live posting while testing.** Use `python3 auto/publish.py --dry-run`. A live post cannot be deleted through the Graph API.
6. **Token discipline:** do not open images/videos unless QA warns; use `python3 scripts/status.py`; do not paste article text into chat (scripts print compact summaries); prefer one batched API call per role (already how `produce.py` works).

## Video copy rules (lint + QC enforce them)
- Casual Indonesian (gimana, udah, nggak, banget); no English mixing except names/game terms. Capital letter only at the start of each caption (names/acronyms keep case). Max 3 lines per caption, max 26 characters per line.
- Structure: hook (open loop, "tunggu angkanya") -> 2 message beats -> gong (`[[2,47]]` counts up, or `((keyword))` highlighted; markers must open AND close on the same line) -> CTA.
- Facts only from the article; every number must be inside a verbatim quote; superlatives (rekor/terbesar/...) need a hedge (estimasi/tercatat/menurut/data); no dates on screen; no itemku product/price claims.
- CTA: "Cek Itemku buat\nkebutuhan {MLBB|Roblox|game} kamu" only (never "Follow Itemku untuk berita game": removed, no CTA experiment). "Itemku" same size, capital I only. Source line on the last slide carries no date.
- **Every caption ends with the hashtags and always includes `#itemku`** (added by `enqueue.py` if the writer forgot).
- **Focus:** gaming only, mobile and PC first (MLBB and Roblox get a score bonus via `config.json -> cat_bonus`); no TCG/collectibles/toys/hobby merchandise (denylist); console-only sites are not scouted. Older stories (up to 30 days for MLBB/Roblox) are allowed as an evergreen mix, but the writer must not call them breaking news (`age_days`).
- **Reel cover is always the frame at second 2**: `publish.py` sends `thumb_offset=2000` (ms) on every container (`config.json -> cover_offset_ms`; Meta ignores it only if a `cover_url` is also sent, so never send one). The template shows the hook text by then.
- **Images:** one real image is enough (never reject a story only for having a single picture), but prefer 3 so the video is not boring: article images >= 1000 px, then 800-999 px, then the og:image of topical same-site pages (>= 3 shared non-generic words with the title), then the franchise pool. A card that is only text/UI with no real picture is always rejected (vision check). `shots.py` gives every repeat of the same image a different crop and alternating zoom. Code: `auto/imagesel.py`, `short/imgextra.py`; test: `tests/image_rules_test.py`.
- Video is silent by default (a silent AAC track is added); music only from licensed tracks in `auto/music/catalog.json`.

## Map
- `auto/produce.py` - the daily producer (one command). `scout.py` candidates, `llm.py` API wrapper (+ usage log), `schemas.py`, `prompts/` (writer, qc, visual), `verify_evidence.py`, `visual.py`, `enqueue.py`, `publish.py` (Graph API), `insights.py`, `plan.py`, `music.py`, `imagepool.py`, `config.json`, `state/` (queue, history, posts, metrics, playbook, usage log, runlog).
- `short/` - renderer and tooling: `make_video.py` (new/build/find), `story.py`, `make_short.py` (ffmpeg composition, cached overlays), `render_jobs.js` (one Playwright browser), `overlay_*.html`, `assets/frame_fg.png` (official template), `lint.py`, `qa.py`, `fetch_news.py`, `find_news.py`, `sources.json`, `WORKFLOW.md`.
- `tests/offline_test.sh` + `tests/make_fixtures.py` - synthetic end-to-end test. `scripts/` - `setup.sh`, `status.py`. Scheduling: Claude cloud scheduled tasks (`scripts/session_run.sh`); the GitHub Actions workflows were removed (they only produced error emails).
- `auto/agents/*.md` are long-form role specs (reference); the compact prompts actually sent to the API are in `auto/prompts/`.

## Commands
`python3 auto/produce.py --dry-run` (scout + fetch + cost estimate) | `python3 auto/produce.py` (real run) | `python3 auto/produce.py --picks-file f.json` with `LLM_MOCK_DIR=<dir>` (offline) | `python3 short/make_video.py find|new|build` | `python3 scripts/status.py` | slash commands: `/status`, `/produce-dry`, `/offline-test`, `/new-story`.

## Lessons already learned (do not re-break)
- Heuristics cannot tell a text card from flat illustrated art (measured); only certainly-bad images are auto-dropped, "text-card suspects" go to the vision check.
- Images are filtered by filename relevance (an ad from a "Baca Juga" link once slipped in); QC checks text only, the visual check handles pictures.
- Topic cooldown (24 h per entity), queue-aware dedupe, keyword lists kept specific ("m8" matched a car), perishable "redeem code" lists and other stores' deals are denied.
- `((highlight))` split across lines used to render raw; lint now rejects it. Numbers glued to units (24GB, 120Hz) are parsed by the verifier.
- `publish.py --dry-run` must never write state (it once left a fake "publishing" item).

- Categories: mlbb, roblox, gta, **popular** (other popular games: Free Fire, PUBG, Genshin, Valorant, Pokemon, ... keywords in `short/sources.json`) and general. When mlbb/roblox/gta have no fresh news, popular/general fill the day; replacement rounds (max 4) keep the output at 3 when candidates exist.

## LLM backends (`auto/llm.py`)
- `api` (default): Anthropic API, needs `ANTHROPIC_API_KEY` + balance.
- `claude_cli` (path B, set with `LLM_BACKEND=claude_cli`; `session_run.sh produce` uses it with the session's own login): shells out to `claude -p` with `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`, run once in a terminal) = Claude subscription, no API balance, but it consumes subscription limits (about 4k tokens fixed overhead per call; 3 calls/day). Runs in a clean temp dir, tools off (Read only for vision). Probed locally with haiku (JSON + vision OK); not yet proven inside GitHub Actions. Check Anthropic's current terms for automated use of subscription tokens.
- Offline test: `bash tests/offline_test.sh` stubs the CLI (no network).

## Music (Instagram Audio API, `auto/ig_audio.py`)
- Official API (docs read 2026-11-21): `GET /ig_audio?audio_type=music` returns trending (no `search_query`) or keyword results; the Reel gets `audio_configuration={audio_id,audio_volume,video_volume}` at container creation. Rights are handled by Instagram (only third-party-authorized tracks are returned).
- Needs Facebook Login / Unified Login (not Instagram Login), IG Business/Creator + connected Facebook Page, `instagram_basic` + `instagram_content_publish`. `publish.py` default host is now `graph.facebook.com`.
- Opt-in: `config.json -> audio.enabled` (false = silent). NOT verified live: Indonesian availability, resumable upload combined with `audio_configuration`, `is_ads_eligible` (brand account: check before boosting a post).

## Status / honest gaps
- **Not yet proven live:** Claude API calls from `llm.py` (structured output + `fallbacks`; falls back to a plain call if rejected), vision call, Meta Graph publishing + Insights field names, (GitHub Actions workflows removed).
- **Not built yet:** weekly learner (`auto/learn.py`; spec in `auto/agents/learner.md`, `playbook.json` already exists), licensed music catalog (empty), visual check of the final rendered video beyond blank-frame detection.
- **Open decisions:** model per role (`config.json -> llm`, default claude-opus-5-5; claude-sonnet-5-5 / claude-haiku-5-5 are cheaper), run schedule outside a Claude session (recommended) vs Claude cloud scheduled tasks, topic denylist wording, category weights vs general news.

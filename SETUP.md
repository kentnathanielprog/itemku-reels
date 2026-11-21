# Setup in a new Claude Code project (step by step)

## 1. Put the code in a private GitHub repo
```bash
cd itemku-reels            # this folder
git init -b main && git add -A && git commit -m "Initial import"
git remote add origin git@github.com:<you>/itemku-reels.git
git push -u origin main
```
(State lives in Git: queue, history, stories, usage log. Rendered videos are NOT committed; they travel as CI artifacts.)

## 2. Open it in Claude Code
- Cloud: claude.ai/code -> new session -> select the repo (connect GitHub first at https://claude.ai/connect-github and install the Claude GitHub App on the repo). Local: `cd itemku-reels && claude`.
- Cloud environment settings (menu in the session title bar -> Edit):
  - **Setup script:** `bash scripts/setup.sh`
  - **Network access** (Limited + allowed domains): `api.anthropic.com`, `graph.instagram.com` (or `graph.facebook.com`), `rupload.facebook.com`, `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, plus the news sites in `short/sources.json` and their image CDNs (add domains when a fetch fails).
  - **Environment variables:** `ANTHROPIC_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN` (you type them there; never in chat).
  - Docs: https://code.claude.com/docs/en/claude-code-on-the-web

## 3. Verify (in this order)
1. `bash tests/offline_test.sh` -> expect `HASIL: 10 lulus, 0 gagal` (about 40 s; no network/API).
2. `python3 auto/produce.py --dry-run` -> real scout + fetch, prints the picked stories and a cost estimate; no API call.
3. First real run: `python3 auto/produce.py`, then `python3 scripts/status.py`. Review the 3 videos yourself the first week (the visual check is new).
4. `python3 auto/publish.py --dry-run` -> prints the Graph API calls; live posting only after step 5 below.

## 4. Meta developer app (Instagram Graph API)
Checklist (verify each item against Meta's current docs; names change):
1. Instagram **Business or Creator** account. Choose the login flavour: *Instagram API with Instagram Login* (no Facebook Page) or Facebook Login (needs a Page).
2. Create an app at developers.facebook.com, add the Instagram product, give the account a role in the app (a single own account usually works in Development mode without App Review; confirm).
3. Permissions: content publishing (`instagram_business_content_publish` / `instagram_content_publish`) and insights (`instagram_business_manage_insights` / `instagram_manage_insights`).
4. Get `IG_USER_ID` and a long-lived token (about 60 days: **add a refresh reminder**). Store both as secrets/env vars.
5. Test with `python3 auto/publish.py --dry-run`, then ONE live post on a test account before enabling the schedule. Posts cannot be deleted via API.

> Panduan langkah demi langkah untuk GitHub Actions: `TUTORIAL_GITHUB.md`.

## 5. Scheduling
**Recommended: GitHub Actions** (`.github/workflows/`, no Claude session = no subscription tokens). Add repo secrets `ANTHROPIC_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN` (optional variables `GRAPH_HOST`, `GRAPH_VERSION`). Run **produce** once manually ("Run workflow") and read the log; then **publish** with dry-run on; only then let the cron run. Times (WIB): produce 05:27, publish 07:33 / 12:07 / 17:03. The workflows are untested on GitHub.
**Alternative: Claude Code cloud scheduled tasks** (each firing opens a full Claude session, which costs subscription tokens):
- Producer prompt: "Run `python3 auto/produce.py`, commit and push `auto/state` and `short/stories`, report the last 5 output lines."
- Publisher prompt: "Run `python3 auto/publish.py` then `python3 auto/insights.py`, commit and push `auto/state`, report the permalink or error."
(videos must then be available in the session's `out/`: this variant needs the producer and publisher in the same environment or an external media store.)

## 6. Go-live checklist
- [ ] `auto/state/queue.json` contains only intended items (empty at first).
- [ ] Licensed music in `auto/music/` + `catalog.json` (or accept silent videos).
- [ ] One supervised live post OK; Insights metric names confirmed.
- [ ] Kill switch tested (`touch auto/STOP` + commit, or repo variable `STOP=1`); token-refresh reminder set; weekly look at `scripts/status.py`.
- [ ] Decide models per role in `auto/config.json -> llm` after one week of measured usage.

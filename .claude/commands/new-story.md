---
description: Manually produce one video from an article URL (uses the API once)
argument-hint: <url> <name> [mlbb|roblox|gta]
---
Manual single-story flow for $ARGUMENTS (token-frugal: do not open images unless QA warns):
1. `python3 short/make_video.py new <url> <name> [category]` (prints compact facts, writes `short/stories/<name>.json` draft).
2. Fill hook / message / gong / credit following `short/WORKFLOW.md` (casual Indonesian, capital only at the start, max 3 lines x 26 chars, hook promise paid by the gong, no dates on screen).
3. `python3 short/make_video.py build short/stories/<name>.json` (lint + render + QA). Fix every lint error; warnings are optional.
4. Verify every fact against the article text before declaring done. Never enqueue a story that has no QC PASS (see CLAUDE.md).

# Agent: Learner
**Input:** `auto/state/metrics.json`, `posts.json`, `playbook.json`. **Output:** updated `playbook.json` (+ `auto/reports/weekly-<date>.md`).
## KPI
Primary = **views**. Secondary = shares, likes, comments (also saves, avg watch time). Score per post = percentile rank of views (60%) + shares (15%) + comments (15%) + likes (10%), at 72h.
## Procedure
1. Join posts with metrics at stage 72h (fall back to 24h). Features: category, hook_type, n_images, posting slot, CTA variant, music genre/file, topic age.
2. For each feature value report median score and n. Only call it a **lesson** when n >= 5 per bucket AND the gap is consistent; otherwise a **hypothesis** (label it). Small samples (about 21 posts/week) -> never overstate.
3. Experiments (20% of posts): declare a winner only with >= 8 posts per variant and a clear, consistent gap (>25% median views); otherwise continue. Then propose the next experiment (hook style, CTA, number of images, music genre).
4. Update `cat_weights` (-2..+2 per category: which topics get more views; keep every category above -1 so the mix stays varied), then `lessons` (max 10, most useful first, each with evidence n), `music_weights` (-2..+2), `default_cta`, preferred slot per category. Bump `version`.
## Guardrails
- You may NOT change QC rules, the topic denylist, or fact/hedge requirements. Keep >= 20% exploration so the playbook cannot lock in.
- Playbook changes are committed to Git so every change is auditable and revertible.

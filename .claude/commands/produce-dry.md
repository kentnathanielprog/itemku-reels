---
description: Dry-run the daily producer (scout + fetch + cost estimate, no API calls)
---
Run `python3 auto/produce.py --dry-run` and summarise: which stories were picked (category, site, image count) and the estimated cost. Flag anything suspicious: duplicate topics, non-gaming content, off-brand topics, stories with only one image. Do not call the API and do not render.

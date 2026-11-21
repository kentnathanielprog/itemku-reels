---
description: Run the offline self-test (about 40 s, no network, no API key)
---
Run `bash tests/offline_test.sh`. Report only the final PASS/FAIL line plus any failing check name. If something fails, read `/tmp/_produce.log` (not the whole repo), find the root cause, fix it, and re-run until all checks pass.

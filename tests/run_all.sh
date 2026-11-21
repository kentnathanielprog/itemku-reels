#!/usr/bin/env bash
# Runs every offline test. No network, no API key, no posting. usage: bash tests/run_all.sh
set -u; cd "$(dirname "$0")/.."; FAILED=()
run(){ echo "=== $1"; shift; "$@" || FAILED+=("$*"); }
run "offline_test (producer end-to-end)" bash tests/offline_test.sh
run "setup_test (Pillow pin, --ignore-installed)" bash tests/setup_test.sh
run "publish_test (fake Graph API: reconcile, burst, not_before, missing video)" python3 tests/publish_test.py
run "state_save_test (hard-fail state push)" bash tests/state_save_test.sh
run "session_run_test (manual-only flags)" bash tests/session_run_test.sh
run "produce_exit_test (exit codes 3/4)" bash tests/produce_exit_test.sh
[ -f tests/learning_test.sh ] && run "learning_test (learning agent guard/analyzer)" bash tests/learning_test.sh
echo; if [ ${#FAILED[@]} -eq 0 ]; then echo "SEMUA TES LULUS"; else echo "GAGAL: ${FAILED[*]}"; exit 1; fi

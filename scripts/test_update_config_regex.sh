#!/bin/bash
# Tiny self-check for the repo_path regex in update_config.sh — the fix that
# makes it handle SSH remotes, not just HTTPS. No framework, just asserts.
#
# Run: sh scripts/test_update_config_regex.sh

set -euo pipefail

repo_path_for() {
  echo "$1" | sed -E 's|.*[/:]([^/:]+)/([^/.]+)(\.git)?$|\1/\2|'
}

fail=0
check() {
  local url="$1" want="$2" got
  got=$(repo_path_for "$url")
  if [ "$got" != "$want" ]; then
    echo "FAIL: $url -> got '$got', want '$want'"
    fail=1
  else
    echo "ok:   $url -> $got"
  fi
}

check "git@github.com:nyucdsc/my-study.git" "nyucdsc/my-study"
check "git@github.com:nyucdsc/my-study" "nyucdsc/my-study"
check "https://github.com/nyucdsc/my-study.git" "nyucdsc/my-study"
check "https://github.com/nyucdsc/my-study" "nyucdsc/my-study"

exit $fail

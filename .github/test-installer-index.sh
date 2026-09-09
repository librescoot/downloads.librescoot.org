#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

input='{
  "tag_name": "v1.4.0",
  "published_at": "2026-09-08T12:34:56Z",
  "html_url": "https://github.com/librescoot/installer/releases/tag/v1.4.0",
  "body": "## Highlights\n\nA safer update flow.",
  "assets": [
    {
      "name": "librescoot-installer-macos-universal-v1.4.0.dmg",
      "size": 1234,
      "digest": "sha256:abcd",
      "browser_download_url": "https://example.invalid/installer.dmg"
    }
  ]
}'
out=$(printf '%s' "$input" | jq -f installer-index.jq)

fails=0
check() {
  local desc=$1 expr=$2 want=$3
  local got
  got=$(printf '%s' "$out" | jq -r "$expr")
  if [ "$got" != "$want" ]; then
    echo "FAIL: $desc: got '$got', want '$want'"
    fails=$((fails + 1))
  else
    echo "ok: $desc"
  fi
}

check "tag" '.tag_name' "v1.4.0"
check "publication date" '.published_at' "2026-09-08T12:34:56Z"
check "release URL" '.release_url' "https://github.com/librescoot/installer/releases/tag/v1.4.0"
check "editorial notes" '.release_notes' $'## Highlights\n\nA safer update flow.'
check "asset digest" '.assets[0].sha256' "abcd"
check "asset URL" '.assets[0].url' "https://example.invalid/installer.dmg"

without_body=$(printf '%s' "$input" | jq 'del(.body)' | jq -f installer-index.jq)
check_empty=$(printf '%s' "$without_body" | jq -r '.release_notes')
if [ -n "$check_empty" ]; then
  echo "FAIL: missing release body: got '$check_empty', want empty string"
  fails=$((fails + 1))
else
  echo "ok: missing release body"
fi

if [ "$fails" -ne 0 ]; then
  echo "$fails check(s) failed"
  exit 1
fi
echo "all checks passed"

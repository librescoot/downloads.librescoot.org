#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_SHA:?}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
printf '[]\n' > "$work/releases.json"
for page in $(seq 1 10); do
  gh api "repos/librescoot/librescoot/releases?per_page=100&page=$page" > "$work/page.json"
  jq -e 'type == "array"' "$work/page.json" >/dev/null
  jq -s '.[0] + .[1]' "$work/releases.json" "$work/page.json" > "$work/next.json"
  mv "$work/next.json" "$work/releases.json"
  count=$(jq length "$work/page.json")
  if [ "$count" -lt 100 ]; then break; fi
  if [ "$page" -eq 10 ]; then echo 'Release history limit exceeded' >&2; exit 1; fi
done
jq -f .github/filter-firmware-releases.jq "$work/releases.json" > "$work/filtered.json"
python3 .github/build-ota-catalog.py "$work/filtered.json" "$work/canary.json" --feed canary

if ! gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/canary-feed" > "$work/ref.json"; then
  gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs" \
    -f ref=refs/heads/canary-feed -f sha="$GITHUB_SHA" >/dev/null
fi
previous=''
if gh api "repos/$GITHUB_REPOSITORY/contents/updates/v2/canary.json?ref=canary-feed" > "$work/existing.json"; then
  previous=$(jq -r .sha "$work/existing.json")
  jq -r .content "$work/existing.json" | base64 --decode > "$work/old.json"
  if cmp -s "$work/old.json" "$work/canary.json"; then
    echo 'Canary catalog is unchanged'
    exit 0
  fi
fi
python3 - "$work/canary.json" "$previous" > "$work/request.json" <<'PY'
import base64, json, pathlib, sys
body = dict(message='chore(ota): refresh isolated canary catalog', branch='canary-feed',
            content=base64.b64encode(pathlib.Path(sys.argv[1]).read_bytes()).decode())
if sys.argv[2]:
    body['sha'] = sys.argv[2]
print(json.dumps(body))
PY
gh api --method PUT "repos/$GITHUB_REPOSITORY/contents/updates/v2/canary.json" --input "$work/request.json" >/dev/null
echo "Canary catalog: https://raw.githubusercontent.com/$GITHUB_REPOSITORY/canary-feed/updates/v2/canary.json"

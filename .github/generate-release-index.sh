#!/usr/bin/env bash
set -euo pipefail

# Generate per-channel release index JSON files from GitHub Releases API.
# Output: releases/{channel}.json with the most recent 30 releases per channel,
# containing only the fields the update service needs.

REPO="librescoot/librescoot"
RELEASES_PER_CHANNEL=30
API_URL="https://api.github.com/repos/${REPO}/releases"
OUTDIR="${DEST:-.}/releases"

mkdir -p "$OUTDIR"

# Fetch all releases (paginated, up to 300 — enough for months of nightlies)
all_releases="[]"
page=1
while [ "$page" -le 3 ]; do
  page_data=$(curl -sf -H "Accept: application/vnd.github+json" \
    -H "User-Agent: librescoot-downloads-gen" \
    ${GITHUB_TOKEN:+-H "Authorization: Bearer ${GITHUB_TOKEN}"} \
    "${API_URL}?per_page=100&page=${page}")

  count=$(echo "$page_data" | jq 'length')
  if [ "$count" -eq 0 ]; then
    break
  fi

  all_releases=$(echo "$all_releases" "$page_data" | jq -s '.[0] + .[1]')
  page=$((page + 1))
done

total=$(echo "$all_releases" | jq 'length')
echo "Fetched ${total} releases total"

# Generate index for each channel
for channel in nightly testing stable; do
  case "$channel" in
    stable)  prefix="v" ;;
    *)       prefix="${channel}-" ;;
  esac

  echo "$all_releases" | jq --arg prefix "$prefix" --argjson limit "$RELEASES_PER_CHANNEL" '
    [.[] | select(.tag_name | startswith($prefix))]
    | sort_by(.published_at) | reverse
    | .[:$limit]
    | [.[] | {
        tag_name,
        published_at,
        prerelease,
        assets: [.assets[] | {name, size, browser_download_url}]
      }]
  ' > "${OUTDIR}/${channel}.json"

  count=$(jq 'length' "${OUTDIR}/${channel}.json")
  echo "${channel}: ${count} releases"
done

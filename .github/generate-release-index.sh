#!/usr/bin/env bash
set -euo pipefail

# Generate per-channel release index JSON files from GitHub Releases API.
# Output: releases/{channel}.json with the most recent 30 releases per channel,
# containing only the fields the update service needs.

REPO="librescoot/librescoot"
RELEASES_PER_CHANNEL=30
API_URL="https://api.github.com/repos/${REPO}/releases"
OUTDIR="${DEST:-src/releases}"

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

# Fetch installer release
installer_data=$(curl -sf -H "Accept: application/vnd.github+json" \
  -H "User-Agent: librescoot-downloads-gen" \
  ${GITHUB_TOKEN:+-H "Authorization: Bearer ${GITHUB_TOKEN}"} \
  "https://api.github.com/repos/librescoot/installer/releases/latest")

if [ -n "$installer_data" ]; then
  echo "$installer_data" | jq '{
    tag_name,
    assets: [.assets[] | {name, size, url: .browser_download_url}]
  }' > "${OUTDIR}/installer.json"
  echo "installer: $(echo "$installer_data" | jq '.tag_name')"
else
  echo '{"tag_name":"","assets":[]}' > "${OUTDIR}/installer.json"
  echo "installer: failed to fetch"
fi

# Generate map/routing data indexes
for repo in osm-tiles valhalla-tiles; do
  data=$(curl -sf -H "Accept: application/vnd.github+json" \
    -H "User-Agent: librescoot-downloads-gen" \
    ${GITHUB_TOKEN:+-H "Authorization: Bearer ${GITHUB_TOKEN}"} \
    "https://api.github.com/repos/librescoot/${repo}/releases/tags/latest")

  if [ -n "$data" ]; then
    echo "$data" | jq '[.assets[] | {
      name,
      size,
      sha256: (.digest | if . then ltrimstr("sha256:") else null end),
      updated_at: .updated_at,
      url: .browser_download_url
    }]' > "${OUTDIR}/${repo}.json"
    count=$(jq 'length' "${OUTDIR}/${repo}.json")
    echo "${repo}: ${count} assets"
  else
    echo "[]" > "${OUTDIR}/${repo}.json"
    echo "${repo}: failed to fetch, wrote empty array"
  fi
done

# Generate combined tiles.json keyed by region slug for update checks
jq -n \
  --slurpfile osm "${OUTDIR}/osm-tiles.json" \
  --slurpfile valhalla "${OUTDIR}/valhalla-tiles.json" '
  def by_region(prefix; suffix):
    [.[] | {
      key: (.name | ltrimstr(prefix) | rtrimstr(suffix)),
      value: {sha256, size, updated_at, url}
    }] | from_entries;

  ($osm[0] | by_region("tiles_"; ".mbtiles")) as $osm_map |
  ($valhalla[0] | by_region("valhalla_tiles_"; ".tar")) as $val_map |
  ($osm_map | keys) + ($val_map | keys) | unique | map({
    key: .,
    value: {
      map: ($osm_map[.] // null),
      valhalla: ($val_map[.] // null)
    }
  }) | from_entries
' > "${OUTDIR}/tiles.json"
echo "tiles.json: combined index written"

# Generate firmware index for each channel
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
        assets: [.assets[] | {name, size, url: .browser_download_url}]
      }]
  ' > "${OUTDIR}/${channel}.json"

  count=$(jq 'length' "${OUTDIR}/${channel}.json")
  echo "${channel}: ${count} releases"
done

# Combined latest-per-channel manifest. One fetch gets the current pointer
# for every firmware channel; consumers (installer) avoid three round trips.
jq -n \
  --slurpfile stable "${OUTDIR}/stable.json" \
  --slurpfile testing "${OUTDIR}/testing.json" \
  --slurpfile nightly "${OUTDIR}/nightly.json" '
  {
    stable:  ($stable[0][0]  // null),
    testing: ($testing[0][0] // null),
    nightly: ($nightly[0][0] // null)
  }
' > "${OUTDIR}/latest.json"
echo "latest.json: combined latest-per-channel manifest written"

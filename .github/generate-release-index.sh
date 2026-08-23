#!/usr/bin/env bash
set -euo pipefail

# Generate per-channel release index JSON files from GitHub Releases API.
# Output: releases/{channel}.json with the most recent 30 releases per channel,
# containing only the fields the update service needs.

REPO="librescoot/librescoot"
RELEASES_PER_CHANNEL=30
# The stage-0 image the installer writes before it installs an artifact. Pinned
# on purpose and bumped by hand: it carries whatever the installer needs in
# order to run (redis, bluetooth-service, mender-update), and the firmware line
# a user picks may predate any of that. Artifacts depend on device_type alone,
# so any stage-0 for this board can carry any target version.
BOOTSTRAP_TAG="${BOOTSTRAP_TAG:-nightly-20260823T021701}"
API_URL="https://api.github.com/repos/${REPO}/releases"
OUTDIR="${DEST:-src/releases}"

mkdir -p "$OUTDIR"

# A transient network or TLS blip used to abort the whole script through
# pipefail, leaving releases/*.json describing the previous build. Nothing
# downstream notices: vehicles keep reading a stale manifest and simply never
# see the new release. Retry before giving up.
gh_api() {
  curl -sfL --retry 5 --retry-delay 3 --retry-all-errors \
    --connect-timeout 15 --max-time 120 \
    -H "Accept: application/vnd.github+json" \
    -H "User-Agent: librescoot-downloads-gen" \
    ${GITHUB_TOKEN:+-H "Authorization: Bearer ${GITHUB_TOKEN}"} \
    "$@"
}


# Fetch all releases (paginated, up to 300 — enough for months of nightlies)
all_releases="[]"
page=1
while [ "$page" -le 3 ]; do
  page_data=$(gh_api \
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
installer_data=$(gh_api \
  "https://api.github.com/repos/librescoot/installer/releases/latest")

if [ -n "$installer_data" ]; then
  echo "$installer_data" | jq '{
    tag_name,
    assets: [.assets[] | {
      name,
      size,
      sha256: (.digest | if . then ltrimstr("sha256:") else null end),
      url: .browser_download_url
    }]
  }' > "${OUTDIR}/installer.json"
  echo "installer: $(echo "$installer_data" | jq '.tag_name')"
else
  echo '{"tag_name":"","assets":[]}' > "${OUTDIR}/installer.json"
  echo "installer: failed to fetch"
fi

# Generate map/routing data indexes
for repo in osm-tiles valhalla-tiles; do
  case "$repo" in
    osm-tiles)
      # osm-tiles publishes every build under its own tiles-<timestamp> tag so
      # asset URLs are immutable: the old scheme rewrote one tag in place, so a
      # URL could serve different bytes than the digest recorded here and a
      # vehicle would fail the checksum on a file it downloaded correctly.
      # There is deliberately no fallback to the old fixed tag. That release
      # still exists but is frozen at the last build of the old scheme, so
      # falling back to it would quietly publish stale tiles rather than fail.
      data=$(gh_api \
        "https://api.github.com/repos/librescoot/${repo}/releases?per_page=20" \
        | jq '[.[] | select(.draft == false and .prerelease == false
                            and (.tag_name | startswith("tiles-")))] | .[0] // empty')
      if [ -z "$data" ]; then
        echo "${repo}: no tiles-* release found" >&2
        exit 1
      fi
      ;;
    *)
      # valhalla-tiles still publishes to a fixed tag, and its dated releases
      # are older than it, so resolve it by tag rather than by date.
      data=$(gh_api \
        "https://api.github.com/repos/librescoot/${repo}/releases/tags/latest")
      ;;
  esac

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

# Generate combined tiles.json keyed by region slug for update checks.
# The jq program lives in tiles-index.jq so .github/test-tiles-index.sh can
# exercise it against fixtures without hitting the GitHub API.
jq -n \
  --slurpfile osm "${OUTDIR}/osm-tiles.json" \
  --slurpfile valhalla "${OUTDIR}/valhalla-tiles.json" \
  -f "$(dirname "${BASH_SOURCE[0]}")/tiles-index.jq" \
  > "${OUTDIR}/tiles.json"
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
        assets: [.assets[] | {
          name,
          size,
          sha256: (.digest | if . then ltrimstr("sha256:") else null end),
          url: .browser_download_url
        }]
      }]
  ' > "${OUTDIR}/${channel}.json"

  count=$(jq 'length' "${OUTDIR}/${channel}.json")
  echo "${channel}: ${count} releases"
done

# The pinned stage-0 release, as its own entry.
echo "$all_releases" | jq --arg tag "$BOOTSTRAP_TAG" '
  [.[] | select(.tag_name == $tag)]
  | .[:1]
  | [.[] | {
      tag_name,
      published_at,
      prerelease,
      assets: [.assets[] | {
        name,
        size,
        sha256: (.digest | if . then ltrimstr("sha256:") else null end),
        url: .browser_download_url
      }]
    }]
' > "${OUTDIR}/bootstrap.json"

if [ "$(jq 'length' "${OUTDIR}/bootstrap.json")" -eq 0 ]; then
  # A pin that no longer resolves is worse than no pin: the installer would
  # fall back to the target release's stage-0, which is the behaviour this
  # exists to avoid. Fail loudly so the tag gets bumped.
  echo "ERROR: bootstrap tag ${BOOTSTRAP_TAG} matched no release" >&2
  exit 1
fi
echo "bootstrap: pinned to ${BOOTSTRAP_TAG}"

# Combined latest-per-channel manifest. One fetch gets the current pointer
# for every firmware channel; consumers (installer) avoid three round trips.
# bootstrap is the stage-0 to write first, whichever channel is chosen.
jq -n \
  --slurpfile stable "${OUTDIR}/stable.json" \
  --slurpfile testing "${OUTDIR}/testing.json" \
  --slurpfile nightly "${OUTDIR}/nightly.json" \
  --slurpfile bootstrap "${OUTDIR}/bootstrap.json" '
  {
    stable:  ($stable[0][0]  // null),
    testing: ($testing[0][0] // null),
    nightly: ($nightly[0][0] // null),
    bootstrap: ($bootstrap[0][0] // null)
  }
' > "${OUTDIR}/latest.json"
echo "latest.json: combined latest-per-channel manifest written"

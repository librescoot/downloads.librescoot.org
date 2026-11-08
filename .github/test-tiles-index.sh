#!/usr/bin/env bash
# Fixture test for tiles-index.jq. No network, no GitHub API.
set -euo pipefail
cd "$(dirname "$0")"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

cat > "$tmp/osm.json" <<'JSON'
[
  {"name":"tiles_bayern.mbtiles","size":428474368,"sha256":"osm-bayern","updated_at":"2026-08-01T03:00:30Z","url":"https://example.invalid/tiles_bayern.mbtiles"},
  {"name":"tiles_bremen.mbtiles","size":15000000,"sha256":"osm-bremen","updated_at":"2026-08-01T03:00:00Z","url":"https://example.invalid/tiles_bremen.mbtiles"},
  {"name":"tiles_bremen.from-tiles-20260701T000000Z.hdelta","size":18523,"sha256":"osm-bremen-patch","updated_at":"2026-08-01T03:00:00Z","url":"https://example.invalid/tiles_bremen.from-tiles-20260701T000000Z.hdelta"}
]
JSON

cat > "$tmp/valhalla.json" <<'JSON'
[
  {"name":"valhalla_tiles_bayern.tar","size":725043200,"sha256":"val-bayern","updated_at":"2026-08-01T02:51:53Z","url":"https://example.invalid/valhalla_tiles_bayern.tar"},
  {"name":"valhalla_tiles_bayern.tar.zst","size":224400000,"sha256":"zst-bayern","updated_at":"2026-08-01T02:55:00Z","url":"https://example.invalid/valhalla_tiles_bayern.tar.zst"},
  {"name":"valhalla_tiles_bremen.tar","size":13000000,"sha256":"val-bremen","updated_at":"2026-08-01T02:40:00Z","url":"https://example.invalid/valhalla_tiles_bremen.tar"}
]
JSON

out=$(jq -n --slurpfile osm "$tmp/osm.json" --slurpfile valhalla "$tmp/valhalla.json" -f tiles-index.jq)

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

check "no phantom .tar.zst region"      '.["bayern.tar.zst"] // "absent"'        "absent"
check "exactly two regions"             'keys | length'                          "2"
check "valhalla url is the plain tar"   '.bayern.valhalla.url'                   "https://example.invalid/valhalla_tiles_bayern.tar"
check "valhalla sha is the plain tar"   '.bayern.valhalla.sha256'                "val-bayern"
check "valhalla size is the plain tar"  '.bayern.valhalla.size'                  "725043200"
check "compressed codec"                '.bayern.valhalla.compressed.codec'      "zstd"
check "compressed url"                  '.bayern.valhalla.compressed.url'        "https://example.invalid/valhalla_tiles_bayern.tar.zst"
check "compressed sha"                  '.bayern.valhalla.compressed.sha256'     "zst-bayern"
check "compressed size"                 '.bayern.valhalla.compressed.size'       "224400000"
check "region without zst has none"     '.bremen.valhalla.compressed // "absent"' "absent"
check "map entry preserved"             '.bayern.map.sha256'                     "osm-bayern"
check "map delta listed"                '.bremen.map.deltas | length'            "1"
check "map delta base version"          '.bremen.map.deltas[0].base_version'     "tiles-20260701T000000Z"
check "map delta base sha comes from the map asset" '.bremen.map.deltas[0].base_sha256' "osm-bremen"
check "map delta is not a phantom region" '.map_deltas_count // "none"'          "none"
check "delta adds no region key"        'keys | length'                          "2"
check "no key carries the delta suffix" '[keys[] | select(test("hdelta|from-"))] | length' "0"

if [ "$fails" -ne 0 ]; then
  echo "$fails check(s) failed"
  exit 1
fi
echo "all checks passed"

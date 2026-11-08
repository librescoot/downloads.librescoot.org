# Build the per-region tiles index from the osm-tiles and valhalla-tiles asset
# lists. Expects --slurpfile osm and --slurpfile valhalla.
#
# `valhalla.url` / `.size` / `.sha256` always describe the UNCOMPRESSED tar,
# because clients that predate the compressed asset rename whatever they
# download straight onto /data/valhalla/tiles.tar. The compressed variant is
# additive and optional.
#
# The endswith() guard matters: rtrimstr(".tar") leaves
# "valhalla_tiles_bayern.tar.zst" untouched, which would otherwise produce a
# phantom region keyed "bayern.tar.zst".
def by_region(prefix; suffix):
  [.[]
   | select(.name | endswith(suffix))
   | {
       key: (.name | ltrimstr(prefix) | rtrimstr(suffix)),
       value: ({sha256, size, updated_at, url} + (if .version then {version} else {} end) + (if .deltas then {deltas} else {} end))
     }
  ] | from_entries;

# Map deltas name their base release in the file name:
# tiles_<region>.from-<base-version>.hdelta. Their base hash comes from the
# base region asset in the same flat list, so the index never guesses it.
def map_deltas($osm_map):
  [ .[]
    | select(.name | test("^tiles_.+\\.from-tiles-[A-Za-z0-9]+\\.hdelta$"))
    | (.name | capture("^tiles_(?<region>.+)\\.from-(?<base>tiles-[A-Za-z0-9]+)\\.hdelta$")) as $m
    | {region: $m.region, base: $m.base,
       entry: ({sha256, size, updated_at, url}
               + {algorithm: "hdiffpatch", base_version: $m.base,
                  base_sha256: $osm_map[$m.region].sha256})}
  ]
  | group_by(.region)
  | map({key: .[0].region, value: map(.entry)})
  | from_entries;

($osm[0]      | by_region("tiles_";          ".mbtiles")) as $osm_map |
($osm[0]      | map_deltas($osm_map))                     as $osm_delta |
($valhalla[0] | by_region("valhalla_tiles_"; ".tar"))     as $val_map |
($valhalla[0] | by_region("valhalla_tiles_"; ".tar.zst")) as $val_zst |

($osm_map | keys) + ($val_map | keys) | unique | map({
  key: .,
  value: {
    map: (if $osm_map[.] == null then null
          else $osm_map[.]
               + (if $osm_delta[.] == null then {} else {deltas: $osm_delta[.]} end)
          end),
    valhalla: (
      . as $slug
      | if $val_map[$slug] == null then null
        else $val_map[$slug]
             + (if $val_zst[$slug] == null then {}
                else {compressed: ({codec: "zstd"} + ($val_zst[$slug] | {url, size, sha256}))}
                end)
        end
    )
  }
}) | from_entries

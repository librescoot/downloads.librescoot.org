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
       value: {sha256, size, updated_at, url}
     }
  ] | from_entries;

($osm[0]      | by_region("tiles_";          ".mbtiles")) as $osm_map |
($valhalla[0] | by_region("valhalla_tiles_"; ".tar"))     as $val_map |
($valhalla[0] | by_region("valhalla_tiles_"; ".tar.zst")) as $val_zst |

($osm_map | keys) + ($val_map | keys) | unique | map({
  key: .,
  value: {
    map: ($osm_map[.] // null),
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

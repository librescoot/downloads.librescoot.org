# Map and routing index

`https://downloads.librescoot.org/releases/maps-routing.json` is the versioned
index for offline map downloads. The site rebuilds it from the newest published
asset **per region** in the `osm-tiles` and `valhalla-tiles` release histories.
Rebuilding one region does not require copying unchanged assets into a new
release. A release may contain regions from several countries.

```json
{
  "version": 1,
  "regions": {
    "graz": {
      "country": "AT",
      "name": "Graz",
      "map": {
        "url": "https://github.com/librescoot/osm-tiles/releases/download/tiles-.../tiles_graz.mbtiles",
        "size": 123,
        "sha256": "...",
        "updated_at": "2026-09-26T00:00:00Z"
      },
      "routing": {
        "url": "https://github.com/librescoot/valhalla-tiles/releases/download/tiles-.../valhalla_tiles_graz.tar",
        "size": 456,
        "sha256": "...",
        "updated_at": "2026-09-26T00:00:00Z",
        "compressed": {
          "codec": "zstd",
          "url": "https://github.com/librescoot/valhalla-tiles/releases/download/tiles-.../valhalla_tiles_graz.tar.zst",
          "size": 78,
          "sha256": "...",
          "updated_at": "2026-09-26T00:00:00Z"
        }
      }
    }
  }
}
```

`country` is an ISO 3166-1 alpha-2 code. `map` or `routing` can be null when
only one repository has published the region; clients should offer installation
only when both are present. `routing.compressed` is optional. SHA-256 may be
null for older GitHub release assets that have no server-provided digest.

The compatibility indexes `tiles.json`, `osm-tiles.json`, and
`valhalla-tiles.json` remain available. All four indexes are generated from
the same selected assets; clients using the older formats continue to resolve
the same URLs.

Both tile repositories schedule a full build on the 1st of each month (maps at
00:00 UTC, routing at 00:30 UTC). Manual builds can publish selected regions
between those full runs. Each successful build creates a separate immutable
release; the index combines the newest assets per region across releases.

Publication never deletes an older release. A separate weekly, read-only audit
reports a release as eligible for cleanup only if none of its asset URLs occur
in the live site indexes and every asset has a replacement published at least
seven days earlier. The fixed Valhalla `latest` release is always protected.
The audit does not delete releases or tags.

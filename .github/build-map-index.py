#!/usr/bin/env python3
"""Select the newest immutable map assets per region from GitHub releases."""

import json
import re
import sys
from pathlib import Path

MAP = re.compile(r"^tiles_(.+)\.mbtiles$")
ROUTING = re.compile(r"^valhalla_tiles_(.+)\.tar$")
COMPRESSED = re.compile(r"^valhalla_tiles_(.+)\.tar\.zst$")


def release_order(releases, repo):
    eligible = [r for r in releases if not r.get("draft") and not r.get("prerelease")
                and (r.get("tag_name", "").startswith("tiles-")
                     or (repo == "valhalla-tiles" and r.get("tag_name") == "latest"))]
    return sorted(eligible, key=lambda r: r.get("published_at") or "", reverse=True)


def asset_info(asset):
    digest = asset.get("digest")
    return {
        "name": asset["name"],
        "size": asset["size"],
        "sha256": digest.removeprefix("sha256:") if digest else None,
        "updated_at": asset.get("updated_at"),
        "url": asset["browser_download_url"],
    }


def select_assets(releases, repo):
    selected = {}
    for release in release_order(releases, repo):
        assets = release.get("assets", [])
        if repo == "osm-tiles":
            for asset in assets:
                match = MAP.fullmatch(asset["name"])
                if match and match.group(1) not in selected:
                    selected[match.group(1)] = [asset_info(asset)]
        else:
            by_name = {a["name"]: a for a in assets}
            for asset in assets:
                match = ROUTING.fullmatch(asset["name"])
                if match and match.group(1) not in selected:
                    compressed = by_name.get(asset["name"] + ".zst")
                    selected[match.group(1)] = [asset_info(asset)]
                    if compressed:
                        selected[match.group(1)].append(asset_info(compressed))
    return [asset for region in sorted(selected) for asset in selected[region]]


def build_manifest(catalog, osm_assets, routing_assets):
    known = {region["id"]: region for region in catalog}
    maps = {m.group(1): a for a in osm_assets if (m := MAP.fullmatch(a["name"]))}
    routes = {m.group(1): a for a in routing_assets if (m := ROUTING.fullmatch(a["name"]))}
    compressed = {m.group(1): a for a in routing_assets
                  if (m := COMPRESSED.fullmatch(a["name"]))}
    regions = {}
    for slug in sorted(maps.keys() | routes.keys()):
        metadata = known.get(slug, {})
        routing = routes.get(slug)
        if routing:
            routing = {k: v for k, v in routing.items() if k != "name"}
            if slug in compressed:
                routing["compressed"] = {"codec": "zstd", **{
                    k: v for k, v in compressed[slug].items() if k != "name"
                }}
        regions[slug] = {
            "country": metadata.get("country"),
            "name": metadata.get("name", slug.replace("-", " ").replace("_", " ").title()),
            "location": metadata.get("location"),
            "map": {k: v for k, v in maps[slug].items() if k != "name"} if slug in maps else None,
            "routing": routing,
        }
    return {"version": 1, "regions": regions}


def main():
    catalog_path, osm_path, routing_path, out_path = map(Path, sys.argv[1:])
    catalog = json.loads(catalog_path.read_text())
    osm = select_assets(json.loads(osm_path.read_text()), "osm-tiles")
    routing = select_assets(json.loads(routing_path.read_text()), "valhalla-tiles")
    if not osm or not routing:
        raise SystemExit("No map or routing release assets found")
    out_path.mkdir(parents=True, exist_ok=True)
    for name, data in (("osm-tiles.json", osm), ("valhalla-tiles.json", routing),
                       ("maps-routing.json", build_manifest(catalog, osm, routing))):
        (out_path / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(f"{name}: {len(data['regions'] if isinstance(data, dict) else data)} entries")


if __name__ == "__main__":
    main()

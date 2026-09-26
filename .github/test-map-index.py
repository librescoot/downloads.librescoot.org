#!/usr/bin/env python3
"""Fixture tests for selecting map assets across partial releases."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("map_index", Path(__file__).with_name("build-map-index.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def asset(name, tag):
    return {"name": name, "size": 12, "digest": "sha256:" + tag,
            "updated_at": "2026-09-26T00:00:00Z",
            "browser_download_url": f"https://example.invalid/{tag}/{name}"}


def release(tag, date, *assets):
    return {"tag_name": tag, "published_at": date, "draft": False,
            "prerelease": False, "assets": list(assets)}


class PartialReleaseTest(unittest.TestCase):
    def test_new_map_asset_keeps_unmodified_region(self):
        releases = [
            release("tiles-1", "2026-08-01T00:00:00Z",
                    asset("tiles_bayern.mbtiles", "old"), asset("tiles_alsace.mbtiles", "old")),
            release("tiles-2", "2026-09-01T00:00:00Z", asset("tiles_alsace.mbtiles", "new")),
        ]
        result = {a["name"]: a for a in module.select_assets(releases, "osm-tiles")}
        self.assertIn("/old/tiles_bayern", result["tiles_bayern.mbtiles"]["url"])
        self.assertIn("/new/tiles_alsace", result["tiles_alsace.mbtiles"]["url"])

    def test_routing_pair_comes_from_one_release_with_legacy_fallback(self):
        releases = [
            release("latest", "2026-08-01T00:00:00Z",
                    asset("valhalla_tiles_bayern.tar", "old"),
                    asset("valhalla_tiles_alsace.tar", "old")),
            release("tiles-2", "2026-09-01T00:00:00Z",
                    asset("valhalla_tiles_alsace.tar", "new"),
                    asset("valhalla_tiles_alsace.tar.zst", "new")),
        ]
        result = {a["name"]: a for a in module.select_assets(releases, "valhalla-tiles")}
        self.assertEqual(len(result), 3)
        self.assertIn("/old/", result["valhalla_tiles_bayern.tar"]["url"])
        self.assertIn("/new/", result["valhalla_tiles_alsace.tar.zst"]["url"])
        catalog = [{"id": "alsace", "name": "Alsace", "country": "FR",
                    "location": {"subdivision_codes": ["FR-67", "FR-68"]}}]
        osm = [module.asset_info(asset("tiles_alsace.mbtiles", "new"))]
        manifest = module.build_manifest(catalog, osm, list(result.values()))
        self.assertEqual(manifest["version"], 1)
        self.assertEqual(manifest["regions"]["alsace"]["country"], "FR")
        self.assertEqual(manifest["regions"]["alsace"]["location"]["subdivision_codes"],
                         ["FR-67", "FR-68"])
        self.assertEqual(manifest["regions"]["alsace"]["routing"]["compressed"]["codec"], "zstd")
        self.assertIsNone(manifest["regions"]["bayern"]["map"])

    def test_draft_releases_are_ignored(self):
        releases = [release("tiles-1", "2026-08-01T00:00:00Z", asset("tiles_alsace.mbtiles", "old")),
                    {**release("tiles-2", "2026-09-01T00:00:00Z", asset("tiles_alsace.mbtiles", "draft")), "draft": True}]
        self.assertIn("/old/", module.select_assets(releases, "osm-tiles")[0]["url"])


if __name__ == "__main__":
    unittest.main()

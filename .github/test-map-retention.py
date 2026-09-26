#!/usr/bin/env python3
"""Offline safety tests for the read-only release retention audit."""

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("audit", Path(__file__).with_name("audit-map-releases.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def asset(name, tag):
    return {"name": name, "size": 100,
            "browser_download_url": f"https://github.com/librescoot/osm-tiles/releases/download/{tag}/{name}"}


def release(tag, days_ago, *assets):
    date = NOW - timedelta(days=days_ago)
    return {"tag_name": tag, "published_at": date.isoformat(),
            "draft": False, "prerelease": False, "assets": list(assets)}


class RetentionTest(unittest.TestCase):
    def test_partial_release_keeps_old_full_release(self):
        old = release("tiles-old", 90, asset("tiles_bayern.mbtiles", "tiles-old"),
                      asset("tiles_alsace.mbtiles", "tiles-old"))
        newer = release("tiles-new", 10, asset("tiles_alsace.mbtiles", "tiles-new"))
        current = {old["assets"][0]["browser_download_url"], newer["assets"][0]["browser_download_url"]}
        self.assertEqual(module.audit([old, newer], "osm-tiles", current, NOW), [])

    def test_superseded_release_waits_seven_days_from_replacement(self):
        old = release("tiles-old", 90, asset("tiles_alsace.mbtiles", "tiles-old"))
        new = release("tiles-new", 6, asset("tiles_alsace.mbtiles", "tiles-new"))
        current = {new["assets"][0]["browser_download_url"]}
        self.assertEqual(module.audit([new, old], "osm-tiles", current, NOW), [])
        new["published_at"] = (NOW - timedelta(days=8)).isoformat()
        self.assertEqual(module.audit([new, old], "osm-tiles", current, NOW),
                         [("tiles-old", 1, 100)])

    def test_live_url_blocks_cleanup_even_after_replacement(self):
        old = release("tiles-old", 90, asset("tiles_alsace.mbtiles", "tiles-old"))
        new = release("tiles-new", 8, asset("tiles_alsace.mbtiles", "tiles-new"))
        current = {old["assets"][0]["browser_download_url"]}
        self.assertEqual(module.audit([new, old], "osm-tiles", current, NOW), [])

    def test_missing_live_asset_fails_closed(self):
        old = release("tiles-old", 90, asset("tiles_alsace.mbtiles", "tiles-old"))
        with self.assertRaises(ValueError):
            module.audit([old], "osm-tiles", {"https://example.invalid/missing"}, NOW)

    def test_flat_and_region_indexes_must_agree(self):
        url = asset("tiles_alsace.mbtiles", "tiles-old")["browser_download_url"]
        manifest = {"version": 1, "regions": {"alsace": {"map": {"url": url}, "routing": None}}}
        legacy = {"alsace": {"map": {"url": url}, "valhalla": None}}
        self.assertEqual(module.live_urls("osm-tiles", [{"url": url}], manifest, legacy), {url})
        with self.assertRaises(ValueError):
            module.live_urls("osm-tiles", [{"url": "https://example.invalid/wrong"}], manifest, legacy)
        with self.assertRaises(ValueError):
            module.live_urls("osm-tiles", [{"url": url}], manifest,
                             {"alsace": {"map": {"url": "https://example.invalid/stale"}}})

    def test_fixed_latest_is_never_a_candidate(self):
        old = release("latest", 90, asset("valhalla_tiles_alsace.tar", "latest"))
        new = release("tiles-new", 8, asset("valhalla_tiles_alsace.tar", "tiles-new"))
        current = {new["assets"][0]["browser_download_url"]}
        self.assertEqual(module.audit([old, new], "valhalla-tiles", current, NOW), [])


if __name__ == "__main__":
    unittest.main()

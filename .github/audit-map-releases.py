#!/usr/bin/env python3
"""Read-only audit of regional tile releases eligible for later cleanup."""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://api.github.com/repos/librescoot"
SITE = "https://downloads.librescoot.org/releases"
GRACE = timedelta(days=7)
PATTERNS = {
    "osm-tiles": re.compile(r"^tiles_(.+)\.mbtiles$"),
    "valhalla-tiles": re.compile(r"^valhalla_tiles_(.+)\.tar(?:\.zst)?$"),
}


def fetch_json(url, token=None):
    headers = {"User-Agent": "librescoot-map-retention-audit"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return json.load(response)


def github_releases(repo, token):
    releases = []
    page = 1
    while True:
        batch = fetch_json(f"{BASE}/{repo}/releases?per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError(f"unexpected release response for {repo}")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def live_urls(repo, listing, manifest, legacy):
    if not isinstance(listing, list) or not listing or manifest.get("version") != 1:
        raise ValueError(f"missing live index for {repo}")
    regions = manifest.get("regions")
    if not isinstance(regions, dict) or not regions:
        raise ValueError("missing maps-routing regions")
    flat = {asset["url"] for asset in listing}
    if len(flat) != len(listing):
        raise ValueError(f"duplicate asset URL in {repo} index")
    selected = set()
    for region in regions.values():
        if repo == "osm-tiles":
            if region.get("map"):
                selected.add(region["map"]["url"])
        else:
            routing = region.get("routing")
            if routing:
                selected.add(routing["url"])
                if routing.get("compressed"):
                    selected.add(routing["compressed"]["url"])
    if flat != selected:
        raise ValueError(f"flat and maps-routing indexes disagree for {repo}")
    if not isinstance(legacy, dict) or not legacy:
        raise ValueError("missing legacy tiles index")
    old = set()
    for region in legacy.values():
        entry = region.get("map") if repo == "osm-tiles" else region.get("valhalla")
        if entry:
            old.add(entry["url"])
            if repo == "valhalla-tiles" and entry.get("compressed"):
                old.add(entry["compressed"]["url"])
    if flat != old:
        raise ValueError(f"flat and legacy tiles indexes disagree for {repo}")
    return flat


def audit(releases, repo, current_urls, now):
    pattern = PATTERNS[repo]
    eligible = [r for r in releases if not r.get("draft") and not r.get("prerelease")
                and (r.get("tag_name", "").startswith("tiles-")
                     or (repo == "valhalla-tiles" and r.get("tag_name") == "latest"))]
    eligible.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    available = {a["browser_download_url"] for r in eligible for a in r.get("assets", [])}
    if not current_urls or not current_urls <= available:
        raise ValueError(f"live {repo} index refers to missing release assets")

    replacements = {}
    candidates = []
    for release in eligible:
        tag = release["tag_name"]
        assets = release.get("assets", [])
        published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
        safe = tag != "latest" and bool(assets)
        for asset in assets:
            name = asset["name"]
            url = asset["browser_download_url"]
            newer = replacements.get(name)
            if not pattern.fullmatch(name) or url in current_urls or newer is None or now - newer < GRACE:
                safe = False
        if safe:
            candidates.append((tag, len(assets), sum(a["size"] for a in assets)))
        for asset in assets:
            replacements.setdefault(asset["name"], published)
    return candidates


def main():
    token = os.environ.get("GITHUB_TOKEN")
    manifest = fetch_json(f"{SITE}/maps-routing.json")
    legacy = fetch_json(f"{SITE}/tiles.json")
    now = datetime.now(timezone.utc)
    for repo in PATTERNS:
        listing = fetch_json(f"{SITE}/{repo}.json")
        current = live_urls(repo, listing, manifest, legacy)
        candidates = audit(github_releases(repo, token), repo, current, now)
        print(f"{repo}: {len(current)} indexed assets; {len(candidates)} cleanup candidates (dry run)")
        for tag, count, size in candidates:
            print(f"  {tag}: {count} assets, {size / 1_000_000:.0f} MB")
    print("No releases or tags were deleted.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"Retention audit failed closed: {exc}")

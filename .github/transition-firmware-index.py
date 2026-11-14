#!/usr/bin/env python3
"""Split existing firmware indexes at three verified channel bridge releases."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

CHANNELS = ("stable", "testing", "nightly")


def validate_bridge(channel, bridge, tag):
    if not isinstance(bridge, dict) or bridge.get("tag_name") != tag or bridge.get("draft") is not False:
        raise ValueError(f"{channel}: bridge tag is missing, unpublished or mismatched")
    if channel == "stable":
        if tag != "v1.4.3" or bridge.get("prerelease") is not False:
            raise ValueError("stable bridge must be published stable v1.4.3")
    elif not re.fullmatch(rf"{channel}-\d{{8}}T\d{{6}}", tag) or bridge.get("prerelease") is not True:
        raise ValueError(f"{channel}: invalid bridge tag or release channel")
    if not isinstance(bridge.get("published_at"), str) or not bridge["published_at"].endswith("Z"):
        raise ValueError(f"{channel}: bridge lacks published timestamp")
    assets = bridge.get("assets")
    if not isinstance(assets, list):
        raise ValueError(f"{channel}: bridge has no assets")
    names = set()
    converted = []
    for asset in assets:
        name = asset.get("name", "")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"{channel}: invalid or duplicate asset name")
        names.add(name)
        digest = asset.get("digest") or ""
        sha = digest.removeprefix("sha256:") if digest.startswith("sha256:") else None
        converted.append({"name": name, "size": asset.get("size"), "sha256": sha, "url": asset.get("browser_download_url")})
    for board in ("mdb", "dbc"):
        expected = f"librescoot-unu-{board}-{tag}.mender"
        matches = [a for a in converted if a["name"] == expected]
        if len(matches) != 1:
            raise ValueError(f"{channel}: missing bridge artifact {expected}")
        asset = matches[0]
        if not isinstance(asset["size"], int) or asset["size"] <= 0 or not re.fullmatch(r"[a-f0-9]{64}", asset["sha256"] or ""):
            raise ValueError(f"{channel}: bridge artifact lacks size or SHA-256")
        parsed = urlparse(asset["url"] or "")
        if (parsed.scheme != "https" or parsed.hostname != "github.com" or
                parsed.path != f"/librescoot/librescoot/releases/download/{tag}/{expected}" or
                parsed.query or parsed.fragment):
            raise ValueError(f"{channel}: bridge artifact URL does not match its release")
    return {"tag_name": tag, "published_at": bridge["published_at"], "prerelease": bridge["prerelease"], "assets": converted}


def transition(indexes, latest, bridges, tags):
    if set(indexes) != set(CHANNELS) or set(bridges) != set(CHANNELS) or set(tags) != set(CHANNELS):
        raise ValueError("all three channel indexes and bridge pins are required")
    anchors = {c: validate_bridge(c, bridges[c], tags[c]) for c in CHANNELS}
    legacy = {}
    for channel in CHANNELS:
        entries = indexes[channel]
        if not isinstance(entries, list):
            raise ValueError(f"{channel}: index must be a list")
        # The bridge is fetched by exact tag and survives the ordinary 30-entry
        # index window. Only older releases can be delta hops in the legacy feed.
        older = [r for r in entries if r.get("tag_name") != tags[channel] and
                 isinstance(r.get("published_at"), str) and r["published_at"] < anchors[channel]["published_at"]]
        legacy[channel] = [anchors[channel], *older][:30]
    if not isinstance(latest, dict) or not isinstance(latest.get("bootstrap"), dict):
        raise ValueError("latest index has no bootstrap release")
    legacy_latest = dict(latest)
    legacy_latest.update({c: legacy[c][0] for c in CHANNELS})
    return legacy, legacy_latest


def main():
    if len(sys.argv) != 6:
        raise SystemExit("usage: transition-firmware-index.py OUTDIR BRIDGE_DIR STABLE_BRIDGE TESTING_BRIDGE NIGHTLY_BRIDGE")
    out = Path(sys.argv[1])
    bridge_dir = Path(sys.argv[2])
    tags = dict(zip(CHANNELS, sys.argv[3:]))
    indexes = {c: json.loads((out / f"{c}.json").read_text()) for c in CHANNELS}
    latest = json.loads((out / "latest.json").read_text())
    bridges = {c: json.loads((bridge_dir / f"bridge-{c}.json").read_text()) for c in CHANNELS}
    legacy, legacy_latest = transition(indexes, latest, bridges, tags)
    v2 = out / "v2"
    v2.mkdir(exist_ok=True)
    for channel in CHANNELS:
        (v2 / f"{channel}.json").write_text(json.dumps(indexes[channel], indent=2) + "\n")
    (v2 / "latest.json").write_text(json.dumps(latest, indent=2) + "\n")
    (v2 / "bridge.json").write_text(json.dumps({"version": 1, "bridges": {c: legacy[c][0] for c in CHANNELS}}, indent=2) + "\n")
    for channel in CHANNELS:
        (out / f"{channel}.json").write_text(json.dumps(legacy[channel], indent=2) + "\n")
    (out / "latest.json").write_text(json.dumps(legacy_latest, indent=2) + "\n")


if __name__ == "__main__":
    main()

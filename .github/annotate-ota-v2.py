#!/usr/bin/env python3
"""Attach verified release-produced OTA capability metadata to v2 indexes."""
import functools
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_METADATA = 1024 * 1024
CHANNELS = ("stable", "testing", "nightly")


def read_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


@functools.lru_cache(maxsize=128)
def fetch_metadata(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(MAX_METADATA + 1)
    if len(data) > MAX_METADATA:
        raise ValueError("OTA metadata exceeds size limit")
    return data


def validate_policy(name, tag, policy):
    if not isinstance(policy, dict) or policy.get("schema") != 1:
        raise ValueError(f"{name}: invalid OTA schema")
    variant = policy.get("variant")
    if variant not in ("unu-mdb", "unu-dbc"):
        raise ValueError(f"{name}: invalid variant")
    requires = policy.get("requires")
    if not isinstance(requires, list) or not requires or any(not isinstance(x, str) or not x for x in requires) or len(set(requires)) != len(requires):
        raise ValueError(f"{name}: invalid capability requirements")
    implied = {"artifact.mender-v3"}
    if policy.get("kind") == "full":
        fmt = policy.get("payload_compression")
        if (name != f"librescoot-{variant}-{tag}.mender" or policy.get("artifact") != f"release-{tag}" or fmt not in ("gzip", "zstd")
                or policy.get("algorithm") or policy.get("base") is not None or policy.get("target") is not None):
            raise ValueError(f"{name}: inconsistent full-image metadata")
        implied.add(f"payload.{fmt}")
    elif policy.get("kind") == "delta":
        algorithm = policy.get("algorithm")
        ext = {"xdelta3": "delta", "hdiffpatch": "hdelta"}.get(algorithm)
        if ext is None or name != f"librescoot-{variant}-{tag}.{ext}" or policy.get("artifact") or policy.get("payload_compression"):
            raise ValueError(f"{name}: inconsistent delta algorithm")
        implied.add(f"delta.{algorithm}-v1")
        for key in ("base", "target"):
            endpoint = policy.get(key)
            if not isinstance(endpoint, dict) or not isinstance(endpoint.get("artifact"), str) or not endpoint["artifact"]:
                raise ValueError(f"{name}: invalid {key} identity")
            if not isinstance(endpoint.get("rootfs_sha256"), str) or not HEX.fullmatch(endpoint["rootfs_sha256"]):
                raise ValueError(f"{name}: invalid {key} checksum")
            fmt = endpoint.get("payload_compression")
            if fmt not in ("gzip", "zstd"):
                raise ValueError(f"{name}: unsupported {key} compression")
            implied.add(f"payload.{fmt}")
        if policy["target"]["artifact"] != f"release-{tag}":
            raise ValueError(f"{name}: delta target differs from release")
    else:
        raise ValueError(f"{name}: unknown OTA kind")
    if not implied.issubset(requires):
        raise ValueError(f"{name}: missing implied capabilities")


def annotate_release(release, backfill, fetch=fetch_metadata):
    if not isinstance(release, dict):
        return release
    tag = release.get("tag_name")
    assets = release.get("assets")
    if not isinstance(tag, str) or not isinstance(assets, list):
        raise ValueError("invalid release")
    by_name = {}
    for asset in assets:
        name = asset.get("name") if isinstance(asset, dict) else None
        if not isinstance(name, str) or name in by_name:
            raise ValueError(f"{tag}: invalid or duplicate asset")
        by_name[name] = asset
    metadata_name = f"librescoot-{tag}.ota-v2.json"
    source = by_name.get(metadata_name)
    documents = []
    if tag in backfill:
        documents.append(backfill[tag])
    if source is not None:
        parsed = urlparse(source.get("url") or "")
        if (parsed.scheme != "https" or parsed.hostname != "github.com" or
                parsed.path != f"/librescoot/librescoot/releases/download/{tag}/{metadata_name}" or parsed.query or parsed.fragment):
            raise ValueError(f"{tag}: invalid metadata URL")
        if not isinstance(source.get("sha256"), str) or not HEX.fullmatch(source["sha256"]) or not isinstance(source.get("size"), int) or source["size"] <= 0 or source["size"] > MAX_METADATA:
            raise ValueError(f"{tag}: missing metadata digest or size")
        data = fetch(source["url"])
        if len(data) != source["size"] or hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"{tag}: metadata digest or size mismatch")
        documents.append(read_json(data))
    attached = {}
    for doc in documents:
        if not isinstance(doc, dict) or doc.get("version") != 1 or doc.get("tag") != tag or not isinstance(doc.get("assets"), dict):
            raise ValueError(f"{tag}: invalid OTA metadata document")
        for name, record in doc["assets"].items():
            asset = by_name.get(name)
            if not isinstance(record, dict) or asset is None or record.get("size") != asset.get("size") or record.get("sha256") != asset.get("sha256"):
                raise ValueError(f"{tag}: metadata does not match release asset {name}")
            if not isinstance(record.get("sha256"), str) or not HEX.fullmatch(record["sha256"]) or not isinstance(record.get("size"), int) or record["size"] <= 0:
                raise ValueError(f"{tag}: invalid digest or size for {name}")
            validate_policy(name, tag, record.get("ota"))
            if name in attached and attached[name] != record["ota"]:
                raise ValueError(f"{tag}: conflicting metadata for {name}")
            attached[name] = record["ota"]
    for name, policy in attached.items():
        by_name[name]["ota"] = policy
    return release


def annotate_directory(out, backfill, fetch=fetch_metadata):
    for channel in CHANNELS:
        path = out / f"{channel}.json"
        releases = read_json(path.read_bytes())
        if not isinstance(releases, list):
            raise ValueError(f"{channel}: expected release list")
        for release in releases:
            annotate_release(release, backfill, fetch)
        path.write_text(json.dumps(releases, indent=2) + "\n")
    latest_path = out / "latest.json"
    latest = read_json(latest_path.read_bytes())
    if not isinstance(latest, dict):
        raise ValueError("invalid latest manifest")
    for channel in CHANNELS:
        if latest.get(channel) is not None:
            annotate_release(latest[channel], backfill, fetch)
    latest_path.write_text(json.dumps(latest, indent=2) + "\n")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: annotate-ota-v2.py V2_DIRECTORY BACKFILL_JSON")
    backfill = read_json(Path(sys.argv[2]).read_bytes())
    if not isinstance(backfill, dict):
        raise ValueError("invalid historical OTA metadata")
    annotate_directory(Path(sys.argv[1]), backfill)


if __name__ == "__main__":
    main()

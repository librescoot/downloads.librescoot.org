#!/usr/bin/env python3
"""Fail a deployment that does not serve the release index it built."""

import hashlib
import json
import os
import sys
import time
import urllib.request


def without_ota(value):
    if isinstance(value, list):
        return [without_ota(item) for item in value]
    if isinstance(value, dict):
        return {key: without_ota(item) for key, item in value.items() if key != "ota"}
    return value


def verify(base_url, expected_digests, fetch):
    manifest = fetch(f"{base_url}/releases/latest.json")
    if hashlib.sha256(manifest).hexdigest() != expected_digests["latest"]:
        raise ValueError("live latest.json differs from the built manifest")
    latest = json.loads(manifest)
    tags = []
    legacy_indexes = {}
    for channel in ("stable", "testing", "nightly"):
        release = latest.get(channel)
        data = fetch(f"{base_url}/releases/{channel}.json")
        if hashlib.sha256(data).hexdigest() != expected_digests[channel]:
            raise ValueError(f"live {channel}.json differs from the built index")
        entries = json.loads(data)
        legacy_indexes[channel] = entries
        if release is None:
            if entries:
                raise ValueError(f"live {channel}.json is not empty")
            continue
        tag = release["tag_name"]
        if not entries or entries[0]["tag_name"] != tag:
            raise ValueError(f"live {channel}.json does not start with {tag}")
        tags.append(tag)
    v2_names = ("v2_latest", "v2_stable", "v2_testing", "v2_nightly")
    if any(name in expected_digests for name in v2_names) or expected_digests.get("v2_bridge"):
        if not all(expected_digests.get(name) for name in v2_names):
            raise ValueError("incomplete expected v2 release indexes")
        v2_manifest = fetch(f"{base_url}/releases/v2/latest.json")
        if hashlib.sha256(v2_manifest).hexdigest() != expected_digests["v2_latest"]:
            raise ValueError("live v2 latest.json differs from the built manifest")
        v2_latest = json.loads(v2_manifest)
        if expected_digests.get("v2_bridge"):
            bridge_data = fetch(f"{base_url}/releases/v2/bridge.json")
            if hashlib.sha256(bridge_data).hexdigest() != expected_digests["v2_bridge"]:
                raise ValueError("live v2 bridge.json differs from the built index")
            bridges = json.loads(bridge_data)
            if bridges.get("version") != 1 or any(bridges.get("bridges", {}).get(c) != latest.get(c) for c in ("stable", "testing", "nightly")):
                raise ValueError("live v2 bridge identities differ from the legacy manifest")
        elif without_ota(v2_latest) != latest:
            raise ValueError("v2 without bridge pins must mirror legacy")
        tags = []
        for channel in ("stable", "testing", "nightly"):
            data = fetch(f"{base_url}/releases/v2/{channel}.json")
            if hashlib.sha256(data).hexdigest() != expected_digests[f"v2_{channel}"]:
                raise ValueError(f"live v2 {channel}.json differs from the built index")
            entries = json.loads(data)
            if not expected_digests.get("v2_bridge") and without_ota(entries) != legacy_indexes[channel]:
                raise ValueError(f"v2 {channel} without bridge pins must mirror legacy")
            release = v2_latest.get(channel)
            if release is None:
                if entries:
                    raise ValueError(f"live v2 {channel}.json is not empty")
                continue
            tag = release["tag_name"]
            if not entries or entries[0]["tag_name"] != tag:
                raise ValueError(f"live v2 {channel}.json does not start with {tag}")
            tags.append(tag)
    for route in ("/", "/en/"):
        html = fetch(f"{base_url}{route}").decode("utf-8")
        for tag in tags:
            if tag not in html:
                raise ValueError(f"live {route} does not show {tag}")
    return tags


def main():
    base_url = os.environ["SITE_URL"].rstrip("/")
    expected_digests = {name: os.environ[f"EXPECTED_{name.upper()}_SHA256"]
                        for name in ("latest", "stable", "testing", "nightly")}
    for name in ("v2_latest", "v2_stable", "v2_testing", "v2_nightly", "v2_bridge"):
        value = os.environ.get(f"EXPECTED_{name.upper()}_SHA256", "")
        if value:
            expected_digests[name] = value

    def fetch(url):
        request = urllib.request.Request(
            f"{url}?deployment={os.environ.get('GITHUB_RUN_ID', 'local')}-{time.time_ns()}",
            headers={"Cache-Control": "no-cache", "User-Agent": "librescoot-deploy-verification"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read()

    for attempt in range(48):
        try:
            tags = verify(base_url, expected_digests, fetch)
            print("Live release indexes and DE/EN pages verified:", ", ".join(tags))
            return 0
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"Live verification {attempt + 1}/48: {error}", flush=True)
            if attempt < 47:
                time.sleep(15)
    return 1


if __name__ == "__main__":
    sys.exit(main())

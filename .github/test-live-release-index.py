#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("verify_live", Path(__file__).with_name("verify-live-release-index.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LiveReleaseIndexTest(unittest.TestCase):
    def setUp(self):
        self.latest = {channel: {"tag_name": tag} for channel, tag in (
            ("stable", "v1.4.1"), ("testing", "testing-20261105T184531"),
            ("nightly", "nightly-20261105T034653"),
        )}
        self.files = {"/releases/latest.json": json.dumps(self.latest).encode()}
        for channel, release in self.latest.items():
            self.files[f"/releases/{channel}.json"] = json.dumps([release]).encode()
        html = " ".join(release["tag_name"] for release in self.latest.values()).encode()
        self.files.update({"/": html, "/en/": html})
        self.digests = {name: hashlib.sha256(self.files[f"/releases/{name}.json"]).hexdigest()
                        for name in ("latest", "stable", "testing", "nightly")}

    def verify(self):
        return module.verify("https://example.test", self.digests,
                             lambda url: self.files[url.removeprefix("https://example.test")])

    def test_matching_deployment(self):
        self.assertEqual(len(self.verify()), 3)

    def test_v2_index_and_site_are_verified_independently(self):
        v2 = {channel: {'tag_name': f'next-{channel}'} for channel in self.latest}
        self.files['/releases/v2/latest.json'] = json.dumps(v2).encode()
        self.files['/releases/v2/bridge.json'] = json.dumps({'version': 1, 'bridges': self.latest}).encode()
        for channel, release in v2.items():
            self.files[f'/releases/v2/{channel}.json'] = json.dumps([release]).encode()
        html = ' '.join(release['tag_name'] for release in v2.values()).encode()
        self.files.update({'/': html, '/en/': html})
        for name in ('latest', 'stable', 'testing', 'nightly', 'bridge'):
            self.digests[f'v2_{name}'] = hashlib.sha256(self.files[f'/releases/v2/{name}.json']).hexdigest()
        self.assertEqual(self.verify(), ['next-stable', 'next-testing', 'next-nightly'])
        self.files['/releases/v2/nightly.json'] = b'[]'
        with self.assertRaisesRegex(ValueError, 'v2 nightly.json'):
            self.verify()

    def test_v2_mirror_without_qualified_bridges(self):
        for name in ('latest', 'stable', 'testing', 'nightly'):
            self.files[f'/releases/v2/{name}.json'] = self.files[f'/releases/{name}.json']
            self.digests[f'v2_{name}'] = self.digests[name]
        self.assertEqual(len(self.verify()), 3)
        self.files['/releases/v2/latest.json'] = b'{"stable":{"tag_name":"v1.5.0"}}'
        self.digests['v2_latest'] = hashlib.sha256(self.files['/releases/v2/latest.json']).hexdigest()
        with self.assertRaisesRegex(ValueError, 'must mirror legacy'):
            self.verify()

    def test_partial_expected_v2_is_rejected(self):
        self.digests['v2_latest'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'incomplete expected v2'):
            self.verify()

    def test_old_manifest_after_green_deployment(self):
        self.files["/releases/latest.json"] = b'{"testing":{"tag_name":"testing-20261103T102714"}}'
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify()

    def test_stale_channel_index(self):
        self.files["/releases/testing.json"] = b'[{"tag_name":"testing-20261103T102714"}]'
        with self.assertRaisesRegex(ValueError, "testing.json"):
            self.verify()

    def test_stale_historical_asset(self):
        stale = [self.latest["stable"], {"tag_name": "v1.2.0", "assets": [{"sha256": "old"}]}]
        self.files["/releases/stable.json"] = json.dumps(stale).encode()
        with self.assertRaisesRegex(ValueError, "stable.json"):
            self.verify()

    def test_empty_channel_index(self):
        self.files["/releases/testing.json"] = b'[]'
        with self.assertRaisesRegex(ValueError, "testing.json"):
            self.verify()

    def test_stale_page(self):
        for route in ("/", "/en/"):
            with self.subTest(route=route):
                saved = self.files[route]
                self.files[route] = saved.replace(b"testing-20261105T184531", b"testing-20261103T102714")
                with self.assertRaisesRegex(ValueError, "does not show"):
                    self.verify()
                self.files[route] = saved

    def test_malformed_manifest(self):
        self.files["/releases/latest.json"] = b'not json'
        self.digests["latest"] = hashlib.sha256(self.files["/releases/latest.json"]).hexdigest()
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == "__main__":
    unittest.main()

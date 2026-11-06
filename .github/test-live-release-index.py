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
        self.digest = hashlib.sha256(self.files["/releases/latest.json"]).hexdigest()

    def verify(self):
        return module.verify("https://example.test", self.digest,
                             lambda url: self.files[url.removeprefix("https://example.test")])

    def test_matching_deployment(self):
        self.assertEqual(len(self.verify()), 3)

    def test_old_manifest_after_green_deployment(self):
        self.files["/releases/latest.json"] = b'{"testing":{"tag_name":"testing-20261103T102714"}}'
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify()

    def test_stale_channel_index(self):
        self.files["/releases/testing.json"] = b'[{"tag_name":"testing-20261103T102714"}]'
        with self.assertRaisesRegex(ValueError, "testing.json"):
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
        self.digest = hashlib.sha256(self.files["/releases/latest.json"]).hexdigest()
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == "__main__":
    unittest.main()

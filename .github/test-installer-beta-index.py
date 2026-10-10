#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('beta_index', Path(__file__).with_name('build-installer-beta-index.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def release(tag, **extra):
    return {
        'tag_name': tag,
        'prerelease': True,
        'draft': False,
        'html_url': f'https://github.com/librescoot/installer/releases/tag/{tag}',
        'assets': [{'name': 'installer.exe', 'size': 42, 'browser_download_url': 'https://example.invalid/installer.exe', 'digest': 'sha256:abc'}],
        **extra,
    }


class BetaIndexTests(unittest.TestCase):
    def choose(self, tags, stable='v1.4.3'):
        return module.select_beta({'tag_name': stable}, [release(tag) for tag in tags])

    def test_numeric_beta_order_not_api_order(self):
        self.assertEqual(self.choose(['v1.4.4-beta.9', 'v1.4.4-beta.10', 'v1.4.4-beta.2'])['tag_name'], 'v1.4.4-beta.10')

    def test_highest_version_not_latest_publication(self):
        self.assertEqual(self.choose(['v1.5.0-beta.1', 'v1.4.4-beta.99'])['tag_name'], 'v1.5.0-beta.1')

    def test_stable_supersedes_its_prereleases(self):
        self.assertIsNone(self.choose(['v1.4.4-beta.10'], stable='v1.4.4'))
        self.assertIsNone(self.choose(['v1.4.3-beta.10', 'v1.3.9-beta.99']))

    def test_newer_core_is_eligible(self):
        self.assertEqual(self.choose(['v1.4.5-beta.1'], stable='v1.4.4')['tag_name'], 'v1.4.5-beta.1')

    def test_invalid_tags_and_other_prereleases_are_ignored(self):
        self.assertIsNone(self.choose(['nightly-20261009', 'v1.4.4-rc.1', 'v1.04.4-beta.1', 'v1.4.4-beta.01']))

    def test_drafts_and_empty_or_stable_releases_are_ignored(self):
        candidates = [release('v1.5.0-beta.1', draft=True), release('v1.5.0-beta.2', assets=[]), release('v1.5.0-beta.3', prerelease=False)]
        self.assertIsNone(module.select_beta({'tag_name': 'v1.4.3'}, candidates))

    def test_assets_and_release_notes_are_preserved(self):
        result = module.select_beta({'tag_name': 'v1.4.3'}, [release('v1.4.4-beta.1', body='Beta notes')])
        self.assertEqual(result['assets'][0]['sha256'], 'abc')
        self.assertEqual(result['release_notes'], 'Beta notes')
        self.assertEqual(result['release_url'], 'https://github.com/librescoot/installer/releases/tag/v1.4.4-beta.1')

    def test_invalid_stable_baseline_fails_the_build(self):
        for tag in ['', 'nightly', 'v1.4.4-beta.1']:
            with self.assertRaises(ValueError):
                module.select_beta({'tag_name': tag}, [])


if __name__ == '__main__':
    unittest.main()

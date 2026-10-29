#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('beta_validation', Path(__file__).with_name('test-installer-beta.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def asset(name):
    return {'name': name, 'url': f'https://example.invalid/{name}'}


class BetaValidationTests(unittest.TestCase):
    def setUp(self):
        self.stable = {'tag_name': 'v1.4.4'}
        self.downloads = [asset(name) for name in (
            'Installer-linux.AppImage', 'Installer-linux.tar.gz',
            'Installer-macos.dmg', 'Installer-windows.exe', 'Installer-windows.zip',
        )]
        self.beta = {
            'tag_name': 'v1.4.5-beta.1',
            'release_url': 'https://example.invalid/releases/tag/v1.4.5-beta.1',
            'assets': self.downloads + [asset('reset-dbc-installer-state.sh'), asset('SHA256SUMS')],
        }
        self.html = ('<p><a href="/releases/tag/v1.4.4">Stable</a></p>'
                     '<details class="installer-beta">Installer v1.4.5-beta.1'
                     f'<a href="{self.beta["release_url"]}">Notes</a>'
                     + ''.join(f'<a href="{a["url"]}">Download</a>' for a in self.downloads)
                     + '</details>')

    def test_auxiliary_assets_do_not_require_installer_buttons(self):
        module.validate_page(self.html, self.stable, self.beta)
        self.assertEqual(module.installer_downloads(self.beta['assets']), self.downloads)

    def test_every_platform_download_is_still_required(self):
        for download in self.downloads:
            with self.subTest(name=download['name']), self.assertRaisesRegex(AssertionError, 'Missing beta download'):
                module.validate_page(self.html.replace(download['url'], ''), self.stable, self.beta)

    def test_only_auxiliary_assets_is_not_a_valid_installer_listing(self):
        self.beta['assets'] = [asset('reset-dbc-installer-state.sh'), asset('SHA256SUMS')]
        with self.assertRaisesRegex(AssertionError, 'supported installer download'):
            module.validate_page(self.html, self.stable, self.beta)

    def test_stable_link_remains_required(self):
        with self.assertRaisesRegex(AssertionError, 'Stable release link'):
            module.validate_page(self.html.replace('/releases/tag/v1.4.4', ''), self.stable, self.beta)

    def test_no_beta_preserves_stable_only_page(self):
        module.validate_page('<p><a href="/releases/tag/v1.4.4">Stable</a></p>', self.stable, None)
        with self.assertRaisesRegex(AssertionError, 'No eligible newer beta'):
            module.validate_page(self.html, self.stable, None)


if __name__ == '__main__':
    unittest.main()

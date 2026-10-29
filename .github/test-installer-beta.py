#!/usr/bin/env python3
"""Check the generated beta entry in the built German/English site."""
import json
from pathlib import Path


def installer_downloads(assets):
    formats = {
        'linux': ('.appimage', '.tar.gz', '.tgz'),
        'macos': ('.dmg',),
        'windows': ('.exe', '.zip'),
    }
    return [asset for asset in assets if any(
        platform in asset['name'].lower() and asset['name'].lower().endswith(suffixes)
        for platform, suffixes in formats.items()
    )]


def validate_page(html, stable, beta):
    assert f'/releases/tag/{stable["tag_name"]}' in html, 'Stable release link must remain present'
    if beta is None:
        assert '<details class="installer-beta">' not in html, 'No eligible newer beta should be listed'
        return
    version = beta['tag_name'].removeprefix('v')
    assert beta['release_url'] in html
    assert f'Installer v{version}' in html
    beta_start = html.index('<details class="installer-beta">')
    stable_notes = html.index(f'/releases/tag/{stable["tag_name"]}')
    assert beta_start > html.index('</p>', stable_notes), 'Beta must follow stable release notes and help links'
    downloads = installer_downloads(beta['assets'])
    assert downloads, 'Beta must contain a supported installer download'
    for asset in downloads:
        assert asset['url'] in html, f'Missing beta download: {asset["name"]}'


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    beta = json.loads((root / 'src/releases/installer-beta.json').read_text())
    stable = json.loads((root / 'src/releases/installer.json').read_text())
    for page in ['_site/index.html', '_site/en/index.html']:
        validate_page((root / page).read_text(), stable, beta)
    print('OK: generated beta downloads in both languages; stable retained.')

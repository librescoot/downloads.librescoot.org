#!/usr/bin/env python3
"""Check the generated beta entry in the built German/English site."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
beta = json.loads((root / 'src/releases/installer-beta.json').read_text())
stable = json.loads((root / 'src/releases/installer.json').read_text())
for page, warning in [('_site/index.html', 'echter Hardware'), ('_site/en/index.html', 'physical hardware validation')]:
    html = (root / page).read_text()
    assert f'/releases/tag/{stable["tag_name"]}' in html, 'Stable release link must remain present'
    if beta is None:
        assert ' — Beta' not in html, 'No eligible newer beta should be listed'
        continue
    version = beta['tag_name'].removeprefix('v')
    assert beta['release_url'] in html
    assert f'Installer v{version} — Beta' in html
    assert warning in html
    for asset in beta['assets']:
        assert asset['url'] in html, f'Missing beta download: {asset["name"]}'
print('OK: generated beta downloads in both languages; stable retained.')

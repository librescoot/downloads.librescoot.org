#!/usr/bin/env python3
"""Check the beta entry in an already-built German/English site."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
beta = json.loads((root / 'src/_data/installerBeta.json').read_text())
stable = json.loads((root / 'src/releases/installer.json').read_text())
assert '-beta.' in beta['version']
assert beta['releaseUrl'] == f'https://github.com/librescoot/installer/releases/tag/v{beta["version"]}'
for page, warning in [('_site/index.html', 'echter Hardware'), ('_site/en/index.html', 'physical hardware validation')]:
    html = (root / page).read_text()
    assert beta['releaseUrl'] in html
    assert f'Installer v{beta["version"]} — Beta' in html
    assert warning in html
    assert f'/releases/tag/{stable["tag_name"]}' in html, 'Stable release link must remain present'
print('OK: separate beta entry and validation warnings in both languages; stable retained.')

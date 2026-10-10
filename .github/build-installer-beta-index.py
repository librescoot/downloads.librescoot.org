#!/usr/bin/env python3
"""Select the highest installer beta version newer than the stable release."""
import json
import re
import sys
from pathlib import Path

TAG = re.compile(r'^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-beta\.(0|[1-9]\d*))?(?:\+[0-9A-Za-z.-]+)?$')


def version(tag):
    match = TAG.fullmatch(tag or '')
    if not match:
        return None
    return tuple(int(part) for part in match.groups()[:3]), match[4]


def select_beta(stable, releases):
    baseline = version(stable.get('tag_name'))
    if baseline is None or baseline[1] is not None:
        raise ValueError('A valid stable installer version is required')
    candidates = []
    for release in releases:
        parsed = version(release.get('tag_name'))
        if (parsed is None or parsed[1] is None or parsed[0] <= baseline[0]
                or release.get('draft') or not release.get('prerelease')
                or not release.get('assets')):
            continue
        candidates.append((parsed[0] + (int(parsed[1]),), release))
    if not candidates:
        return None
    release = max(candidates, key=lambda item: item[0])[1]
    return {
        'tag_name': release['tag_name'],
        'published_at': release.get('published_at'),
        'release_url': release['html_url'],
        'release_notes': release.get('body') or '',
        'assets': [{
            'name': asset['name'],
            'size': asset['size'],
            'sha256': (asset.get('digest') or '').removeprefix('sha256:') or None,
            'url': asset['browser_download_url'],
        } for asset in release['assets']],
    }


if __name__ == '__main__':
    stable, releases, output = map(Path, sys.argv[1:])
    output.write_text(json.dumps(select_beta(json.loads(stable.read_text()), json.loads(releases.read_text())), indent=2) + '\n')

#!/usr/bin/env python3
"""Build an additive OTA-v2 index from verified, immutable release descriptors."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

HEX = re.compile(r'^[0-9a-f]{64}$')
STABLE = re.compile(r'^v[0-9]+\.[0-9]+\.[0-9]+$')
TESTING = re.compile(r'^testing-[0-9]{8}T[0-9]{6}$')


def release_version(release):
    return release['tag_name'].removeprefix('canary-')


def channel(release, feed='releases'):
    if release.get('draft'):
        return None
    canary = release['tag_name'].startswith('canary-')
    if canary != (feed == 'canary'):
        return None
    version = release_version(release)
    if (canary or not release['prerelease']) and STABLE.fullmatch(version):
        return 'stable'
    if release['prerelease'] and TESTING.fullmatch(version):
        return 'testing'
    return None


def validate_artifact(a):
    expected = hashlib.sha256(f'{a["variant_id"]}\n{a["artifact_name"]}\n{a["manifest_sha256"]}\n{a["header_sha256"]}\n'.encode()).hexdigest()
    if a['id'] != expected or a['variant_id'] not in ['unu-mdb', 'unu-dbc'] or a['variant_id'] not in a['device_types']:
        raise ValueError('invalid artifact identity/variant')
    for field in ['manifest_sha256', 'header_sha256', 'rootfs_sha256', 'payload_tar_sha256']:
        if not HEX.fullmatch(a[field]):
            raise ValueError('invalid artifact digest')
    if a['payload_tar_size'] <= 0 or a['artifact_name'] != 'release-' + a['version'] or a['full']['size'] <= 0 or not HEX.fullmatch(a['full']['sha256']):
        raise ValueError('invalid artifact name/full object')


def build(releases, documents, feed='releases'):
    artifacts, edges = {}, {}
    for doc in documents:
        if doc['schema_version'] != 2:
            raise ValueError('unsupported descriptor schema')
        for artifact in doc['artifacts']:
            validate_artifact(artifact)
            old = artifacts.get(artifact['id'])
            if old is not None and old != artifact:
                raise ValueError('conflicting immutable artifact')
            artifacts[artifact['id']] = artifact
        for edge in doc['deltas']:
            key = edge['source'], edge['target']
            old = edges.get(key)
            if old is not None and old != edge:
                raise ValueError('conflicting immutable delta')
            edges[key] = edge
    for edge in edges.values():
        source, target = artifacts[edge['source']], artifacts[edge['target']]
        if source['id'] == target['id'] or source['variant_id'] != target['variant_id'] or edge['size'] <= 0 or not HEX.fullmatch(edge['sha256']):
            raise ValueError('invalid delta')
    targets = {'stable': {}, 'testing': {}}
    ordered = sorted(releases, key=lambda r: r['published_at'], reverse=True)
    # A release without v2 descriptors remains a legacy-only release. Never
    # silently redirect its channel to an older v2 target.
    for ch in targets:
        for variant in ['unu-mdb', 'unu-dbc']:
            for release in ordered:
                if channel(release, feed) != ch:
                    continue
                name = f'librescoot-{variant}-{release_version(release)}.mender'
                if not any(a['name'] == name for a in release['assets']):
                    continue
                matches = [a for a in artifacts.values() if a['variant_id'] == variant and a['version'] == release_version(release)]
                if len(matches) > 1:
                    raise ValueError('ambiguous target version')
                if matches and matches[0].get('updater_protocol') == 2:
                    targets[ch][variant] = matches[0]['id']
                break
    # Keep only objects in the bounded descriptor window. Full fallback is
    # always attached to the selected artifact, never inferred from its name.
    result = dict(schema_version=2, targets=targets,
                  artifacts=sorted(artifacts.values(), key=lambda a: a['id']),
                  deltas=sorted(edges.values(), key=lambda e: (e['source'], e['target'])))
    if len(result['artifacts']) > 512 or len(result['deltas']) > 2048:
        raise ValueError('catalog object limit exceeded')
    result['revision'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('releases', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--feed', choices=['releases', 'canary'], default='releases')
    args = parser.parse_args()
    releases = json.loads(args.releases.read_text())
    documents = []
    selected = []
    for ch in ['stable', 'testing']:
        selected.extend(sorted([r for r in releases if channel(r, args.feed) == ch], key=lambda r: r['published_at'], reverse=True)[:10])
    for release in selected:
        for asset in release['assets']:
            if not (asset['name'].startswith('ota-v2-') or ('-from-' in asset['name'] and '-to-' in asset['name'])) or not asset['name'].endswith('.json'):
                continue
            if asset['size'] > 1024 * 1024:
                raise ValueError('oversized OTA descriptor')
            checksum = asset.get('digest', '')
            if not checksum.startswith('sha256:'):
                raise ValueError('OTA descriptor has no digest')
            with urllib.request.urlopen(asset['browser_download_url'], timeout=120) as response:
                data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != checksum[7:]:
                raise ValueError('OTA descriptor checksum mismatch')
            doc = json.loads(data)
            # Transfer objects must refer to retained GitHub release assets,
            # including reverse deltas stored with their newer source release.
            known = {a['browser_download_url']: a for r in releases for a in r['assets']}
            objects = [a['full'] for a in doc['artifacts']] + doc['deltas']
            for obj in objects:
                remote = known.get(obj['url'])
                if remote is None or remote['size'] != obj['size'] or remote.get('digest') != 'sha256:' + obj['sha256']:
                    raise ValueError('descriptor references missing/changed transfer object')
            documents.append(doc)
    result = build(releases, documents, args.feed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    temporary.replace(args.output)


if __name__ == '__main__':
    main()

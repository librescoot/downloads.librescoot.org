#!/usr/bin/env python3
import copy
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

path = Path(__file__).with_name('transition-firmware-index.py')
spec = importlib.util.spec_from_file_location('transition_firmware_index', path)
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)

TAGS = {'stable': 'v1.4.3', 'testing': 'testing-20261115T100000', 'nightly': 'nightly-20261115T100000'}


def bridge(channel):
    tag = TAGS[channel]
    return {
        'tag_name': tag, 'draft': False, 'prerelease': channel != 'stable',
        'published_at': '2026-11-15T10:00:00Z',
        'assets': [{
            'name': f'librescoot-unu-{board}-{tag}.mender', 'size': 100,
            'digest': 'sha256:' + 'a' * 64,
            'browser_download_url': f'https://github.com/librescoot/librescoot/releases/download/{tag}/librescoot-unu-{board}-{tag}.mender',
        } for board in ('mdb', 'dbc')],
    }


def entry(tag, date):
    return {'tag_name': tag, 'published_at': date, 'prerelease': False, 'assets': []}


class TransitionTest(unittest.TestCase):
    def setUp(self):
        self.bridges = {c: bridge(c) for c in TAGS}
        self.indexes = {c: [entry(f'{c}-future', '2026-11-16T00:00:00Z'),
                             entry(TAGS[c], '2026-11-15T10:00:00Z'),
                             entry(f'{c}-old', '2026-11-01T00:00:00Z')]
                        for c in TAGS}
        self.latest = {c: self.indexes[c][0] for c in TAGS}
        self.latest['bootstrap'] = {'tag_name': 'v1.3.0'}

    def test_each_legacy_feed_is_pinned_and_v2_data_stays_unmodified(self):
        before = copy.deepcopy(self.indexes), copy.deepcopy(self.latest)
        legacy, latest = index.transition(self.indexes, self.latest, self.bridges, TAGS)
        for channel, tag in TAGS.items():
            self.assertEqual([e['tag_name'] for e in legacy[channel]], [tag, f'{channel}-old'])
            self.assertEqual(latest[channel]['tag_name'], tag)
            self.assertEqual(legacy[channel][0]['assets'][0]['sha256'], 'a' * 64)
        self.assertEqual(latest['bootstrap'], {'tag_name': 'v1.3.0'})
        self.assertEqual((self.indexes, self.latest), before)

    def test_bridge_survives_falling_out_of_latest_30(self):
        self.indexes['nightly'] = [entry('nightly-future', '2026-12-20T00:00:00Z')]
        legacy, _ = index.transition(self.indexes, self.latest, self.bridges, TAGS)
        self.assertEqual([e['tag_name'] for e in legacy['nightly']], [TAGS['nightly']])

    def test_cli_writes_v2_and_legacy_as_one_generation(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'out'
            bridge_dir = Path(root) / 'bridges'
            out.mkdir(); bridge_dir.mkdir()
            for channel in TAGS:
                (out / f'{channel}.json').write_text(json.dumps(self.indexes[channel]))
                (bridge_dir / f'bridge-{channel}.json').write_text(json.dumps(self.bridges[channel]))
            (out / 'latest.json').write_text(json.dumps(self.latest))
            subprocess.run(['python3', str(path), str(out), str(bridge_dir), *TAGS.values()], check=True)
            for channel in TAGS:
                self.assertEqual(json.loads((out / 'v2' / f'{channel}.json').read_text()), self.indexes[channel])
                self.assertEqual(json.loads((out / f'{channel}.json').read_text())[0]['tag_name'], TAGS[channel])
            self.assertEqual(json.loads((out / 'v2/latest.json').read_text()), self.latest)
            manifest = json.loads((out / 'v2/bridge.json').read_text())
            self.assertEqual(manifest['version'], 1)
            self.assertEqual({c: manifest['bridges'][c]['tag_name'] for c in TAGS}, TAGS)

    def test_unpinned_v2_mirrors_gzip_legacy_without_bridge_manifest(self):
        mirror = path.with_name('prepare-v2-mirror.sh')
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            for name in ('latest', 'stable', 'testing', 'nightly'):
                (out / f'{name}.json').write_text(f'{name} fixture')
            env = {**os.environ, 'STABLE_BRIDGE_TAG': '', 'TESTING_BRIDGE_TAG': '', 'NIGHTLY_BRIDGE_TAG': ''}
            subprocess.run(['bash', str(mirror), str(out)], env=env, check=True)
            for name in ('latest', 'stable', 'testing', 'nightly'):
                self.assertEqual((out / f'{name}.json').read_bytes(), (out / 'v2' / f'{name}.json').read_bytes())
            self.assertFalse((out / 'v2/bridge.json').exists())
            (out / 'v2/bridge.json').write_text('stale')
            result = subprocess.run(['bash', str(mirror), str(out)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((out / 'v2/bridge.json').read_text(), 'stale')

    def test_bridge_configuration_fails_closed_after_zstd_publication(self):
        guard = path.with_name('check-ota-bridge-config.sh')
        base_env = {**os.environ, 'STABLE_BRIDGE_TAG': '', 'TESTING_BRIDGE_TAG': '', 'NIGHTLY_BRIDGE_TAG': ''}
        gzip_only = [{'assets': [{'name': 'firmware.mender'}]}]
        zstd_release = [{'assets': [{'name': 'librescoot-v1.5.0.ota-zstd.json'}]}]
        cases = [(gzip_only, {}, 0), (zstd_release, {}, 1),
                 (gzip_only, {'STABLE_BRIDGE_TAG': 'v1.4.3'}, 1),
                 (zstd_release, {'STABLE_BRIDGE_TAG': TAGS['stable'], 'TESTING_BRIDGE_TAG': TAGS['testing'],
                                 'NIGHTLY_BRIDGE_TAG': TAGS['nightly']}, 0)]
        for releases, env, expected in cases:
            with self.subTest(releases=releases, env=env):
                result = subprocess.run(['bash', str(guard)], input=json.dumps(releases), text=True,
                                        capture_output=True, env={**base_env, **env})
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_never_exposes_zstd_marked_releases_to_legacy(self):
        future = self.indexes['nightly'][0]
        future['assets'] = [{'name': 'librescoot-nightly-future.ota-zstd.json'}]
        legacy, _ = index.transition(self.indexes, self.latest, self.bridges, TAGS)
        self.assertNotIn(future, legacy['nightly'])
        self.indexes['nightly'][2]['assets'] = [{'name': 'librescoot-nightly-old.ota-zstd.json'}]
        with self.assertRaisesRegex(ValueError, 'zstd-only'):
            index.transition(self.indexes, self.latest, self.bridges, TAGS)
        self.indexes['nightly'][2]['assets'] = []
        self.bridges['nightly']['assets'].append({'name': 'librescoot-nightly-bridge.ota-zstd.json'})
        with self.assertRaisesRegex(ValueError, 'zstd-only'):
            index.transition(self.indexes, self.latest, self.bridges, TAGS)

    def test_refuses_partial_or_incomplete_bridges(self):
        cases = []
        x = copy.deepcopy(self.bridges); x['nightly']['draft'] = True; cases.append(x)
        x = copy.deepcopy(self.bridges); x['stable']['prerelease'] = True; cases.append(x)
        x = copy.deepcopy(self.bridges); x['testing']['assets'].pop(); cases.append(x)
        x = copy.deepcopy(self.bridges); x['testing']['assets'][0]['digest'] = None; cases.append(x)
        x = copy.deepcopy(self.bridges); x['testing']['assets'][0]['browser_download_url'] = 'https://example.org/image'; cases.append(x)
        x = copy.deepcopy(self.bridges); x['testing']['assets'].append(x['testing']['assets'][0]); cases.append(x)
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                index.transition(self.indexes, self.latest, invalid, TAGS)
        with self.assertRaises(ValueError):
            index.transition(self.indexes, self.latest, self.bridges, {'stable': 'v1.4.3'})
        with self.assertRaises(ValueError):
            index.transition(self.indexes, {}, self.bridges, TAGS)


if __name__ == '__main__':
    unittest.main()

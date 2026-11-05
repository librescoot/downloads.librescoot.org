import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

spec = importlib.util.spec_from_file_location('catalog', Path(__file__).with_name('build-ota-catalog.py'))
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def artifact(version, variant='unu-mdb'):
    a = dict(variant_id=variant, version=version, artifact_name='release-' + version,
             device_types=[variant], manifest_sha256='a' * 64, header_sha256='b' * 64,
             rootfs_sha256='c' * 64, payload_tar_sha256='d' * 64, payload_tar_size=2048,
             full=dict(url='https://example/image.mender', size=1000, sha256='e' * 64))
    a['id'] = hashlib.sha256(f'{variant}\nrelease-{version}\n{"a" * 64}\n{"b" * 64}\n'.encode()).hexdigest()
    return a


class IndexTests(unittest.TestCase):
    def test_board_targets_and_legacy_only_new_release(self):
        a, b = artifact('v1.4.1'), artifact('v1.4.0', 'unu-dbc')
        def release(tag, board):
            return dict(tag_name=tag, prerelease=False, published_at=tag,
                        assets=[dict(name=f'librescoot-{board}-{tag}.mender')])
        releases = [release('v1.4.1', 'unu-mdb'), release('v1.4.0', 'unu-dbc')]
        doc = dict(schema_version=2, artifacts=[a, b], deltas=[])
        index = catalog.build(releases, [doc])
        self.assertEqual(index['targets']['stable'], {'unu-mdb': a['id'], 'unu-dbc': b['id']})
        releases.append(release('v1.4.2', 'unu-mdb'))
        self.assertNotIn('unu-mdb', catalog.build(releases, [doc])['targets']['stable'])
        self.assertEqual(index, catalog.build(releases[:2], [doc]))

    def test_prerelease_never_stable(self):
        self.assertIsNone(catalog.channel(dict(tag_name='v1.4.2-beta.1', prerelease=True)))
        self.assertIsNone(catalog.channel(dict(tag_name='v1.4.2-beta.1', prerelease=False)))

    def test_legacy_stable_index_excludes_beta_tags(self):
        script = Path(__file__).with_name('generate-release-index.sh').read_text()
        start = script.index('[.[] | select(.tag_name | startswith($prefix))')
        end = script.index("' >", start)
        releases = [dict(tag_name=tag, prerelease=pre, published_at=date, assets=[]) for tag, pre, date in [
            ('v1.4.1', False, '2026-01-01'), ('v1.4.2-beta.1', True, '2026-01-02'),
            ('v1.4.2-beta.2', False, '2026-01-03')]]
        result = subprocess.run(['jq', '--arg', 'prefix', 'v', '--argjson', 'limit', '30', script[start:end]],
                                input=json.dumps(releases), text=True, capture_output=True, check=True)
        self.assertEqual([r['tag_name'] for r in json.loads(result.stdout)], ['v1.4.1'])

    def test_conflicting_identity_rejected(self):
        a = artifact('v1.4.1')
        b = copy.deepcopy(a)
        b['full']['sha256'] = 'f' * 64
        with self.assertRaises(ValueError):
            catalog.build([], [dict(schema_version=2, artifacts=[a, b], deltas=[])])


if __name__ == '__main__':
    unittest.main()

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).with_name('annotate-ota-v2.py')
spec = importlib.util.spec_from_file_location('annotate_ota', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.tag = 'v1.4.3'
        self.name = 'librescoot-unu-mdb-v1.4.3.mender'
        self.digest = 'a' * 64
        self.policy = {'schema': 1, 'kind': 'full', 'variant': 'unu-mdb', 'artifact': 'release-v1.4.3',
                       'payload_compression': 'gzip', 'requires': ['artifact.mender-v3', 'payload.gzip']}
        self.record = {'size': 100, 'sha256': self.digest, 'ota': self.policy}
        self.doc = {'version': 1, 'tag': self.tag, 'assets': {self.name: self.record}}
        self.body = json.dumps(self.doc).encode()
        self.sidecar = f'librescoot-{self.tag}.ota-v2.json'
        self.release = {'tag_name': self.tag, 'assets': [
            {'name': self.name, 'size': 100, 'sha256': self.digest, 'url': 'https://example.org/image'},
            {'name': self.sidecar, 'size': len(self.body), 'sha256': hashlib.sha256(self.body).hexdigest(),
             'url': f'https://github.com/librescoot/librescoot/releases/download/{self.tag}/{self.sidecar}'},
        ]}

    def test_valid_sidecar_and_future_requirement(self):
        result = mod.annotate_release(copy.deepcopy(self.release), {}, lambda _: self.body)
        self.assertEqual(result['assets'][0]['ota'], self.policy)
        self.policy['requires'].append('future.codec-v1')
        mod.validate_policy(self.name, self.tag, self.policy)

    def test_missing_sidecar_leaves_ota_absent(self):
        self.release['assets'].pop()
        result = mod.annotate_release(self.release, {})
        self.assertNotIn('ota', result['assets'][0])

    def test_backfill_bound_to_exact_digest_and_size(self):
        self.release['assets'].pop()
        annotated = mod.annotate_release(copy.deepcopy(self.release), {self.tag: self.doc})
        self.assertEqual(annotated['assets'][0]['ota'], self.policy)
        self.release['assets'][0]['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'does not match'):
            mod.annotate_release(self.release, {self.tag: self.doc})

    def test_bad_sidecar_digest_or_url_fails(self):
        with self.assertRaisesRegex(ValueError, 'digest or size mismatch'):
            mod.annotate_release(copy.deepcopy(self.release), {}, lambda _: b'wrong')
        self.release['assets'][1]['url'] = 'https://elsewhere.example/sidecar'
        with self.assertRaisesRegex(ValueError, 'invalid metadata URL'):
            mod.annotate_release(self.release, {}, lambda _: self.body)

    def test_inconsistent_policy_and_missing_implied_capability_fail(self):
        self.policy['payload_compression'] = 'zstd'
        with self.assertRaisesRegex(ValueError, 'missing implied'):
            mod.validate_policy(self.name, self.tag, self.policy)
        self.policy['payload_compression'] = 'gzip'
        self.policy['variant'] = 'unu-dbc'
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            mod.validate_policy(self.name, self.tag, self.policy)

    def test_duplicate_keys_and_conflicting_sources_fail(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            mod.read_json(b'{"version":1,"version":2}')
        alternate = copy.deepcopy(self.doc)
        alternate['assets'][self.name]['ota']['requires'].append('future.codec-v1')
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            mod.annotate_release(copy.deepcopy(self.release), {self.tag: alternate}, lambda _: self.body)

    def test_all_documents_get_the_same_annotation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for channel in mod.CHANNELS:
                (root / f'{channel}.json').write_text(json.dumps([self.release]))
            (root / 'latest.json').write_text(json.dumps({c: self.release for c in mod.CHANNELS}))
            mod.annotate_directory(root, {}, lambda _: self.body)
            latest = json.loads((root / 'latest.json').read_text())
            for channel in mod.CHANNELS:
                self.assertEqual(latest[channel], json.loads((root / f'{channel}.json').read_text())[0])
                self.assertEqual(latest[channel]['assets'][0]['ota'], self.policy)


if __name__ == '__main__':
    unittest.main()

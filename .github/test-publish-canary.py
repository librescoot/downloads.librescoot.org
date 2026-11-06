import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublishTests(unittest.TestCase):
    def test_only_canary_data_branch_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            gh = work / 'gh'
            gh.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['GH_CALLS'], 'a') as f: f.write(json.dumps(args) + '\\n')
if '--input' in args:
    request = pathlib.Path(args[args.index('--input') + 1]).read_text()
    pathlib.Path(os.environ['GH_BODY']).write_text(request)
    print('{}')
elif any('/releases?' in a for a in args): print('[]')
elif any('/git/ref/' in a for a in args): print('{}')
else: sys.exit(1)
''')
            gh.chmod(0o755)
            calls, body = work / 'calls', work / 'body'
            subprocess.run(['bash', '.github/publish-canary-feed.sh'], cwd=ROOT, check=True, capture_output=True,
                           env={**os.environ, 'PATH': str(work) + ':' + os.environ['PATH'],
                                'GITHUB_REPOSITORY': 'owner/firmware', 'GITHUB_SHA': 'a' * 40,
                                'GH_CALLS': str(calls), 'GH_BODY': str(body)})
            request = json.loads(body.read_text())
            self.assertEqual(request['branch'], 'canary-feed')
            data = json.loads(base64.b64decode(request['content']))
            self.assertEqual(data['schema_version'], 2)
            self.assertEqual(data['targets'], {'stable': {}, 'testing': {}})
            writes = [json.loads(line) for line in calls.read_text().splitlines() if 'PUT' in line]
            self.assertEqual(len(writes), 1)
            self.assertIn('repos/owner/firmware/contents/updates/v2/canary.json', writes[0])


if __name__ == '__main__':
    unittest.main()

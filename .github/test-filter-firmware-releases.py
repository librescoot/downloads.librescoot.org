#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

jq_file = Path(__file__).with_name("filter-firmware-releases.jq")
releases = [
    {"tag_name": "nightly-20261101T121938", "draft": False},
    {"tag_name": "nightly-20261101T121938", "draft": True},
    {"tag_name": "nightly-20261101T140411", "draft": True},
    {"tag_name": "nightly-20261101T000858", "draft": False},
    {"tag_name": "testing-20261031T000000", "draft": False},
    {"tag_name": "v1.3.0", "draft": False},
]
result = subprocess.run(
    ["jq", "-f", str(jq_file)], input=json.dumps(releases), text=True,
    check=True, capture_output=True,
)
assert json.loads(result.stdout) == releases[3:]
print("Firmware release withdrawal and draft filtering passed")

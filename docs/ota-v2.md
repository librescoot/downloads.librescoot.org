# OTA v2 catalogs

The static catalogs are served as:

- `/updates/v2/releases.json`: regular stable/testing targets.
- `/updates/v2/canary.json`: isolated canary stable/testing targets.

`/releases/ota-v2.json` is a compatibility copy of the regular catalog. Legacy
`/releases/*.json` endpoints retain their channel selection and exclude canary
release tags.

The catalog generator accepts `--feed=releases` or `--feed=canary`. Canary
releases use GitHub tags `canary-<version>`, with full-image assets named by their
embedded version without that prefix. Their descriptors and full/delta assets
must have matching GitHub SHA256 digests. Descriptors provide old images as
possible reconstruction bases, but only the selected feed's release list can
choose a channel target. A source artifact is not automatically an offered target.

Targets must advertise updater protocol 2. A missing descriptor or capability
leaves the corresponding board without a v2 target. The generator does not
substitute an older target or copy a regular target into the canary feed.

Firmware publishers generate immutable descriptors after reconstructing the
proposed delta. The generator validates references against retained release
assets before publishing. It reads a bounded window of recent descriptors for
each feed and keeps their referenced bases and edges in the generated catalog.
The current release cleanup only removes nightlies; it does not remove regular
or canary stable/testing assets. Objects referenced by an offered route must not
be deleted manually while clients may still be using that route.

Run the offline tests with:

```sh
python3 .github/test-ota-catalog.py
```

`V2_DEST` overrides the output directory when exercising the generator locally;
`DEST` continues to select the legacy release-index output directory.

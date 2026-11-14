# Firmware release feeds

The legacy firmware indexes are `/releases/latest.json` and `/releases/<channel>.json`. The optional versioned indexes use the same JSON shape under `/releases/v2/`. `/releases/v2/bridge.json` records the exact immutable bridge release and asset digests for each channel.

Before the split is activated, v2 is a gzip-only mirror of legacy with no `bridge.json`. This lets a feed-aware bridge use v2 immediately after commit while blocking zstd-only publication.

The split is disabled until all three repository variables are set: `OTA_STABLE_BRIDGE_TAG`, `OTA_TESTING_BRIDGE_TAG` and `OTA_NIGHTLY_BRIDGE_TAG`. The stable tag must be `v1.4.3`; the others must be published Testing and Nightly tags. A partial configuration, missing release, unpublished bridge, missing board artifact or missing digest fails generation. The script fetches each bridge by exact tag, independently of the rolling release-list limit.

With the split active, the legacy per-channel lists stop at their respective bridge. Older entries remain available as possible delta hops, but no newer release is advertised there. The v2 lists carry the ordinary current releases. The downloads website displays the v2 latest versions; older installers continue to see the legacy bridge. The build verifies every live index and bridge manifest after deployment.

Zstd-only releases carry a `.ota-zstd.json` marker. If any such release is visible, index generation fails when bridge pins are missing, rather than exposing that release to legacy clients. Generation also rejects a marked release inside a legacy list.

The split must only be activated after the bridge artifacts are confirmed gzip-compatible, the necessary releases are retained, and both MDB and DBC have booted and committed a bridge in acceptance testing. A delta chain that merely reconstructs a bridge as an intermediate file is not a bridge boot. Do not replace or modify published bridge assets. Protect the Nightly bridge from release/tag cleanup for as long as any legacy client may need it.

A feed-aware updater switches only after its rootfs marker, running image and committed Mender identity agree and there is no unresolved activation. Once selected, v2 errors do not fall back to legacy, so v2 must be available before a feed-aware bridge is offered. Custom updater feeds are not changed.

The automatic legacy-feed bridge supports the stable v1.0.0 and later client line. Pre-v1.0 update-service versions that query GitHub Releases directly do not consult this index and are outside the automatic migration guarantee; they need separate migration or recovery.

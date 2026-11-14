# Firmware release feeds

The legacy firmware indexes are `/releases/latest.json` and `/releases/<channel>.json`. The optional versioned indexes use the same JSON shape under `/releases/v2/`. `/releases/v2/bridge.json` records the exact immutable bridge release and asset digests for each channel.

The split is disabled until all three repository variables are set: `OTA_STABLE_BRIDGE_TAG`, `OTA_TESTING_BRIDGE_TAG` and `OTA_NIGHTLY_BRIDGE_TAG`. The stable tag must be `v1.4.3`; the others must be published Testing and Nightly tags. A partial configuration, missing release, unpublished bridge, missing board artifact or missing digest fails generation. The script fetches each bridge by exact tag, independently of the rolling release-list limit.

With the split active, the legacy per-channel lists stop at their respective bridge. Older entries remain available as possible delta hops, but no newer release is advertised there. The v2 lists carry the ordinary current releases. The downloads website displays the v2 latest versions; older installers continue to see the legacy bridge. The build verifies every live index and bridge manifest after deployment.

The split must only be activated after the bridge artifacts are confirmed gzip-compatible, the necessary releases are retained, and both MDB and DBC have booted and committed a bridge in acceptance testing. A delta chain that merely reconstructs a bridge as an intermediate file is not a bridge boot. Do not replace or modify published bridge assets. Protect the Nightly bridge from release/tag cleanup for as long as any legacy client may need it.

A feed-aware updater switches only after its rootfs marker, running image and committed Mender identity agree and there is no unresolved activation. Until v2 exists, its 404 fallback remains on legacy. Custom updater feeds are not changed.

const fs = require("fs");
const path = require("path");

module.exports = function () {
  const file = path.join(__dirname, "..", "releases", "installer-beta.json");
  try {
    const release = JSON.parse(fs.readFileSync(file, "utf8"));
    return {
      version: (release?.tag_name || "").replace(/^v/, ""),
      releaseUrl: release?.release_url,
      assets: release?.assets || [],
    };
  } catch {
    return { version: null, assets: [] };
  }
};

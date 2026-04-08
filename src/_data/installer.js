const fs = require("fs");
const path = require("path");

module.exports = function () {
  const file = path.join(__dirname, "..", "releases", "installer.json");
  try {
    const release = JSON.parse(fs.readFileSync(file, "utf8"));
    return {
      version: (release.tag_name || "").replace(/^v/, ""),
      assets: release.assets || [],
    };
  } catch {
    return { version: null, assets: [] };
  }
};

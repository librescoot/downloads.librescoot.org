const fs = require("fs");
const path = require("path");

module.exports = function () {
  const dir = path.join(__dirname, "..", "releases");
  const channels = {};

  for (const ch of ["stable", "testing", "nightly"]) {
    const file = path.join(dir, `${ch}.json`);
    try {
      channels[ch] = JSON.parse(fs.readFileSync(file, "utf8"));
    } catch {
      channels[ch] = [];
    }
  }

  return channels;
};

const fs = require("fs");
const path = require("path");

module.exports = function () {
  const dir = path.join(__dirname, "..", "releases");
  try {
    const latest = JSON.parse(fs.readFileSync(path.join(dir, "latest.json"), "utf8"));
    return Object.fromEntries(["stable", "testing", "nightly"].map((ch) =>
      [ch, latest[ch] ? [latest[ch]] : []]));
  } catch {
    const channels = {};
    for (const ch of ["stable", "testing", "nightly"]) {
      try {
        channels[ch] = JSON.parse(fs.readFileSync(path.join(dir, `${ch}.json`), "utf8"));
      } catch {
        channels[ch] = [];
      }
    }
    return channels;
  }
};

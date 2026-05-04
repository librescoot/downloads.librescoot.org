module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/CNAME");
  eleventyConfig.addPassthroughCopy("src/releases");

  eleventyConfig.addFilter("fmt", function (bytes) {
    if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + " GB";
    if (bytes >= 1e6) return Math.round(bytes / 1e6) + " MB";
    if (bytes >= 1e3) return Math.round(bytes / 1e3) + " KB";
    return bytes + " B";
  });

  eleventyConfig.addFilter("fmtDate", function (iso) {
    return new Date(iso).toLocaleDateString("sv-SE", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  });

  eleventyConfig.addFilter("board", function (name) {
    if (name.indexOf("-dbc-") !== -1) return "dbc";
    if (name.indexOf("-mdb-") !== -1) return "mdb";
    return null;
  });

  // Categorize installer release assets by platform so templates can render
  // each platform's button without re-walking the asset list. Windows is split
  // into `windowsExe` (preferred portable single-file installer) and
  // `windowsZip` (legacy folder zip).
  eleventyConfig.addFilter("byPlatform", function (assets) {
    const out = { linux: null, macos: null, windowsExe: null, windowsZip: null };
    for (const a of assets || []) {
      const n = (a.name || "").toLowerCase();
      if (n.includes("linux") && (n.endsWith(".tar.gz") || n.endsWith(".tgz"))) {
        out.linux = a;
      } else if (n.includes("macos") && n.endsWith(".dmg")) {
        out.macos = a;
      } else if (n.includes("windows") && n.endsWith(".exe")) {
        out.windowsExe = a;
      } else if (n.includes("windows") && n.endsWith(".zip")) {
        out.windowsZip = a;
      }
    }
    return out;
  });

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
  };
};

module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/CNAME");
  eleventyConfig.addPassthroughCopy("src/releases");

  eleventyConfig.addFilter("fmt", function (bytes) {
    if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + " GB";
    if (bytes >= 1e6) return Math.round(bytes / 1e6) + " MB";
    if (bytes >= 1e3) return Math.round(bytes / 1e3) + " KB";
    return bytes + " B";
  });

  eleventyConfig.addFilter("fmtDate", function (iso, lang) {
    lang = lang || "en";
    if (lang === "de") {
      return new Date(iso).toLocaleDateString("sv-SE", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
    }
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  });

  eleventyConfig.addFilter("board", function (name) {
    if (name.indexOf("-dbc-") !== -1) return "dbc";
    if (name.indexOf("-mdb-") !== -1) return "mdb";
    return null;
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

const fs = require("fs");
const path = require("path");

// German state IDs to display names
const STATE_NAMES = {
  "baden-wuerttemberg": "Baden-W\u00FCrttemberg",
  "bayern": "Bayern",
  "berlin_brandenburg": "Berlin & Brandenburg",
  "bremen": "Bremen",
  "hamburg": "Hamburg",
  "hessen": "Hessen",
  "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
  "niedersachsen": "Niedersachsen (incl. Bremen)",
  "nordrhein-westfalen": "Nordrhein-Westfalen",
  "rheinland-pfalz": "Rheinland-Pfalz",
  "saarland": "Saarland",
  "sachsen-anhalt": "Sachsen-Anhalt",
  "sachsen": "Sachsen",
  "schleswig-holstein": "Schleswig-Holstein",
  "thueringen": "Th\u00FCringen",
};

module.exports = function () {
  const dir = path.join(__dirname, "..", "releases");

  function loadAssets(filename) {
    try {
      return JSON.parse(fs.readFileSync(path.join(dir, filename), "utf8"));
    } catch {
      return [];
    }
  }

  const osmAssets = loadAssets("osm-tiles.json");
  const valhallaAssets = loadAssets("valhalla-tiles.json");

  // Build lookup by state ID
  const osm = {};
  for (const a of osmAssets) {
    const m = a.name.match(/^tiles_(.+)\.mbtiles$/);
    if (m) osm[m[1]] = a;
  }

  const valhalla = {};
  for (const a of valhallaAssets) {
    const m = a.name.match(/^valhalla_tiles_(.+)\.tar$/);
    if (m) valhalla[m[1]] = a;
  }

  // Find newest updated_at across all assets
  const allDates = [...osmAssets, ...valhallaAssets]
    .map((a) => a.updated_at)
    .filter(Boolean);
  const updated = allDates.length
    ? allDates.reduce((a, b) => (a > b ? a : b))
    : null;

  // Merge into list, sorted by display name
  const ids = [...new Set([...Object.keys(osm), ...Object.keys(valhalla)])].sort();
  const states = ids.map((id) => ({
    id,
    name: STATE_NAMES[id] || id,
    osm: osm[id] || null,
    valhalla: valhalla[id] || null,
  }));

  return { updated, states };
};

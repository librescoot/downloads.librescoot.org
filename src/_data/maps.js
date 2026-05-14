const fs = require("fs");
const path = require("path");

// Region IDs paired with display names and the country bucket they
// render under. Order within each country is preserved on the page.
const REGIONS = [
  { id: "baden-wuerttemberg", name: "Baden-Württemberg", country: "de" },
  { id: "bayern", name: "Bayern", country: "de" },
  { id: "berlin_brandenburg", name: "Berlin & Brandenburg", country: "de" },
  { id: "bremen", name: "Bremen", country: "de" },
  { id: "hamburg", name: "Hamburg", country: "de" },
  { id: "hessen", name: "Hessen", country: "de" },
  { id: "mecklenburg-vorpommern", name: "Mecklenburg-Vorpommern", country: "de" },
  { id: "niedersachsen", name: "Niedersachsen (incl. Bremen)", country: "de" },
  { id: "nordrhein-westfalen", name: "Nordrhein-Westfalen", country: "de" },
  { id: "rheinland-pfalz", name: "Rheinland-Pfalz", country: "de" },
  { id: "saarland", name: "Saarland", country: "de" },
  { id: "sachsen", name: "Sachsen", country: "de" },
  { id: "sachsen-anhalt", name: "Sachsen-Anhalt", country: "de" },
  { id: "schleswig-holstein", name: "Schleswig-Holstein", country: "de" },
  { id: "thueringen", name: "Thüringen", country: "de" },
  { id: "netherlands", name: "Nederland", country: "nl" },
  { id: "belgium", name: "België", country: "be" },
  { id: "luxembourg", name: "Luxembourg", country: "lu" },
  { id: "ile-de-france", name: "Île-de-France", country: "fr" },
];

const COUNTRIES = [
  { id: "de", name: "Deutschland" },
  { id: "nl", name: "Nederland" },
  { id: "be", name: "België" },
  { id: "lu", name: "Luxembourg" },
  { id: "fr", name: "France" },
];

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

  const allDates = [...osmAssets, ...valhallaAssets]
    .map((a) => a.updated_at)
    .filter(Boolean);
  const updated = allDates.length
    ? allDates.reduce((a, b) => (a > b ? a : b))
    : null;

  const rowFor = (r) => ({
    id: r.id,
    name: r.name,
    osm: osm[r.id] || null,
    valhalla: valhalla[r.id] || null,
  });

  // Group known regions under their country bucket. Any unrecognised slugs
  // that appear in the release JSON fall through to an "Other" group so
  // they remain visible while we update REGIONS.
  const known = new Set(REGIONS.map((r) => r.id));
  const countries = COUNTRIES
    .map((c) => ({
      id: c.id,
      name: c.name,
      states: REGIONS.filter((r) => r.country === c.id).map(rowFor),
    }))
    .filter((c) => c.states.length > 0);

  const seen = new Set([...Object.keys(osm), ...Object.keys(valhalla)]);
  const orphans = [...seen]
    .filter((id) => !known.has(id))
    .sort()
    .map((id) => ({ id, name: id, osm: osm[id] || null, valhalla: valhalla[id] || null }));
  if (orphans.length) {
    countries.push({ id: "other", name: "Other", states: orphans });
  }

  return { updated, countries };
};

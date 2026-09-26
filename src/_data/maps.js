const fs = require("fs");
const path = require("path");
const catalog = require("./map-regions.json");

const countries = [
  { id: "DE", name: "Deutschland", nameEn: "Germany" },
  { id: "NL", name: "Nederland", nameEn: "Netherlands" },
  { id: "BE", name: "België", nameEn: "Belgium" },
  { id: "LU", name: "Luxembourg", nameEn: "Luxembourg" },
  { id: "FR", name: "France", nameEn: "France" },
  { id: "IT", name: "Italia", nameEn: "Italy" },
  { id: "ES", name: "España", nameEn: "Spain" },
  { id: "AT", name: "Österreich", nameEn: "Austria" },
  { id: "CH", name: "Schweiz", nameEn: "Switzerland" },
];

module.exports = function () {
  const dir = path.join(__dirname, "..", "releases");
  let regions;
  try {
    regions = JSON.parse(fs.readFileSync(path.join(dir, "maps-routing.json"), "utf8")).regions;
  } catch {
    // The generated manifest is absent during a fresh local checkout.
    const load = (file) => {
      try { return JSON.parse(fs.readFileSync(path.join(dir, file), "utf8")); }
      catch { return []; }
    };
    regions = {};
    for (const asset of load("osm-tiles.json")) {
      const match = /^tiles_(.+)\.mbtiles$/.exec(asset.name);
      if (match) (regions[match[1]] ||= {}).map = asset;
    }
    for (const asset of load("valhalla-tiles.json")) {
      const match = /^valhalla_tiles_(.+)\.tar(\.zst)?$/.exec(asset.name);
      if (!match) continue;
      const region = (regions[match[1]] ||= {});
      if (match[2]) (region.routing ||= {}).compressed = asset;
      else region.routing = { ...region.routing, ...asset };
    }
  }

  const known = new Set(catalog.map((r) => r.id));
  const row = (slug, info = {}) => {
    const meta = catalog.find((r) => r.id === slug);
    return {
      id: slug,
      name: info.name || meta?.name || slug,
      map: info.map || null,
      routing: info.routing || null,
      available: Boolean(info.map || info.routing),
    };
  };
  const grouped = countries.map((country) => ({
    ...country,
    states: catalog.filter((r) => r.country === country.id)
      .map((r) => row(r.id, regions[r.id])),
  }));
  const orphans = Object.keys(regions).filter((id) => !known.has(id)).sort()
    .map((id) => row(id, regions[id]));
  if (orphans.length) grouped.push({ id: "other", name: "Other", states: orphans });

  const dates = Object.values(regions).flatMap((r) =>
    [r.map?.updated_at, r.routing?.updated_at].filter(Boolean));
  return { updated: dates.length ? dates.sort().at(-1) : null, countries: grouped };
};

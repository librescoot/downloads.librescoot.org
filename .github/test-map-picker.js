const assert = require('node:assert/strict');
const { matchingRegion, mapFragment, parseMapFragment } = require('../src/_includes/map-picker.js');

const cases = [
  [{ country_code: 'de', state: 'Berlin' }, 'berlin_brandenburg'],
  [{ country_code: 'de', state: 'Brandenburg' }, 'berlin_brandenburg'],
  [{ country_code: 'de', state: 'Baden-Württemberg' }, 'baden-wuerttemberg'],
  [{ country_code: 'de', state: 'North Rhine-Westphalia' }, 'nordrhein-westfalen'],
  [{ country_code: 'de', state: 'Saxony-Anhalt' }, 'sachsen-anhalt'],
  [{ country_code: 'de', state: 'Saxony' }, 'sachsen'],
  [{ country_code: 'nl' }, 'netherlands'],
  [{ country_code: 'be' }, 'belgium'],
  [{ country_code: 'lu' }, 'luxembourg'],
  [{ country_code: 'fr', state: 'Île-de-France' }, 'ile-de-france'],
  [{ country_code: 'fr', state: 'Grand Est', county: 'Bas-Rhin' }, 'alsace'],
  [{ country_code: 'fr', state: 'Grand Est', county: 'Moselle' }, null],
  [{ country_code: 'es', state: 'Balearic Islands' }, 'islas-baleares'],
  [{ country_code: 'at', city: 'Graz', state: 'Styria' }, 'graz'],
  [{ country_code: 'at', state: 'Vienna' }, 'vienna'],
  [{ country_code: 'it', state: 'Lombardy' }, 'italy-nord-ovest'],
  [{ country_code: 'it', state: 'Tuscany' }, null],
];
for (const [address, expected] of cases) {
  assert.equal(matchingRegion(address), expected, JSON.stringify(address));
}
for (const [country, region] of [
  ['FR', 'alsace'], ['DE', 'berlin_brandenburg'], ['CH', 'zurich'], ['NL', null],
]) {
  const fragment = mapFragment(country, region);
  assert.deepEqual(parseMapFragment(fragment), { country, region });
}
assert.deepEqual(parseMapFragment('#maps/fr/ALSACE'), { country: 'FR', region: 'alsace' });
assert.equal(parseMapFragment('#maps'), null);
assert.equal(parseMapFragment('#firmware'), null);
assert.equal(parseMapFragment('#maps/FR/alsace/extra'), null);
console.log(`${cases.length} map location cases and fragment round-trips passed`);

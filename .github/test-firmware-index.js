const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const filename = path.join(__dirname, '../src/_data/firmware.js');
const source = fs.readFileSync(filename, 'utf8');
function load(v2) {
  const names = [];
  const fakeFs = {
    existsSync: (name) => v2 && name.endsWith('/v2/latest.json'),
    readFileSync: (name) => {
      names.push(name);
      return JSON.stringify({stable: {tag_name: name.includes('/v2/') ? 'v1.5.0' : 'v1.4.3'}});
    },
  };
  const context = {module: {exports: {}}, __dirname: '/site/src/_data',
    require: (name) => name === 'fs' ? fakeFs : require(name)};
  vm.runInNewContext(source, context, {filename});
  const result = context.module.exports();
  return {tag: result.stable[0].tag_name, name: names[0]};
}
assert.equal(load(false).tag, 'v1.4.3');
assert.equal(load(true).tag, 'v1.5.0');
console.log('Firmware page selects v2 latest only when published');

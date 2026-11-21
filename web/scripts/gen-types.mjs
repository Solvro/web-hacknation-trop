// Generate web/lib/types.ts from docs/contracts/schema.json (lead-owned contract).
// Usage: npm run types
import { compile } from 'json-schema-to-typescript';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, '../../docs/contracts/schema.json');
const out = path.resolve(here, '../lib/types.ts');
const schema = JSON.parse(fs.readFileSync(src, 'utf8'));
const defs = schema.$defs;
// Pydantic puts a `title` on every property; json-schema-to-typescript turns each into a named alias that collides
// with the model names (e.g. `Decision`). Keep titles only on the $defs themselves.
function stripTitles(node, keep) {
  if (Array.isArray(node)) return node.forEach((x) => stripTitles(x, false));
  if (!node || typeof node !== 'object') return;
  if (!keep && typeof node.title === 'string') delete node.title;
  for (const [k, v] of Object.entries(node)) {
    if (k === 'properties' && v && typeof v === 'object') for (const p of Object.values(v)) stripTitles(p, false);
    else stripTitles(v, false);
  }
}
for (const d of Object.values(defs)) stripTitles(d, true);
const root = {
  title: 'TropContracts',
  type: 'object',
  additionalProperties: false,
  properties: Object.fromEntries(Object.keys(defs).map((k) => [k, { $ref: `#/$defs/${k}` }])),
  $defs: defs,
};
const ts = await compile(root, 'TropContracts', {
  bannerComment: '/* AUTO-GENERATED from docs/contracts/schema.json by web/scripts/gen-types.mjs. Do not edit. */',
  additionalProperties: false,
  declareExternallyReferenced: true,
  unreachableDefinitions: true,
  strictIndexSignatures: false,
  format: true,
});
fs.writeFileSync(out, ts);
console.log('wrote', out, ts.split('\n').length, 'lines');

// Builds a small Asia basemap (TopoJSON) + label points from Natural Earth 1:50m (world-atlas).
// Run once (npm run basemap); outputs are committed: src/lib/basemap.json
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { feature } from "topojson-client";
import { topology } from "topojson-server";
import { presimplify, quantile, simplify } from "topojson-simplify";
import { geoCentroid, geoBounds } from "d3-geo";

const require = createRequire(import.meta.url);
const world = JSON.parse(readFileSync(require.resolve("world-atlas/countries-50m.json"), "utf8"));
const yamlText = readFileSync(new URL("../../config/countries.yaml", import.meta.url), "utf8");

// numeric code -> ISO3 for in-scope countries (tiny YAML parse: "  ISO: {name: X, numeric: "123", ...}")
const inScope = {};
for (const m of yamlText.matchAll(/^\s{2}([A-Z]{3}):\s*\{[^}]*numeric:\s*"(\d{3})"/gm)) inScope[m[2]] = m[1];

// Keep countries whose bounds touch the Asia window (context + in-scope).
const W = [42, -14, 152, 58];
const fc = feature(world, world.objects.countries);
const kept = fc.features.filter((f) => {
  const [[x0, y0], [x1, y1]] = geoBounds(f);
  return x1 >= W[0] && x0 <= W[2] && y1 >= W[1] && y0 <= W[3] && !(x0 < -150 && x1 > 150);
});
for (const f of kept) {
  f.properties = { n: f.properties.name };
  if (inScope[f.id]) f.properties.iso = inScope[f.id];
}

// Label points: geographic centroid, with a few hand overrides where the centroid falls in the sea.
const overrides = { MYS: [102.2, 4.0], IDN: [113.5, -1.5], PHL: [122.5, 12.0], JPN: [138.5, 36.5] };
const points = {};
for (const f of kept) {
  const iso = f.properties.iso;
  if (!iso) continue;
  const c = overrides[iso] || geoCentroid(f);
  points[iso] = [Math.round(c[0] * 100) / 100, Math.round(c[1] * 100) / 100];
}

let topo = topology({ countries: { type: "FeatureCollection", features: kept } }, 2e4);
topo = presimplify(topo);
topo = simplify(topo, quantile(topo, 0.12));
// Re-quantize to shrink coordinates.
const out = { topo, points, inScope: Object.values(inScope).sort() };
const text = JSON.stringify(out);
writeFileSync(new URL("../src/lib/basemap.json", import.meta.url), text);
console.log(`kept ${kept.length} countries, ${Object.keys(points).length} in scope, ${(text.length / 1024).toFixed(0)} KB`);
const missing = Object.values(inScope).filter((iso) => !points[iso]);
if (missing.length) console.log("MISSING in basemap:", missing.join(","));

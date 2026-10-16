// Builds one small basemap per area (TopoJSON + label points + projection spec) from Natural Earth 1:50m (world-atlas).
// Run when countries.yaml changes (npm run basemap); outputs are committed: src/lib/basemaps/<area>.json
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { feature } from "topojson-client";
import { topology } from "topojson-server";
import { presimplify, quantile, simplify } from "topojson-simplify";
import { geoCentroid, geoBounds } from "d3-geo";

const require = createRequire(import.meta.url);
const world = JSON.parse(readFileSync(require.resolve("world-atlas/countries-50m.json"), "utf8"));
const yamlText = readFileSync(new URL("../../config/countries.yaml", import.meta.url), "utf8");

// numeric code -> {iso, area} (tiny YAML parse of lines like `  ISO: {name: X, numeric: "123", ..., area: asia}`)
const countries = {};
for (const m of yamlText.matchAll(/^\s{2}([A-Z]{3}):\s*\{[^}]*numeric:\s*"(\d{3})"[^}]*area:\s*(\w+)/gm)) countries[m[2]] = { iso: m[1], area: m[3] };

const AREAS = {
  asia: {
    window: [42, -14, 152, 58],
    proj: { type: "mercator" },
    overrides: { MYS: [102.2, 4.0], IDN: [113.5, -1.5], PHL: [122.5, 12.0], JPN: [138.5, 36.5] },
  },
  north_america: {
    window: [-172, 5, -50, 76],
    // Equal-area conic centred on the continent; fitted to a box so Canada's Arctic islands don't shrink the map.
    proj: { type: "conic", rotate: [100, 0], parallels: [20, 60], fitBox: [[-165, 52], [-60, 50], [-120, 70], [-75, 9], [-110, 15], [-58, 12]] },
    overrides: { USA: [-98.5, 39.5], CAN: [-104, 56], MEX: [-102.5, 23.8], BHS: [-77.4, 24.6] },
  },
  south_america: {
    window: [-95, -57, -28, 15],
    proj: { type: "mercator" },
    overrides: { CHL: [-71, -33], ECU: [-78.4, -1.5] },
  },
  africa: {
    window: [-26, -37, 60, 38],
    proj: { type: "mercator", fitBox: [[-18, 36], [52, 36], [52, -35], [-18, -35]] },
    overrides: { MAR: [-6.5, 32], ZAF: [24, -30], MDG: [46.8, -19.5] },
  },
  europe: {
    window: [-26, 33, 62, 72],
    // Equal-area conic fitted to Iceland, the Urals and the Caucasus (Russia's Asian part runs off the frame).
    proj: { type: "conic", rotate: [-15, 0], parallels: [43, 62], fitBox: [[-24, 64], [56, 66], [50, 38], [-10, 36], [25, 35]] },
    overrides: { FRA: [2.5, 46.6], NOR: [9, 61.3], RUS: [44, 57], GBR: [-1.8, 52.8], SWE: [15, 62.5], FIN: [26, 62.5], DNK: [9.3, 56], GRC: [22, 39.5], HRV: [16, 45.4] },
  },
};

// World map for the "All Regions" summary: every country, covered ones tagged with their area (no label points).
const WORLD_SIMPLIFY = 0.02;

const fc = feature(world, world.objects.countries);
mkdirSync(new URL("../src/lib/basemaps/", import.meta.url), { recursive: true });
for (const [area, cfg] of Object.entries(AREAS)) {
  const W = cfg.window;
  const kept = [];
  for (const f0 of fc.features) {
    const c = countries[f0.id];
    const ours = c && c.area === area;
    const [[x0, y0], [x1, y1]] = geoBounds(f0);
    const wraps = x0 > x1 || (x0 < -150 && x1 > 150);
    const touches = !wraps && x1 >= W[0] && x0 <= W[2] && y1 >= W[1] && y0 <= W[3];
    if (!ours && !touches) continue;
    if (!ours && c) {} // a covered country from another area: context only
    const f = { ...f0, properties: { n: f0.properties.name } };
    if (ours) f.properties.iso = c.iso;
    kept.push(f);
  }
  const points = {};
  for (const f of kept) {
    const iso = f.properties.iso;
    if (!iso) continue;
    const p = cfg.overrides[iso] || geoCentroid(f);
    points[iso] = [Math.round(p[0] * 100) / 100, Math.round(p[1] * 100) / 100];
  }
  let topo = topology({ countries: { type: "FeatureCollection", features: kept } }, 2e4);
  topo = presimplify(topo);
  topo = simplify(topo, quantile(topo, 0.12));
  const out = { area, proj: cfg.proj, topo, points };
  const text = JSON.stringify(out);
  writeFileSync(new URL(`../src/lib/basemaps/${area}.json`, import.meta.url), text);
  const wanted = Object.values(countries).filter((c) => c.area === area).map((c) => c.iso);
  const missing = wanted.filter((iso) => !points[iso]);
  console.log(`${area}: kept ${kept.length} countries, ${Object.keys(points).length} in scope, ${(text.length / 1024).toFixed(0)} KB${missing.length ? "; MISSING " + missing.join(",") : ""}`);
}
{
  const feats = fc.features.filter((f) => f.id !== "010").map((f0) => {  // Antarctica dropped
    const c = countries[f0.id];
    return { ...f0, properties: c ? { n: f0.properties.name, a: c.area } : { n: f0.properties.name } };
  });
  let topo = topology({ countries: { type: "FeatureCollection", features: feats } }, 4e3);
  topo = presimplify(topo);
  topo = simplify(topo, quantile(topo, WORLD_SIMPLIFY));
  const text = JSON.stringify({ area: "world", proj: { type: "naturalEarth" }, topo, points: {} });
  writeFileSync(new URL("../src/lib/basemaps/world.json", import.meta.url), text);
  console.log(`world: ${feats.length} countries, ${(text.length / 1024).toFixed(0)} KB`);
}

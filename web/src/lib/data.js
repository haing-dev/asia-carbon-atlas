// Data loading, filtering and aggregation. All filtering runs in the browser on the compact index.

export const L1_COLORS = {
  forestry: "#009E73", agriculture: "#B39B00", engineered: "#CC79A7", renewables: "#E69F00",
  efficiency: "#0072B2", household: "#D55E00", waste: "#8C6D46", industrial: "#56B4E9",
  transport: "#6E57A6", other: "#8A8A8A",
};

export const STAGE_LABELS = { pipeline: "Listed", registered: "Validated", issuing: "Issuing", inactive: "Inactive", announced: "Announced deal" };
// Which year to show for each stage: listed -> listing year, validated -> registration year, issuing -> first issuance year.

export async function loadMeta() {
  const r = await fetch("/data/meta.json", { cache: "no-cache" });
  if (!r.ok) throw new Error("meta.json not found");
  return r.json();
}

let summaryCache = null;
export function loadSummary(meta) {
  if (!summaryCache) summaryCache = fetch("/data/" + meta.files.summary).then((r) => r.json());
  return summaryCache;
}

const indexCache = new Map();
export function loadIndex(meta, area) {
  if (!indexCache.has(area)) indexCache.set(area, fetchIndex(meta.files.index[area]));
  return indexCache.get(area);
}
const basemaps = import.meta.glob("./basemaps/*.json", { import: "default" });
export function loadBasemap(area) {
  return basemaps[`./basemaps/${area}.json`]();
}

async function fetchIndex(file) {
  const r = await fetch("/data/" + file);
  const idx = await r.json();
  const c = idx.cols;
  const n = (c.id || []).length;
  const projects = new Array(n);
  for (let i = 0; i < n; i++) {
    projects[i] = {
      id: c.id[i], shares: c.c[i], l2: c.l2[i], st: c.st[i], rg: c.rg[i], a6: c.a6[i], ex: c.ex ? c.ex[i] : 0,
      ea: c.ea[i], is: c.is[i], re: c.re[i], pi: c.pi ? c.pi[i] : null,
    };
  }
  const l2ToL1 = idx.l2.map((x) => x.l1);
  return { ...idx, projects, l2ToL1 };
}

const rowCache = new Map();
export async function loadRows(meta, iso) {
  const file = meta.files.rows[iso];
  if (!file) return [];
  if (!rowCache.has(file)) rowCache.set(file, fetch("/data/" + file).then((r) => r.json()).then((rows) => rows.map((r) => hydrateRow(meta, r))));
  return rowCache.get(file);
}

// Rows are stored compactly (pipeline/build.py compact_row): rebuild the full shape the UI uses.
export function urlFor(meta, rid) {
  const i = rid.indexOf(":");
  const t = meta.url_templates?.[rid.slice(0, i)];
  const id = rid.slice(i + 1);
  return t ? t.replace("{id}", id).replace("{lid}", id.toLowerCase()) : null;
}
export function hydrateRow(meta, r) {
  const y = r.y || [];
  return {
    project_id: r.id, display_name: r.n, developer: r.d || null, countries: r.c,
    country_names: r.c.map((c) => meta.names?.[c] || c),
    country_shares: r.sh || { [r.c[0]]: 1 },
    registries: r.rg.map((g) => {
      const [rid, url] = Array.isArray(g) ? g : [g, urlFor(meta, g)];
      return { record_id: rid, registry: rid.slice(0, rid.indexOf(":")), url };
    }),
    years: { listed: y[0] ?? null, registered: y[1] ?? null, first_issuance: y[2] ?? null },
    issuance_by_vintage: r.v || {}, methodology_codes: r.m || [], crediting: r.cr || [null, null],
    article6: r.a6 || null, flags: r.f || [], project_url: r.pu || null, developer_url: r.du || null,
    offtakers: r.o || [],
    tags: r.t || [], rb: r.rb || [],
  };
}

// Tag search: a query that equals a tag's label or alias (or begins such a term followed by a space,
// e.g. "solar" -> "solar lantern") selects exactly the projects carrying those tags.
const normTerm = (s) => s.toLowerCase().replace(/&/g, "and").replace(/[\s_-]+/g, " ").trim();
export function tagsForQuery(meta, q) {
  const n = normTerm(q);
  if (!n) return null;
  const hit = new Set();
  (meta.tags || []).forEach((t, i) => {
    if ([t.label, ...t.aliases].some((term) => { const x = normTerm(term); return x === n || x.startsWith(n + " "); })) hit.add(i);
  });
  return hit.size ? hit : null;
}

// filters: {l2: Set<number>|null, stages: Set<number>, registries: Set<number>|null, a6: bool}
export function makePredicate(f) {
  return (p) =>
    (!f.l2 || f.l2.has(p.l2)) &&
    (!f.stages || f.stages.has(p.st)) &&
    (!f.registries || [...f.registries].some((ri) => p.rg & (1 << ri))) &&
    (!f.a6 || p.a6 === 1);
}

// Sum metric per country index using population-weighted shares.
export function aggregate(projects, pred, metric) {
  const totals = new Map();
  for (const p of projects) {
    if (!pred(p)) continue;
    if (metric === "ea" && p.ex) continue;   // estimated annual: only projects still in a crediting period
    const v = p[metric] || 0;
    if (!v) continue;
    for (const [ci, s] of p.shares) totals.set(ci, (totals.get(ci) || 0) + v * s);
  }
  return totals;
}

export function fmt(v) {
  if (v == null) return "—";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 1 : 2) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(v >= 1e4 ? 0 : 1) + "k";
  return String(Math.round(v));
}

export function fmtFull(v) {
  return v == null ? "—" : Math.round(v).toLocaleString("en-US");
}

<script>
  import { onMount } from "svelte";
  import Map from "./lib/Map.svelte";
  import Filters from "./lib/Filters.svelte";
  import Table from "./lib/Table.svelte";
  import { aggregate, fmt, loadIndex, loadMeta, loadRows, makePredicate } from "./lib/data.js";

  const METRICS = {
    is: { label: "Issued (cumulative)", unit: "tCO₂e" },
    ea: { label: "Estimated annual", unit: "tCO₂e/yr" },
  };

  let meta = $state(null);
  let index = $state(null);
  let error = $state(null);
  let metric = $state("is");
  let country = $state(null);
  let f = $state({ l2: null, stages: new Set([0, 1, 2]), registries: null, a6: false, q: "" });
  let rawRows = $state([]);
  let loadingRows = $state(false);
  let theme = $state(null);

  // ---- URL state (shareable links) ----
  function readUrl(idx) {
    const p = new URLSearchParams(location.search);
    if (p.get("m") in METRICS) metric = p.get("m");
    if (p.get("c") && idx.countries.some((c) => c.id === p.get("c"))) country = p.get("c");
    const ids = (k) => (p.get(k) ? p.get(k).split(",") : null);
    const t = ids("t");
    if (t) f.l2 = new Set(t.map((id) => idx.l2.findIndex((x) => x.id === id)).filter((i) => i >= 0));
    const st = ids("st");
    if (st) f.stages = st[0] === "all" ? null : new Set(st.map((s) => idx.stages.indexOf(s)).filter((i) => i >= 0));
    const r = ids("r");
    if (r) f.registries = new Set(r.map((id) => idx.registries.findIndex((x) => x.id === id)).filter((i) => i >= 0));
    f.a6 = p.get("a6") === "1";
    f.q = p.get("q") || "";
  }
  $effect(() => {
    if (!index) return;
    const p = new URLSearchParams();
    if (metric !== "is") p.set("m", metric);
    if (country) p.set("c", country);
    if (f.l2) p.set("t", [...f.l2].map((i) => index.l2[i].id).join(","));
    const st = f.stages ? [...f.stages].sort().map((i) => index.stages[i]).join(",") : "all";
    if (st !== "pipeline,registered,issuing") p.set("st", st);
    if (f.registries) p.set("r", [...f.registries].map((i) => index.registries[i].id).join(","));
    if (f.a6) p.set("a6", "1");
    if (f.q) p.set("q", f.q);
    const qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  });

  onMount(async () => {
    try {
      meta = await loadMeta();
      const idx = await loadIndex(meta);
      readUrl(idx);
      index = idx;
    } catch (e) {
      error = e.message;
    }
  });

  const pred = $derived(makePredicate(f));
  const totals = $derived(index ? aggregate(index.projects, pred, metric) : new globalThis.Map());
  const byId = $derived(index ? new globalThis.Map(index.projects.map((p) => [p.id, p])) : new globalThis.Map());

  // Load display rows for the selected country (or all countries).
  $effect(() => {
    if (!index || !meta) return;
    const isos = country ? [country] : index.countries.map((c) => c.id);
    loadingRows = true;
    Promise.all(isos.map((iso) => loadRows(meta, iso))).then((lists) => {
      const seen = new Set();
      rawRows = lists.flat().filter((r) => !seen.has(r.project_id) && seen.add(r.project_id));
      loadingRows = false;
    });
  });

  const rows = $derived.by(() => {
    if (!index) return [];
    const q = f.q.trim().toLowerCase();
    const out = [];
    for (const r of rawRows) {
      const p = byId.get(r.project_id);
      if (!p || !pred(p)) continue;
      if (q && !(r.display_name.toLowerCase().includes(q) || (r.developer || "").toLowerCase().includes(q))) continue;
      const l2 = index.l2[p.l2];
      const l1 = index.l1.find((x) => x.id === l2.l1);
      out.push({ ...r, st: p.st, ea: p.ea, is: p.is, re: p.re, l1: l1.id, typeLabel: `${l1.label} – ${l2.label}` });
    }
    return out;
  });

  const countryName = $derived(country && index ? index.countries.find((c) => c.id === country)?.name : null);
  const total = $derived([...totals.values()].reduce((a, b) => a + b, 0));

  function clearFilters() {
    f = { l2: null, stages: new Set([0, 1, 2]), registries: null, a6: false, q: "" };
  }
  function selectCountry(iso) {
    country = iso;
    if (iso) document.getElementById("projects")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function downloadCsv() {
    const head = ["project_id", "project", "developer", "countries", "credit_type", "registries", "registry_urls", "stage",
      "est_annual_tco2e", "issued_tco2e", "retired_tco2e", "offtakers", "project_url", "developer_url"];
    const esc = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
    const lines = [head.join(",")].concat(rows.map((r) => [r.project_id, r.display_name, r.developer, r.countries.join(" "),
      r.typeLabel, r.registries.map((g) => g.record_id).join(" "), r.registries.map((g) => g.url).join(" "),
      index.stages[r.st], r.ea, r.is, r.re, r.offtakers.map((o) => o.name).join("; "), r.project_url, r.developer_url].map(esc).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = `asia-carbon-atlas-${country || "all"}.csv`;
    a.click();
  }
  function toggleTheme() {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    theme = dark ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch (e) {}
  }
  // Footnotes, numbered in reading order. Markers in the page link to #note-N.
  const NOTES = [
    "Circle area is proportional to the value (not a log scale): a country with a quarter of the volume has half the radius. Totals include only the filters currently selected.",
    "Projects hosted in several countries appear once in the table. For country totals on the map, their volumes are split across host countries in proportion to population (UN World Population Prospects 2024).",
    "A project listed in several registries (e.g. CDM → Verra, or CDM → Article 6.4) is merged into one row; a vintage issued in two registries is counted once. Verra and Gold Standard records come via the Berkeley Voluntary Registry Offsets Database.",
    "Pipeline: listed or under validation. Registered: registered with no issuance yet. Issuing: at least one issuance. Inactive: withdrawn, rejected or crediting period ended (hidden by default).",
    "The registry's own ex-ante estimate of annual reductions or removals, which often exceeds what is later issued.",
    "One credit = one tonne of CO₂e reduced or removed. Issued and retired volumes are cumulative.",
    "Offtakers are limited to public registry retirement records, government publications and public announcements, and are therefore not exhaustive.",
  ];
  const asOf = (s) => s.last_changed ? s.last_changed.slice(0, 10) : s.enabled ? "pending" : "not yet connected";
</script>

<header class="wrap top">
  <div>
    <h1>Asia Carbon Credit Atlas</h1>
    <p class="muted">Carbon credit projects in Asia (excl. mainland China) across registries and Paris Agreement mechanisms. Research use only.</p>
  </div>
  <nav>
    <a href="#sources">Sources</a>
    <a href="#notes">Notes</a>
    <button class="theme" onclick={toggleTheme} aria-label="Toggle dark mode">◐</button>
  </nav>
</header>

<main class="wrap">
  {#if error}
    <p class="notice">Could not load data ({error}).</p>
  {:else if !index}
    <p class="muted">Loading…</p>
  {:else}
    {#if meta.project_count === 0}
      <p class="notice">Registry data is being connected source by source. The map and table fill in as each source goes live.</p>
    {/if}
    <div class="maphead">
      <label>Circle size<sup class="fn"><a href="#note-1">1</a></sup>
        <select bind:value={metric}>
          {#each Object.entries(METRICS) as [k, m]}<option value={k}>{m.label} ({m.unit})</option>{/each}
        </select>
      </label>
      <span class="muted">Total in view: <span class="num">{fmt(total)}</span> {METRICS[metric].unit}</span>
    </div>
    <Map {totals} countries={index.countries} selected={country} metricLabel={METRICS[metric].label} unit={METRICS[metric].unit} onselect={selectCountry} />

    <section id="projects">
      <div class="tablehead">
        <h2>
          {#if countryName}{countryName} <button class="chip" onclick={() => (country = null)} aria-label="Show all countries">✕ all countries</button>{:else}All countries{/if}
          <span class="muted count">{rows.length.toLocaleString()} {rows.length === 1 ? "project" : "projects"}</span>
        </h2>
        <button class="dl" onclick={downloadCsv} disabled={!rows.length}>Download CSV</button>
      </div>
      <Filters {index} bind:f onclear={clearFilters} />
      <Table {rows} {index} loading={loadingRows} />
    </section>

    <section id="sources" class="prose">
      <h2>Sources and data freshness</h2>
      <table class="src">
        <thead><tr><th>Source</th><th>Data as of</th><th>Status</th></tr></thead>
        <tbody>
          {#each Object.entries(meta.built_from) as [id, s]}
            <tr>
              <td>{#if s.url}<a href={s.url} target="_blank" rel="noopener">{s.label}</a>{:else}{s.label}{/if}{#if s.license} <span class="muted">({s.license})</span>{/if}</td>
              <td class="num">{asOf(s)}</td>
              <td>{s.stale ? "⚠ stale — last good data shown" : s.enabled ? "live" : "coming"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    <section id="notes" class="notes">
      <h2>Notes</h2>
      <ol>
        {#each NOTES as n, i}
          <li id="note-{i + 1}">{@html n}</li>
        {/each}
      </ol>
      <p>Verra and Gold Standard data come via the Berkeley Carbon Trading Project, <em>Voluntary Registry Offsets Database</em>, UC Berkeley (CC BY 4.0). Article 6 data: UNEP Copenhagen Climate Centre, <em>Article 6 Pipeline</em>. Basemap: Natural Earth. Population: UN DESA, <em>World Population Prospects 2024</em>. Research use only; not investment advice.</p>
    </section>
  {/if}
</main>

<footer class="wrap muted small">Asia Carbon Credit Atlas · non-commercial research project · data checked every 10 days</footer>

<style>
  .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding-top: 22px; padding-bottom: 6px; }
  h1 { font-size: 22px; margin: 0 0 2px; letter-spacing: -0.01em; }
  h1 + p { margin: 0; font-size: 14px; max-width: 640px; }
  nav { display: flex; gap: 14px; align-items: center; font-size: 14px; white-space: nowrap; }
  .theme { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; width: 30px; height: 30px; cursor: pointer; }
  .notice { background: var(--chip); border: 1px solid var(--line); border-radius: var(--radius); padding: 8px 12px; font-size: 14px; }
  .maphead { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin: 10px 0 8px; font-size: 14px; }
  .maphead select { margin-left: 6px; border: 1px solid var(--line); border-radius: 6px; padding: 3px 6px; background: var(--surface); }
  #projects { margin-top: 18px; scroll-margin-top: 12px; }
  .tablehead { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  h2 { font-size: 18px; margin: 0; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .count { font-size: 14px; font-weight: 400; }
  .chip { font-size: 12px; border: 1px solid var(--line); background: var(--chip); border-radius: 999px; padding: 2px 9px; cursor: pointer; }
  .dl { border: 1px solid var(--accent); color: var(--accent); background: var(--surface); border-radius: 999px; padding: 4px 14px; cursor: pointer; font-size: 13px; }
  .dl:disabled { opacity: 0.4; cursor: default; }
  .prose { margin-top: 36px; max-width: 860px; font-size: 14px; }
  .notes { margin-top: 36px; padding-top: 12px; border-top: 1px solid var(--line); max-width: 860px; font-size: 12px; color: var(--muted); }
  .notes h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
  .notes ol { padding-left: 18px; margin: 0 0 10px; }
  .notes li { margin-bottom: 3px; scroll-margin-top: 16px; }
  .notes li:target { color: var(--ink); background: var(--accent-soft); }
  .prose h2 { margin-bottom: 8px; }
  .prose li { margin-bottom: 4px; }
  .src { border-collapse: collapse; width: 100%; font-size: 13.5px; }
  .src th, .src td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .small { font-size: 12.5px; }
  footer { padding: 28px 16px 40px; }
</style>

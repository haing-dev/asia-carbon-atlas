<script>
  import { onMount } from "svelte";
  import Map from "./lib/Map.svelte";
  import Ranking from "./lib/Ranking.svelte";
  import Filters from "./lib/Filters.svelte";
  import Table from "./lib/Table.svelte";
  import Summary from "./lib/Summary.svelte";
  import BuyerProfile from "./lib/BuyerProfile.svelte";
  import { aggregate, fmt, loadBasemap, loadIndex, loadMeta, loadRows, loadSummary, makePredicate, tagsForQuery } from "./lib/data.js";

  const METRICS = {
    is: { label: "Issued (cumulative)", unit: "tCO₂e" },
    ea: { label: "Estimated annual", unit: "tCO₂e/yr" },
  };

  let meta = $state(null);
  let index = $state(null);
  let area = $state("all");     // "all" = the All Regions summary tab
  let summary = $state(null);
  let buyer = $state(null);     // buyer profile open on the All Regions tab
  let worldmap = $state(null);
  let basemap = $state(null);
  let error = $state(null);
  let metric = $state("is");
  let country = $state(null);
  let mapHl = $state(null);   // country hovered in the ranking
  let rankHl = $state(null);  // country hovered on the map
  let f = $state({ l2: null, stages: new Set([0, 1, 2, 4]), registries: null, a6: false, q: "" });
  let rawRows = $state([]);
  let loadingRows = $state(false);

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
    if (area === "all") {
      if (meta) history.replaceState(null, "", buyer ? "?b=" + encodeURIComponent(buyer) : location.pathname);
      return;
    }
    if (!index) return;
    const p = new URLSearchParams();
    p.set("a", area);
    if (metric !== "is") p.set("m", metric);
    if (country) p.set("c", country);
    if (f.l2) p.set("t", [...f.l2].map((i) => index.l2[i].id).join(","));
    const st = f.stages ? [...f.stages].sort().map((i) => index.stages[i]).join(",") : "all";
    if (st !== "pipeline,registered,issuing,announced") p.set("st", st);
    if (f.registries) p.set("r", [...f.registries].map((i) => index.registries[i].id).join(","));
    if (f.a6) p.set("a6", "1");
    if (f.q) p.set("q", f.q);
    const qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  });

  onMount(async () => {
    try {
      meta = await loadMeta();
      const a = new URLSearchParams(location.search).get("a");
      if (meta.areas.some((x) => x.id === a)) {
        area = a;
        const [idx, bm] = await Promise.all([loadIndex(meta, area), loadBasemap(area)]);
        readUrl(idx);
        basemap = bm;
        index = idx;
      } else {
        buyer = new URLSearchParams(location.search).get("b");
        await openSummary();
      }
    } catch (e) {
      error = e.message;
    }
  });
  async function openSummary() {
    const [sm, wm] = await Promise.all([loadSummary(meta), loadBasemap("world")]);
    summary = sm;
    worldmap = wm;
  }
  function openProfile(name) {
    buyer = name;
    window.scrollTo({ top: 0 });
  }
  async function switchArea(a) {
    if (a === "all" && buyer) { buyer = null; window.scrollTo({ top: 0 }); }
    if (a === area || !meta) return;
    area = a;
    country = null;
    mapHl = rankHl = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (a === "all") {
      index = null;
      await openSummary();
      return;
    }
    index = null;
    const [idx, bm] = await Promise.all([loadIndex(meta, a), loadBasemap(a)]);
    if (area !== a) return;   // switched again meanwhile
    // Keep filters that still make sense (credit types, stages); registry choice resets.
    f.registries = null;
    basemap = bm;
    index = idx;
  }
  const tabs = $derived(meta ? [meta.summary || { id: "all", label: "All Regions" }, ...meta.areas] : []);
  const areaInfo = $derived(area === "all" ? { label: "All Regions", scope: "Asia (excl. mainland China), the Americas, Africa and Europe" }
    : meta?.areas.find((x) => x.id === area));
  const headlines = $derived(meta?.headlines?.areas?.[area] || []);

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
    const tagHit = q ? tagsForQuery(meta, q) : null;
    const out = [];
    for (const r of rawRows) {
      const p = byId.get(r.project_id);
      if (!p || !pred(p)) continue;
      if (tagHit) { if (!r.tags.some((t) => tagHit.has(t))) continue; }
      else if (q && !(r.display_name.toLowerCase().includes(q) || (r.developer || "").toLowerCase().includes(q)
        || r.offtakers.some((o) => o.name.toLowerCase().includes(q)) || r.methodology_codes.some((m) => m.toLowerCase().includes(q)))) continue;
      const l2 = index.l2[p.l2];
      const l1 = index.l1.find((x) => x.id === l2.l1);
      out.push({ ...r, st: p.st, ea: p.ea, is: p.is, re: p.re, pi: p.pi, pr: p.is > 0 && p.re != null ? p.re / p.is : null, l1: l1.id, typeLabel: `${l1.label} – ${l2.label}`,
        tagLabels: r.tags.map((t) => meta.tags[t]).sort((a, b) => a.broad - b.broad).map((t) => t.label) });
    }
    return out;
  });

  const countryName = $derived(country && index ? index.countries.find((c) => c.id === country)?.name : null);
  const total = $derived([...totals.values()].reduce((a, b) => a + b, 0));

  function clearFilters() {
    f = { l2: null, stages: new Set([0, 1, 2, 4]), registries: null, a6: false, q: "" };
  }
  function selectCountry(iso) {
    country = iso;
    if (iso) document.getElementById("projects")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function downloadCsv() {
    const head = ["project_id", "project", "developer", "countries", "credit_type", "tags", "registries", "registry_urls", "stage", "listed_year", "validated_year", "first_issued_year",
      "est_annual_tco2e", "issued_tco2e", "retired_tco2e", "issued_vs_estimate", "retired_share", "offtakers", "project_url", "developer_url"];
    const esc = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
    const lines = [head.join(",")].concat(rows.map((r) => [r.project_id, r.display_name, r.developer, (r.country_names || r.countries).join("; "),
      r.typeLabel, r.tagLabels.join("; "), r.registries.map((g) => g.record_id).join(" "), r.registries.map((g) => g.url).join(" "),
      index.stages[r.st], r.years?.listed, r.years?.registered, r.years?.first_issuance, r.ea, r.is, r.re, r.pi, r.pr == null ? "" : r.pr.toFixed(3), r.offtakers.map((o) => o.name).join("; "), r.project_url, r.developer_url].map(esc).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = `carbon-credit-atlas-${country || area}.csv`;
    a.click();
  }
  // Footnotes come from content/notes.md (owner-editable). Markers refer to notes by key; numbers follow file order.
  const notes = $derived(meta?.notes || []);
  const fnum = (key) => notes.findIndex((n) => n.key === key) + 1 || null;
  const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // Tiny, safe inline markdown: [text](https://...) and **bold**.
  const md = (t) => esc(t)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Owner-only edit link: open the site once with ?owner=1 on your own browser (?owner=0 to hide it again).
  let owner = $state(false);
  onMount(() => {
    try {
      const o = new URLSearchParams(location.search).get("owner");
      if (o === "1") localStorage.setItem("atlas-owner", "1");
      if (o === "0") localStorage.removeItem("atlas-owner");
      owner = localStorage.getItem("atlas-owner") === "1";
    } catch (e) {}
  });
  const DISCLAIMER = "This project is purely for research purposes and is not used for any commercialization or monetization. All data sources are credited.";
  const EDIT_NOTES = "https://github.com/haing-dev/asia-carbon-atlas/edit/main/content/notes.md";
  const asOf = (s) => s.last_changed ? s.last_changed.slice(0, 10) : s.enabled ? "pending" : "not yet connected";
</script>

<header class="wrap top">
  <div>
    <h1>Carbon Credit Atlas <span class="where">· {areaInfo?.label || ""}</span></h1>
    <p class="muted">Carbon credit projects in {areaInfo?.scope || "…"}, across registries and Paris Agreement mechanisms.</p>
    <p class="disclaimer">Disclaimer: {DISCLAIMER}</p>
  </div>
  <nav>
    <a href="#sources">Sources</a>
    <a href="#notes">Notes</a>
  </nav>
</header>
{#if meta?.areas}
  <div class="wrap">
    <div class="regions" role="tablist" aria-label="Region" style:--n={tabs.length} style:--i={tabs.findIndex((x) => x.id === area)}>
      <span class="thumb" aria-hidden="true"></span>
      {#each tabs as a}
        <button role="tab" aria-selected={a.id === area} onclick={() => switchArea(a.id)}>{a.label}</button>
      {/each}
    </div>
  </div>
{/if}

<main class="wrap">
  {#if error}
    <p class="notice">Could not load data ({error}).</p>
  {:else if area === "all"}
    {#if summary && worldmap && buyer}
      <BuyerProfile {meta} {summary} name={buyer} onback={() => openProfile(null)} />
    {:else if summary && worldmap}
      <Summary {meta} {summary} basemap={worldmap} onselect={switchArea} onprofile={openProfile} {fnum} />
    {:else}
      <p class="muted">Loading…</p>
    {/if}
  {:else if !index || !basemap}
    <p class="muted">Loading…</p>
  {:else}
    {#if meta.project_count === 0}
      <p class="notice">Registry data is being connected source by source. The map and table fill in as each source goes live.</p>
    {/if}
    {#if headlines.length}
      <section class="news" aria-labelledby="news-h">
        <h2 id="news-h">Weekly headlines <span class="muted wk">week to {meta.headlines.week_ending}</span></h2>
        <ol>
          {#each headlines.slice(0, 10) as h}
            <li><a href={h.url} target="_blank" rel="noopener">{h.title}</a> <span class="muted meta">{h.source} · {h.date.slice(5)}</span></li>
          {/each}
        </ol>
      </section>
    {/if}
    <div class="maphead">
      <label>Show{#if fnum("map")}<sup class="fn"><a href="#note-{fnum('map')}">{fnum("map")}</a></sup>{/if}
        <select bind:value={metric}>
          {#each Object.entries(METRICS) as [k, m]}<option value={k}>{m.label} ({m.unit})</option>{/each}
        </select>
      </label>
      <span class="muted">Total in view: <span class="num">{fmt(total)}</span> {METRICS[metric].unit}</span>
    </div>
    <div class="mapgrid">
      <Map {basemap} {totals} countries={index.countries} selected={country} highlight={mapHl} metricLabel={METRICS[metric].label} unit={METRICS[metric].unit} onselect={selectCountry} onhover={(iso) => (rankHl = iso)} />
      <Ranking {totals} countries={index.countries} selected={country} highlight={rankHl} unit={METRICS[metric].unit} onselect={selectCountry} onhover={(iso) => (mapHl = iso)} />
    </div>

    <section id="projects">
      <div class="tablehead">
        <h2>
          {#if countryName}{countryName} <button class="chip" onclick={() => (country = null)} aria-label="Show all countries">✕ all countries</button>{:else}All countries{/if}
          <span class="muted count">{rows.length.toLocaleString()} {rows.length === 1 ? "project" : "projects"}</span>
        </h2>
        <button class="dl" onclick={downloadCsv} disabled={!rows.length}>Download CSV</button>
      </div>
      <Filters {index} bind:f onclear={clearFilters} />
      <Table {rows} {index} {fnum} loading={loadingRows} />
    </section>
  {/if}
  {#if meta && !error && area !== "all"}

    <section id="sources" class="prose">
      <h2>Sources and data freshness</h2>
      <table class="src">
        <thead><tr><th>Source</th><th>Source data as of</th><th>Last updated here</th><th>Status</th></tr></thead>
        <tbody>
          {#each Object.entries(meta.built_from) as [id, s]}
            <tr>
              <td>{#if s.url}<a href={s.url} target="_blank" rel="noopener">{s.label}</a>{:else}{s.label}{/if}{#if s.license}<span class="muted" style="margin-left:5px">({s.license})</span>{/if}</td>
              <td class="num" title={s.live ? "Live registry: date last read" : "Date of the source's release/export"}>{s.source_date || "—"}{#if s.live && s.source_date}<span class="muted" style="margin-left:6px">(live)</span>{/if}</td>
              <td class="num">{asOf(s)}</td>
              <td>{s.stale ? "⚠ stale — last good data shown" : s.enabled ? "live" : "coming"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    <section id="notes" class="notes">
      <h2>Notes {#if owner}<a class="edit" href={EDIT_NOTES} target="_blank" rel="noopener">Edit notes</a>{/if}</h2>
      <ol>
        {#each notes as n, i}
          <li id="note-{i + 1}"><strong class="nt">{n.title}</strong><ul>{#each n.points as pt}<li>{@html md(pt)}</li>{/each}</ul></li>
        {/each}
      </ol>
      <h2 class="cr">Credit</h2>
      <ul class="credits">
        <li><strong>Data:</strong> Berkeley Carbon Trading Project, <em>Voluntary Registry Offsets Database</em> (CC BY 4.0); UNEP Copenhagen Climate Centre, <em>CDM Pipeline</em> and <em>Article 6 Pipeline</em>; the registries listed under Sources; Natural Earth; UN DESA, <em>World Population Prospects 2024</em>.</li>
        <li><strong>Disclaimer:</strong> {DISCLAIMER}</li>
        <li><strong>Author:</strong> <a href="mailto:haing.penn@gmail.com">haing.penn@gmail.com</a> · <a href="https://www.linkedin.com/in/hai-n-13a45370" target="_blank" rel="noopener">LinkedIn</a></li>
      </ul>
    </section>
  {/if}
</main>

<footer class="wrap muted small">Carbon Credit Atlas · non-commercial research project · registry data checked weekly</footer>

<style>
  .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding-top: 22px; padding-bottom: 6px; }
  h1 { font-size: 22px; margin: 0 0 2px; letter-spacing: -0.01em; }
  h1 + p { margin: 0; font-size: 14px; max-width: 680px; }
  nav { display: flex; gap: 14px; align-items: center; font-size: 14px; white-space: nowrap; }
  .notice { background: var(--chip); border: 1px solid var(--line); border-radius: var(--radius); padding: 8px 12px; font-size: 14px; }
  .where { color: var(--accent); font-weight: 600; }
  .regions { position: relative; display: grid; grid-template-columns: repeat(var(--n), 1fr); max-width: 860px; margin: 10px 0 2px;
    background: var(--chip); border: 1px solid var(--line); border-radius: 999px; padding: 3px; }
  .regions button { position: relative; z-index: 1; border: 0; background: none; padding: 6px 10px; border-radius: 999px; cursor: pointer;
    font-size: 14px; font-weight: 600; color: var(--muted); transition: color 0.2s; }
  .regions button[aria-selected="true"] { color: #0d2023; }
  .regions .thumb { position: absolute; top: 3px; bottom: 3px; left: 3px; width: calc((100% - 6px) / var(--n)); border-radius: 999px;
    background: var(--choro-hi); transform: translateX(calc(100% * var(--i))); transition: transform 0.25s ease; }
  @media (prefers-reduced-motion: reduce) { .regions .thumb, .regions button { transition: none; } }
  @media (max-width: 640px) { .regions { border-radius: 14px; } .regions button { font-size: 12px; padding: 6px 4px; line-height: 1.2; } }
  .news { margin: 12px 0 6px; padding: 10px 14px 8px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
  .news h2 { font-size: 15px; margin-bottom: 6px; }
  .news .wk { font-size: 12.5px; font-weight: 400; }
  .news ol { margin: 0; padding-left: 20px; columns: 2 380px; column-gap: 28px; font-size: 13.5px; }
  .news li { break-inside: avoid; margin-bottom: 5px; line-height: 1.35; }
  .news .meta { font-size: 11.5px; white-space: nowrap; }
  .maphead { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin: 10px 0 8px; font-size: 14px; }
  .mapgrid { display: grid; grid-template-columns: minmax(0, 2.3fr) minmax(220px, 1fr); gap: 12px; align-items: start; }
  .mapgrid :global(.ranking) { max-height: 560px; }
  @media (max-width: 820px) { .mapgrid { grid-template-columns: 1fr; } .mapgrid :global(.ranking) { max-height: 320px; } }
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
  .notes .edit { font-size: 11px; text-transform: none; letter-spacing: 0; border: 1px solid var(--accent); border-radius: 999px; padding: 1px 8px; }
  .notes h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
  .notes ol { padding-left: 18px; margin: 0 0 10px; }
  .notes > ol > li { margin-bottom: 6px; scroll-margin-top: 16px; }
  .notes .nt { color: var(--ink); font-weight: 600; }
  .notes h2.cr { margin-top: 14px; }
  .credits { margin: 0 0 10px; padding-left: 18px; }
  .credits li { margin-bottom: 3px; }
  .disclaimer { margin: 4px 0 0; font-size: 12.5px; color: var(--faint); max-width: 760px; }
  .notes ul { margin: 0; padding-left: 14px; list-style: "– "; }
  .notes > ol > li:target { color: var(--ink); background: var(--accent-soft); }
  .prose h2 { margin-bottom: 8px; }
  .prose li { margin-bottom: 4px; }
  .src { border-collapse: collapse; width: 100%; font-size: 13.5px; }
  .src th, .src td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .small { font-size: 12.5px; }
  footer { padding: 28px 16px 40px; }
</style>

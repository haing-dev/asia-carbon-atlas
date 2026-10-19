<script>
  // Buyer profile: totals through the three lenses, credit-type and country mix, and every project with sources.
  import BuyerProjects from "./BuyerProjects.svelte";
  import { L1_COLORS, fmt } from "./data.js";

  let { meta, summary, name, onback } = $props();

  const b = $derived(summary.buyers.list.find((x) => x.n === name));
  const l2 = $derived(summary.l2);
  const LENSES = [
    { k: "re", label: "Retired", sub: "in registry records" },
    { k: "is", label: "Deals on issuing projects", sub: "announced volume" },
    { k: "an", label: "Deals not yet issuing", sub: "announced volume" },
  ];
  const val = (e, k) => (k === "re" ? e.re : k === "is" ? (e.iss ? e.an || 0 : 0) : (!e.iss ? e.an || 0 : 0));
  const L1_ORDER = $derived(Object.fromEntries(summary.l1.map((x, i) => [x.id, i])));
  function mix(k) {
    const by = new Map();
    for (const e of b.p) { const v = val(e, k); if (v) by.set(e.l2, (by.get(e.l2) || 0) + v); }
    return [...by.entries()].map(([id, v]) => ({ id, l1: l2[id]?.l1 || "other", label: l2[id]?.label || id, v }))
      .sort((x, y) => L1_ORDER[x.l1] - L1_ORDER[y.l1] || y.v - x.v);
  }
  const countries = $derived.by(() => {
    if (!b) return [];
    const by = new Map();
    for (const e of b.p) for (const c of e.c) by.set(c, (by.get(c) || 0) + (Math.max(e.re, e.an || 0) / e.c.length));
    return [...by.entries()].sort((x, y) => y[1] - x[1]).map(([c, v]) => ({ c, name: meta.names?.[c] || c, v }));
  });
  const years = $derived.by(() => {
    if (!b) return null;
    const ds = b.p.flatMap((e) => e.rd || []).filter(Boolean).sort();
    return ds.length ? [ds[0].slice(0, 4), ds[ds.length - 1].slice(0, 4)] : null;
  });
  const deals = $derived(b ? b.p.reduce((a, e) => a + e.dl.length, 0) : 0);
</script>

<p class="back"><button class="link" onclick={onback}>← All Regions</button></p>
{#if !b}
  <p class="muted">No data for “{name}”.</p>
{:else}
  <h2 class="title">{b.n} <span class="muted kind">Buyer profile</span></h2>
  <p class="muted lead">{b.np.toLocaleString()} {b.np === 1 ? "project" : "projects"} · {deals} announced {deals === 1 ? "deal" : "deals"} · {countries.length} {countries.length === 1 ? "country" : "countries"}{#if years} · retirements {years[0]}{years[1] !== years[0] ? "–" + years[1] : ""}{/if}</p>
  <div class="tiles">
    {#each LENSES as l}
      <div class="tile">
        <span class="muted small">{l.label}</span>
        <strong class="num">{b[l.k] ? fmt(b[l.k]) : "—"}</strong>
        <span class="muted small">tCO₂e {l.sub}{#if l.k === "re" && summary.buyers.retired_as_of}, as of {summary.buyers.retired_as_of}{/if}</span>
      </div>
    {/each}
  </div>

  <section class="card">
    <h3>Credit types</h3>
    {#each LENSES.filter((l) => b[l.k] > 0) as l}
      {@const m = mix(l.k)}
      <div class="mixrow">
        <span class="ml">{l.label}</span>
        <span class="bar">{#each m as s}<span class="seg" style:flex-grow={s.v} style:background={L1_COLORS[s.l1]} title="{s.label}: {fmt(s.v)} tCO₂e ({((s.v / b[l.k]) * 100).toFixed(0)}%)">{#if s.v / b[l.k] > 0.12}<span class="sl">{s.label}</span>{/if}</span>{/each}</span>
      </div>
      <div class="mixlist muted">{#each m as s}<span><i style:background={L1_COLORS[s.l1]}></i>{s.label} <span class="num">{fmt(s.v)}</span> ({((s.v / b[l.k]) * 100).toFixed(0)}%)</span>{/each}</div>
    {/each}
  </section>

  <section class="card">
    <h3>Countries</h3>
    <div class="ctys">{#each countries.slice(0, 24) as c}<span class="cty">{c.name} <span class="num muted">{fmt(c.v)}</span></span>{/each}</div>
    <p class="muted small">Volume per country = the larger of retired and announced on each project (split equally for multi-country projects).</p>
  </section>

  <section class="card">
    <h3>Projects</h3>
    <BuyerProjects {meta} buyer={b} {l2} lens="all" />
    {#if b.np > b.p.length}<p class="muted small">Showing the {b.p.length} largest of {b.np} projects.</p>{/if}
  </section>
{/if}

<style>
  .back { margin: 12px 0 4px; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font: inherit; font-size: 14px; }
  .title { font-size: 22px; margin: 0; display: flex; gap: 10px; align-items: baseline; }
  .kind { font-size: 13px; font-weight: 400; }
  .lead { margin: 2px 0 12px; font-size: 13.5px; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
  .tile { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 10px 12px; display: grid; gap: 2px; }
  .tile strong { font-size: 24px; font-weight: 600; }
  .small { font-size: 12px; }
  .card { margin-top: 14px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 12px 14px; }
  h3 { margin: 0 0 8px; font-size: 15px; }
  .mixrow { display: grid; grid-template-columns: 190px 1fr; gap: 10px; align-items: center; margin-top: 6px; }
  .ml { font-size: 13px; font-weight: 600; }
  .bar { display: flex; height: 22px; border-radius: 4px; overflow: hidden; }
  .seg { min-width: 3px; border-right: 2px solid var(--surface); display: flex; align-items: center; overflow: hidden; }
  .seg:last-child { border-right: 0; }
  .sl { font-size: 11px; font-weight: 600; color: #0d2023; padding: 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mixlist { display: flex; flex-wrap: wrap; gap: 3px 14px; font-size: 12px; margin: 4px 0 4px 200px; }
  .mixlist i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  @media (max-width: 640px) { .mixrow { grid-template-columns: 1fr; } .mixlist { margin-left: 0; } }
  .ctys { display: flex; flex-wrap: wrap; gap: 6px; }
  .cty { font-size: 12.5px; padding: 2px 9px; border: 1px solid var(--line); border-radius: 999px; }
</style>

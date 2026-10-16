<script>
  // "All Regions" tab: regional totals on a world map (click to open a region) and the largest announced offtakers.
  import RegionMap from "./RegionMap.svelte";
  import OfftakerBars from "./OfftakerBars.svelte";
  import { fmt } from "./data.js";

  let { meta, summary, basemap, onselect, fnum = () => null } = $props();

  const METRICS = {
    is: { label: "Issued (cumulative)", unit: "tCO₂e" },
    ea: { label: "Estimated annual", unit: "tCO₂e/yr" },
    re: { label: "Retired (cumulative)", unit: "tCO₂e" },
  };
  let metric = $state("is");
  const regions = $derived(summary.regions);
  const ranked = $derived([...regions].sort((a, b) => (b[metric] || 0) - (a[metric] || 0)));
  const total = $derived(regions.reduce((a, r) => a + (r[metric] || 0), 0));
  const vmax = $derived(Math.max(1, ...regions.map((r) => r[metric] || 0)));
</script>

<div class="maphead">
  <label>Show
    <select bind:value={metric}>
      {#each Object.entries(METRICS) as [k, m]}<option value={k}>{m.label} ({m.unit})</option>{/each}
    </select>
  </label>
  <span class="muted">All regions: <span class="num">{fmt(total)}</span> {METRICS[metric].unit}</span>
</div>
<div class="mapgrid">
  <RegionMap {basemap} {regions} {metric} unit={METRICS[metric].unit} {onselect} />
  <ol class="rlist" aria-label="Regions">
    {#each ranked as r (r.id)}
      <li>
        <button onclick={() => onselect(r.id)}>
          <span class="top"><strong>{r.label}</strong><span class="num">{fmt(r[metric])}</span></span>
          <span class="bar"><span style:width="{((r[metric] || 0) / vmax) * 100}%"></span></span>
          <span class="muted small">{r.projects.toLocaleString()} projects · {r.countries} countries with issuance · {total ? (((r[metric] || 0) / total) * 100).toFixed(0) : 0}%</span>
        </button>
      </li>
    {/each}
  </ol>
</div>

<section class="offtakers">
  <h2>Largest announced offtakers, all regions</h2>
  <p class="muted lead">Top 15 buyers by total announced volume (tCO₂e), each bar split by the credit types bought. Click a buyer to see its deals and sources.</p>
  <div class="two">
    <OfftakerBars title="Deals on projects already issuing credits" subtitle="The project has issued credits in its registry."
      data={summary.offtakers.issued} l1={summary.l1} l2={summary.l2} names={meta.names} top={15} />
    <OfftakerBars title="Announced deals, not yet issuing" subtitle="The project has not issued credits yet, or is not yet registered (announcement only)."
      data={summary.offtakers.announced} l1={summary.l1} l2={summary.l2} names={meta.names} top={15} />
  </div>
</section>

<style>
  .maphead { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin: 10px 0 8px; font-size: 14px; }
  .maphead select { margin-left: 6px; border: 1px solid var(--line); border-radius: 6px; padding: 3px 6px; background: var(--surface); }
  .mapgrid { display: grid; grid-template-columns: minmax(0, 2.3fr) minmax(220px, 1fr); gap: 12px; align-items: start; }
  @media (max-width: 820px) { .mapgrid { grid-template-columns: 1fr; } }
  .rlist { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  .rlist button { width: 100%; text-align: left; display: grid; gap: 4px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--radius);
    background: var(--surface); cursor: pointer; color: inherit; font: inherit; }
  .rlist button:hover { border-color: var(--accent); }
  .top { display: flex; justify-content: space-between; gap: 8px; font-size: 14.5px; }
  .bar { height: 6px; background: var(--chip); border-radius: 3px; overflow: hidden; }
  .bar span { display: block; height: 100%; background: var(--choro-hi); }
  .small { font-size: 12px; }
  .offtakers { margin-top: 22px; }
  .offtakers h2 { font-size: 18px; margin: 0; }
  .lead { margin: 4px 0 10px; font-size: 13.5px; }
  .two { display: grid; grid-template-columns: 1fr; gap: 16px; }
</style>

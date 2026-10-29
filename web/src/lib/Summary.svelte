<script>
  // "All Regions" tab: regional totals on a world map (click to open a region), top buyers (retired / issued /
  // announced lenses) and retired share + time to first issuance by credit type.
  import RegionMap from "./RegionMap.svelte";
  import BuyerTable from "./BuyerTable.svelte";
  import TypeTable from "./TypeTable.svelte";
  import { fmt } from "./data.js";

  let { meta, summary, basemap, onselect, onprofile, fnum = () => null } = $props();

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

<h2 class="sec">Where are carbon credits generated?</h2>
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

<BuyerTable {meta} data={summary.buyers} l1={summary.l1} l2={summary.l2} top={15} {onprofile} />
<TypeTable types={summary.types} l1={summary.l1} l2={summary.l2} areas={meta.areas} />

<style>
  .sec { font: 700 22px/1.25 var(--serif); margin: 26px 0 0; }
  .maphead { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin: 10px 0 8px; font-size: 14px; }
  .maphead select { margin-left: 6px; border: 1px solid var(--black); border-radius: 0; padding: 3px 6px; background: var(--white); }
  .mapgrid { display: grid; grid-template-columns: minmax(0, 2.3fr) minmax(220px, 1fr); gap: 12px; align-items: start; }
  @media (max-width: 820px) { .mapgrid { grid-template-columns: 1fr; } }
  .rlist { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  .rlist button { width: 100%; text-align: left; display: grid; gap: 4px; padding: 10px 0; border: 0; border-top: 1px solid var(--black); border-radius: 0;
    background: none; cursor: pointer; color: inherit; font: inherit; }
  .rlist button:hover { background: var(--gray-pale); }
  .top { display: flex; justify-content: space-between; gap: 8px; font-size: 14.5px; }
  .top .num { font: 700 18px var(--serif); }
  .bar { height: 6px; background: var(--gray-pale); overflow: hidden; }
  .bar span { display: block; height: 100%; background: var(--deep-blue); }
  .small { font-size: 12px; }
</style>

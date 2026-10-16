<script>
  // World map for the "All Regions" tab: each covered region shaded by its total; click a region to open its tab.
  import { geoNaturalEarth1, geoPath } from "d3-geo";
  import { feature } from "topojson-client";
  import { fmt } from "./data.js";

  let { basemap, regions, metric, unit, onselect } = $props();

  const W = 960, H = 470;
  // Label anchors (lon, lat) for each region, placed over its main land mass.
  const ANCHOR = { asia: [84, 27], north_america: [-100, 44], south_america: [-60, -14], africa: [19, 4], europe: [22, 53] };

  const geo = $derived.by(() => {
    const all = feature(basemap.topo, basemap.topo.objects.countries).features;
    const projection = geoNaturalEarth1().fitExtent([[8, 8], [W - 8, H - 8]], { type: "Sphere" });
    const path = geoPath(projection);
    // Drop any shape drawn inside-out by simplification (it would cover the whole globe).
    const shapes = all.filter((f) => path.area(f) < W * H * 0.2)
      .map((f) => ({ a: f.properties.a || null, name: f.properties.n, d: path(f) }));
    return { shapes, projection };
  });

  const val = $derived(Object.fromEntries(regions.map((r) => [r.id, r[metric] || 0])));
  const vmax = $derived(Math.max(0, ...Object.values(val)));
  const vsum = $derived(Object.values(val).reduce((a, b) => a + b, 0));
  const level = (v) => (v > 0 && vmax > 0 ? 0.15 + 0.85 * Math.sqrt(v / vmax) : 0);
  const fill = (v) => (v > 0 ? `color-mix(in oklab, var(--choro-hi) ${Math.round(level(v) * 100)}%, var(--choro-lo))` : null);

  let hover = $state(null);
  const labels = $derived(regions.map((r) => {
    const [x, y] = geo.projection(ANCHOR[r.id]) || [0, 0];
    return { ...r, x, y, v: val[r.id] };
  }));
  const tip = $derived(hover ? labels.find((l) => l.id === hover) : null);
</script>

<figure class="rmap">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="World map shaded by region">
    <g class:focusing={!!hover}>
      {#each geo.shapes as s}
        {#if s.a}
          <path d={s.d} class="in" class:on={hover === s.a} style:fill={fill(val[s.a])}
            role="button" tabindex="-1" aria-label="Open {s.a}"
            onclick={() => onselect(s.a)} onmouseenter={() => (hover = s.a)} onmouseleave={() => (hover = null)}><title>{s.name}</title></path>
        {:else}
          <path d={s.d} class="ctx"><title>{s.name} (not covered)</title></path>
        {/if}
      {/each}
    </g>
    <g class="labels" aria-hidden="true">
      {#each labels as l (l.id)}
        <text x={l.x} y={l.y} class:on={hover === l.id}>
          <tspan class="n">{l.label}</tspan>
          <tspan class="v" x={l.x} dy="15">{fmt(l.v)}</tspan>
        </text>
      {/each}
    </g>
  </svg>
  {#if tip}
    <div class="tip" style:left="{(tip.x / W) * 100}%" style:top="{(tip.y / H) * 100}%">
      <strong>{tip.label}</strong>
      <span class="num">{fmt(tip.v)} {unit}</span>
      {#if vsum > 0}<span class="muted">{((tip.v / vsum) * 100).toFixed(0)}% of total · {tip.projects.toLocaleString()} projects</span>{/if}
      <span class="go">Click to open →</span>
    </div>
  {/if}
</figure>

<style>
  .rmap { margin: 0; position: relative; }
  svg { width: 100%; height: auto; display: block; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
  .ctx { fill: var(--land); stroke: var(--surface); stroke-width: 0.4; }
  .in { fill: var(--land-in); stroke: var(--surface); stroke-width: 0.4; cursor: pointer; transition: opacity 0.15s, filter 0.15s; outline: none; }
  .focusing .in:not(.on) { opacity: 0.4; }
  .in.on { filter: brightness(1.15); }
  .labels text { font: 700 13px var(--font); fill: var(--ink); text-anchor: middle; paint-order: stroke; stroke: var(--surface); stroke-width: 3.5px;
    stroke-linejoin: round; pointer-events: none; }
  .labels .v { font: 500 11.5px var(--mono); }
  .tip { position: absolute; transform: translate(-50%, calc(-100% - 22px)); pointer-events: none; background: var(--surface);
    border: 1px solid var(--accent); border-radius: 8px; padding: 6px 10px; font-size: 13px; line-height: 1.35; display: grid;
    text-align: center; white-space: nowrap; box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45); z-index: 2; }
  .tip strong { font-size: 14px; }
  .tip .go { color: var(--accent); font-size: 12px; }
  @media (prefers-reduced-motion: reduce) { .in { transition: none; } }
</style>

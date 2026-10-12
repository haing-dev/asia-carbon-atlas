<script>
  import { geoMercator, geoPath } from "d3-geo";
  import { feature } from "topojson-client";
  import basemap from "./basemap.json";
  import { fmt } from "./data.js";

  let { totals, countries, selected = null, metricLabel, unit, onselect } = $props();

  const W = 960, H = 600;
  const all = feature(basemap.topo, basemap.topo.objects.countries).features;
  const inScope = all.filter((f) => f.properties.iso);
  const projection = geoMercator().fitExtent([[16, 16], [W - 16, H - 16]], { type: "FeatureCollection", features: inScope });
  const path = geoPath(projection);
  const shapes = all.map((f) => ({ iso: f.properties.iso, name: f.properties.n, d: path(f) }));

  // Small places get a nudged label point with a leader line so circles don't hide each other.
  const NUDGE = { HKG: [26, 10], MAC: [-30, 22], SGP: [-8, 34], BRN: [30, -22], MDV: [-22, 20] };
  const anchors = {};
  for (const [iso, lonlat] of Object.entries(basemap.points)) {
    const [x, y] = projection(lonlat);
    const [dx, dy] = NUDGE[iso] || [0, 0];
    anchors[iso] = { x, y, cx: x + dx, cy: y + dy, nudged: !!NUDGE[iso] };
  }

  const R_MAX = Math.max(28, Math.min(56, 0.06 * W));
  let hover = $state(null);

  const circles = $derived.by(() => {
    const vals = countries.map((c, i) => ({ iso: c.id, name: c.name, v: totals.get(i) || 0 })).filter((d) => d.v > 0 && anchors[d.iso]);
    const vmax = Math.max(0, ...vals.map((d) => d.v));
    return vals
      .map((d) => ({ ...d, ...anchors[d.iso], r: Math.max(3, R_MAX * Math.sqrt(d.v / vmax)) }))
      .sort((a, b) => b.r - a.r);
  });

  const legend = $derived.by(() => {
    const vmax = circles.length ? Math.max(...circles.map((c) => c.v)) : 0;
    if (!vmax) return [];
    const nice = (v) => { const p = 10 ** Math.floor(Math.log10(v)); return Math.round(v / p) * p; };
    return [vmax, vmax / 10, vmax / 100].map((v) => nice(v)).filter((v, i, a) => v > 0 && a.indexOf(v) === i)
      .map((v) => ({ v, r: Math.max(3, R_MAX * Math.sqrt(v / vmax)) }));
  });

  const nameOf = (iso) => countries.find((c) => c.id === iso)?.name || iso;
</script>

<figure class="map">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Map of Asia with circles sized by {metricLabel} per country">
    <g class="land">
      {#each shapes as s}
        {#if s.iso}
          <path
            d={s.d}
            class="in"
            class:sel={selected === s.iso}
            role="button"
            tabindex="0"
            aria-label={nameOf(s.iso)}
            onclick={() => onselect(selected === s.iso ? null : s.iso)}
            onkeydown={(e) => (e.key === "Enter" || e.key === " ") && onselect(selected === s.iso ? null : s.iso)}
            onmouseenter={() => (hover = { iso: s.iso, name: nameOf(s.iso), v: circles.find((c) => c.iso === s.iso)?.v || 0 })}
            onmouseleave={() => (hover = null)}
          ><title>{nameOf(s.iso)}</title></path>
        {:else}
          <path d={s.d} class="ctx"><title>{s.name} (not covered)</title></path>
        {/if}
      {/each}
    </g>
    <g class="bubbles">
      {#each circles as c (c.iso)}
        {#if c.nudged}<line x1={c.x} y1={c.y} x2={c.cx} y2={c.cy} class="leader" />{/if}
        <circle
          cx={c.cx} cy={c.cy} r={c.r}
          class:sel={selected === c.iso}
          role="button" tabindex="0" aria-label="{c.name}: {fmt(c.v)} {unit}"
          onclick={() => onselect(selected === c.iso ? null : c.iso)}
          onkeydown={(e) => (e.key === "Enter" || e.key === " ") && onselect(selected === c.iso ? null : c.iso)}
          onmouseenter={() => (hover = c)}
          onmouseleave={() => (hover = null)}
        ><title>{c.name}: {fmt(c.v)} {unit}</title></circle>
      {/each}
    </g>
    {#if legend.length}
      <g class="legend" transform="translate({20 + R_MAX}, {H - 18})">
        {#each legend as l}
          <circle cx="0" cy={-l.r} r={l.r} />
          <text x={R_MAX + 6} y={-2 * l.r + 4}>{fmt(l.v)}</text>
        {/each}
      </g>
    {/if}
  </svg>
  <figcaption>
    {#if hover}
      <strong>{hover.name}</strong> · <span class="num">{fmt(hover.v)}</span> {unit}
    {:else}
      Circle area is proportional to {metricLabel.toLowerCase()} ({unit}). Click a country to see its projects.
    {/if}
  </figcaption>
</figure>

<style>
  .map { margin: 0; }
  svg { width: 100%; height: auto; display: block; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
  .ctx { fill: var(--land); stroke: var(--surface); stroke-width: 0.6; }
  .in { fill: var(--land-in); stroke: var(--surface); stroke-width: 0.8; cursor: pointer; }
  .in:hover { fill: var(--land-in-hover); }
  .in.sel { fill: var(--land-in-hover); stroke: var(--accent); stroke-width: 1.4; }
  .bubbles circle { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.2; cursor: pointer; }
  .bubbles circle.sel { stroke-width: 2.6; fill: var(--accent); fill-opacity: 0.4; }
  .leader { stroke: var(--accent); stroke-width: 0.8; opacity: 0.7; }
  .legend circle { fill: none; stroke: var(--faint); }
  .legend text { font: 11px var(--mono); fill: var(--muted); }
  figcaption { font-size: 13px; color: var(--muted); padding: 6px 2px; min-height: 2.2em; }
</style>

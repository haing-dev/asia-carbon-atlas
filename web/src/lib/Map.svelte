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
  const shapes = all.map((f) => ({ iso: f.properties.iso, name: f.properties.n, d: path(f), area: path.area(f) }));

  // Tiny places get a dot + nudged label so they stay visible and clickable.
  const SMALL = new Set(["HKG", "MAC", "SGP", "BRN", "MDV", "TLS", "BTN"]);
  const NUDGE = { HKG: [22, 8], MAC: [-26, 18], SGP: [-10, 30], BRN: [26, -18], MDV: [-20, 18] };
  const anchors = {};
  for (const [iso, lonlat] of Object.entries(basemap.points)) {
    const [x, y] = projection(lonlat);
    const [dx, dy] = NUDGE[iso] || [0, 0];
    anchors[iso] = { x, y, lx: x + dx, ly: y + dy };
  }
  const nameOf = (iso) => countries.find((c) => c.id === iso)?.name || iso;

  let hover = $state(null);
  const hoverShape = $derived(hover ? shapes.find((x) => x.iso === hover.iso) : null);

  const values = $derived(new Map(countries.map((c, i) => [c.id, totals.get(i) || 0])));
  const vmax = $derived(Math.max(0, ...values.values()));
  // Colour intensity: square-root scale so mid-sized countries stay distinguishable from zero.
  const level = (v) => (v > 0 && vmax > 0 ? 0.12 + 0.88 * Math.sqrt(v / vmax) : 0);
  const fill = (v) => (v > 0 ? `color-mix(in oklab, var(--choro-hi) ${Math.round(level(v) * 100)}%, var(--choro-lo))` : null);

  // Label the biggest countries on the map (others on hover / in the ranking).
  const areaOf = Object.fromEntries(shapes.filter((s) => s.iso).map((s) => [s.iso, s.area]));
  // Greedy placement, biggest first; skip a label if it would overlap one already placed.
  const labels = $derived.by(() => {
    const ranked = [...values.entries()].filter(([iso, v]) => v > 0 && anchors[iso]).sort((a, b) => b[1] - a[1]);
    const placed = [];
    for (const [iso, v] of ranked) {
      if (placed.length >= 12) break;
      const a = anchors[iso];
      const small = SMALL.has(iso);
      const x = small ? a.lx + 8 : a.x, y = small ? a.ly + 4 : a.y;
      const w = Math.max(nameOf(iso).length, fmt(v).length) * 6.6 + 6;
      const box = small ? [x, y - 12, x + w, y + 16] : [x - w / 2, y - 12, x + w / 2, y + 16];
      if (placed.some((p) => box[0] < p.box[2] && box[2] > p.box[0] && box[1] < p.box[3] && box[3] > p.box[1])) continue;
      placed.push({ iso, v, x, y, box, small, dark: !small && level(v) > 0.55 && (areaOf[iso] || 0) > 4000 });
    }
    return placed;
  });
  const dots = $derived([...values.entries()].filter(([iso, v]) => v > 0 && SMALL.has(iso) && anchors[iso]).map(([iso, v]) => ({ iso, v, ...anchors[iso] })));

  const ticks = $derived(vmax > 0 ? [0.01, 0.1, 0.25, 0.5, 1].map((f) => f * vmax) : []);
</script>

<figure class="map">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Map of Asia shaded by {metricLabel} per country">
    <g class="land">
      {#each shapes as s}
        {#if s.iso}
          {@const v = values.get(s.iso) || 0}
          <path
            d={s.d}
            class="in"
            class:sel={selected === s.iso}
            class:zero={!v}
            style:fill={fill(v)}
            role="button"
            tabindex="0"
            aria-label="{nameOf(s.iso)}: {fmt(v)} {unit}"
            onclick={() => onselect(selected === s.iso ? null : s.iso)}
            onkeydown={(e) => (e.key === "Enter" || e.key === " ") && onselect(selected === s.iso ? null : s.iso)}
            onmouseenter={() => (hover = { iso: s.iso, name: nameOf(s.iso), v })}
            onmouseleave={() => (hover = null)}
          ><title>{nameOf(s.iso)}: {fmt(v)} {unit}</title></path>
        {:else}
          <path d={s.d} class="ctx"><title>{s.name} (not covered)</title></path>
        {/if}
      {/each}
    </g>
    {#if hover && hoverShape}
      <!-- Hovered country redrawn on top, lifted with a shadow (pointer events pass through to the real shape). -->
      <path d={hoverShape.d} class="lift" style:fill={fill(hover.v) || "var(--land-in)"} aria-hidden="true" />
    {/if}
    <g class="dots">
      {#each dots as d (d.iso)}
        {#if d.lx !== d.x || d.ly !== d.y}<line x1={d.x} y1={d.y} x2={d.lx} y2={d.ly} />{/if}
        <circle cx={d.lx} cy={d.ly} r="4.5" style:fill={fill(d.v)} class:sel={selected === d.iso}
          role="button" tabindex="0" aria-label="{nameOf(d.iso)}: {fmt(d.v)} {unit}"
          onclick={() => onselect(selected === d.iso ? null : d.iso)}
          onkeydown={(e) => (e.key === "Enter" || e.key === " ") && onselect(selected === d.iso ? null : d.iso)}
          onmouseenter={() => (hover = { iso: d.iso, name: nameOf(d.iso), v: d.v })} onmouseleave={() => (hover = null)}
        ><title>{nameOf(d.iso)}: {fmt(d.v)} {unit}</title></circle>
      {/each}
    </g>
    <g class="labels" aria-hidden="true">
      {#each labels as l (l.iso)}
        <text x={l.x} y={l.y} class:dark={l.dark} class:left={l.small}>
          <tspan class="n">{nameOf(l.iso)}</tspan>
          <tspan class="v" x={l.x} dy="13">{fmt(l.v)}</tspan>
        </text>
      {/each}
    </g>
    {#if ticks.length}
      <g class="legend" transform="translate(24, {H - 46})">
        <text x="0" y="-8" class="lt">{unit}</text>
        {#each ticks as t, i}
          <rect x={i * 46} y="0" width="44" height="10" style:fill={fill(t)} />
          <text x={i * 46} y="24">{fmt(t)}</text>
        {/each}
      </g>
    {/if}
  </svg>
  <figcaption>
    {#if hover}<strong>{hover.name}</strong> · <span class="num">{fmt(hover.v)}</span> {unit}{/if}
  </figcaption>
</figure>

<style>
  .map { margin: 0; }
  svg { width: 100%; height: auto; display: block; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
  .ctx { fill: var(--land); stroke: var(--surface); stroke-width: 0.6; }
  .in { fill: var(--land-in); stroke: var(--surface); stroke-width: 0.8; cursor: pointer; transition: fill 0.2s; }
  .in.zero { fill: var(--land-in); }
  .lift { stroke: var(--ink); stroke-width: 1; pointer-events: none; transform: translate(-1.5px, -3px);
    filter: drop-shadow(0 4px 5px rgba(0, 0, 0, 0.35)); transition: transform 0.12s ease-out; }
  .in.sel { stroke: var(--ink); stroke-width: 2; }
  .dots line { stroke: var(--muted); stroke-width: 0.8; }
  .dots circle { stroke: var(--ink); stroke-width: 0.8; cursor: pointer; }
  .dots circle.sel { stroke-width: 2.2; }
  .labels text { font: 600 11.5px var(--font); fill: var(--ink); text-anchor: middle; paint-order: stroke; stroke: var(--surface); stroke-width: 3px; stroke-linejoin: round; pointer-events: none; }
  .labels text.left { text-anchor: start; }
  .labels text.dark { fill: #fff; stroke: rgba(0, 0, 0, 0.25); stroke-width: 2.5px; }
  .labels .v { font: 500 10.5px var(--mono); }
  .legend text { font: 10.5px var(--mono); fill: var(--muted); }
  .legend .lt { font-family: var(--font); }
  figcaption { font-size: 13px; color: var(--muted); padding: 6px 2px; min-height: 2.2em; }
</style>

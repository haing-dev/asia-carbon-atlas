<script>
  import { geoMercator, geoPath } from "d3-geo";
  import { feature } from "topojson-client";
  import basemap from "./basemap.json";
  import { fmt } from "./data.js";

  let { totals, countries, selected = null, highlight = null, metricLabel, unit, onselect, onhover = () => {} } = $props();

  const W = 960, H = 600;
  const all = feature(basemap.topo, basemap.topo.objects.countries).features;
  const inScope = all.filter((f) => f.properties.iso);
  const projection = geoMercator().fitExtent([[16, 16], [W - 16, H - 16]], { type: "FeatureCollection", features: inScope });
  const path = geoPath(projection);
  const shapes = all.map((f) => ({ iso: f.properties.iso, name: f.properties.n, d: path(f), area: path.area(f), b: path.bounds(f) }));
  const shapeOf = Object.fromEntries(shapes.filter((s) => s.iso).map((s) => [s.iso, s]));

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

  let hoverIso = $state(null);
  function enter(iso) { hoverIso = iso; onhover(iso); }
  function leave() { hoverIso = null; onhover(null); }
  // Hover on the map or on a ranking row both focus a country.
  const focus = $derived(hoverIso || highlight);

  const values = $derived(new Map(countries.map((c, i) => [c.id, totals.get(i) || 0])));
  const vmax = $derived(Math.max(0, ...values.values()));
  const vsum = $derived([...values.values()].reduce((a, b) => a + b, 0));
  // Colour intensity: square-root scale so mid-sized countries stay distinguishable from zero.
  const level = (v) => (v > 0 && vmax > 0 ? 0.12 + 0.88 * Math.sqrt(v / vmax) : 0);
  const fill = (v) => (v > 0 ? `color-mix(in oklab, var(--choro-hi) ${Math.round(level(v) * 100)}%, var(--choro-lo))` : null);

  // The focused country, redrawn on top and enlarged around its label point.
  const lifted = $derived.by(() => {
    const sh = focus && shapeOf[focus];
    if (!sh) return null;
    const a = anchors[focus] || { x: (sh.b[0][0] + sh.b[1][0]) / 2, y: (sh.b[0][1] + sh.b[1][1]) / 2 };
    const k = sh.area > 30000 ? 1.04 : sh.area > 3000 ? 1.09 : 1.2;
    const v = values.get(focus) || 0;
    // Tooltip above the country, or below it when the country touches the top edge.
    const below = sh.b[0][1] < 80;
    return { ...sh, ax: a.x, ay: a.y, k, v, below, top: below ? sh.b[1][1] * (1 + (k - 1) / 2) + 6 : Math.max(8, sh.b[0][1] - 8) };
  });

  // Every covered country gets a label: name (+ value when it has one). Greedy placement, biggest first,
  // trying a few positions around the label point; tiny places sit beside their dot.
  const labels = $derived.by(() => {
    const ranked = countries.map((c) => [c.id, values.get(c.id) || 0]).filter(([iso]) => anchors[iso])
      .sort((a, b) => b[1] - a[1]);
    const placed = [];
    const hit = (box) => placed.some((p) => box[0] < p.box[2] && box[2] > p.box[0] && box[1] < p.box[3] && box[3] > p.box[1]);
    for (const [iso, v] of ranked) {
      const a = anchors[iso], small = SMALL.has(iso), two = v > 0;
      const w = Math.max(nameOf(iso).length * 6.4, two ? fmt(v).length * 6.6 : 0) + 6, h = two ? 27 : 14;
      const tries = small ? [[a.lx + 8, a.ly + 4, "start"], [a.lx - 8, a.ly + 4, "end"]]
        : [[a.x, a.y, "middle"], [a.x, a.y + 15, "middle"], [a.x, a.y - 15, "middle"], [a.x + w / 2 + 6, a.y, "middle"], [a.x - w / 2 - 6, a.y, "middle"]];
      for (const [x, y, anchor] of tries) {
        const x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
        const box = [x0, y - 12, x0 + w, y - 12 + h];
        if (box[0] < 2 || box[2] > W - 2 || hit(box)) continue;
        placed.push({ iso, v, x, y, box, anchor, onFill: !small && level(v) > 0.55 && (shapeOf[iso]?.area || 0) > 4000 });
        break;
      }
    }
    return placed;
  });
  const dots = $derived([...values.entries()].filter(([iso]) => SMALL.has(iso) && anchors[iso]).map(([iso, v]) => ({ iso, v, ...anchors[iso] })));

  const ticks = $derived(vmax > 0 ? [0.01, 0.1, 0.25, 0.5, 1].map((f) => f * vmax) : []);
</script>

<figure class="map">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Map of Asia shaded by {metricLabel} per country">
    <g class="land" class:focusing={!!focus}>
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
            onmouseenter={() => enter(s.iso)}
            onmouseleave={leave}
            onfocus={() => enter(s.iso)}
            onblur={leave}
          ></path>
        {:else}
          <path d={s.d} class="ctx"><title>{s.name} (not covered)</title></path>
        {/if}
      {/each}
    </g>
    {#if lifted}
      <!-- Focused country redrawn on top, enlarged around its label point (pointer events pass through). -->
      <path d={lifted.d} class="lift" style:fill={fill(lifted.v) || "var(--land-in-hover)"} aria-hidden="true"
        transform="translate({lifted.ax} {lifted.ay - 2}) scale({lifted.k}) translate({-lifted.ax} {-lifted.ay})" />
    {/if}
    <g class="dots">
      {#each dots as d (d.iso)}
        {#if d.lx !== d.x || d.ly !== d.y}<line x1={d.x} y1={d.y} x2={d.lx} y2={d.ly} />{/if}
        <circle cx={d.lx} cy={d.ly} r={focus === d.iso ? 7 : 4.5} style:fill={fill(d.v) || "var(--land-in-hover)"} class:sel={selected === d.iso} class:on={focus === d.iso}
          role="button" tabindex="0" aria-label="{nameOf(d.iso)}: {fmt(d.v)} {unit}"
          onclick={() => onselect(selected === d.iso ? null : d.iso)}
          onkeydown={(e) => (e.key === "Enter" || e.key === " ") && onselect(selected === d.iso ? null : d.iso)}
          onmouseenter={() => enter(d.iso)} onmouseleave={leave}
        ></circle>
      {/each}
    </g>
    <g class="labels" class:focusing={!!focus} aria-hidden="true">
      {#each labels as l (l.iso)}
        <text x={l.x} y={l.y} class:onfill={l.onFill} class:zero={!l.v} class:on={focus === l.iso} style:text-anchor={l.anchor}>
          <tspan class="n">{nameOf(l.iso)}</tspan>
          {#if l.v}<tspan class="v" x={l.x} dy="13">{fmt(l.v)}</tspan>{/if}
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
  {#if lifted}
    <div class="tip" class:below={lifted.below} style:left="{(lifted.ax / W) * 100}%" style:top="{(lifted.top / H) * 100}%">
      <strong>{nameOf(focus)}</strong>
      <span class="num">{fmt(lifted.v)} {unit}</span>
      {#if vsum > 0 && lifted.v > 0}<span class="muted">{((lifted.v / vsum) * 100).toFixed(lifted.v / vsum >= 0.1 ? 0 : 1)}% of total</span>{/if}
    </div>
  {/if}
</figure>

<style>
  .map { margin: 0; position: relative; }
  svg { width: 100%; height: auto; display: block; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
  .ctx { fill: var(--land); stroke: var(--surface); stroke-width: 0.6; }
  .in { fill: var(--land-in); stroke: var(--surface); stroke-width: 0.8; cursor: pointer; transition: fill 0.2s, opacity 0.15s; outline: none; }
  .land.focusing .in { opacity: 0.38; }
  .in.sel { stroke: var(--ink); stroke-width: 2; }
  .lift { stroke: var(--ink); stroke-width: 1.6; vector-effect: non-scaling-stroke; pointer-events: none;
    filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.6)); }
  .dots line { stroke: var(--muted); stroke-width: 0.8; }
  .dots circle { stroke: var(--ink); stroke-width: 0.8; cursor: pointer; transition: r 0.12s; }
  .dots circle.sel, .dots circle.on { stroke-width: 2.2; }
  .labels text { font: 600 11.5px var(--font); fill: var(--ink); paint-order: stroke; stroke: var(--surface); stroke-width: 3px; stroke-linejoin: round; pointer-events: none; transition: opacity 0.15s; }
  .labels text.zero { font-weight: 500; font-size: 10.5px; fill: var(--muted); }
  .labels text.onfill { fill: #0d2023; stroke: none; }
  .labels.focusing text:not(.on) { opacity: 0.3; }
  .labels .v { font: 500 10.5px var(--mono); }
  .legend text { font: 10.5px var(--mono); fill: var(--muted); }
  .legend .lt { font-family: var(--font); }
  .tip { position: absolute; transform: translate(-50%, -100%); pointer-events: none; background: var(--surface); border: 1px solid var(--accent);
    border-radius: 8px; padding: 6px 10px; font-size: 13px; line-height: 1.35; display: grid; text-align: center; white-space: nowrap;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45); z-index: 2; }
  .tip.below { transform: translate(-50%, 0); }
  .tip strong { font-size: 14px; }
  @media (prefers-reduced-motion: reduce) { .in, .labels text, .dots circle { transition: none; } }
</style>

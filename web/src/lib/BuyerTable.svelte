<script>
  // Top 15 buyers through one of three lenses (retired / issued / announced); bars split by credit type.
  // Click a buyer for its projects (announced, issued, retired per project); the name opens the buyer profile.
  import BuyerProjects from "./BuyerProjects.svelte";
  import { L1_COLORS, fmt } from "./data.js";

  let { meta, data, l1, l2, top = 15, onprofile } = $props();

  const LENSES = {
    re: { label: "Retired", sub: () => `Credits retired in the buyer's name in registry records (Verra, Gold Standard, ACR, CAR, ART TREES), as of ${data.retired_as_of || "—"}.` },
    is: { label: "Issued", sub: () => "Announced deal volumes on projects that are already issuing credits." },
    an: { label: "Announced", sub: () => "Announced deal volumes on projects not issuing yet, or not yet registered (announcement only)." },
  };
  let lens = $state("re");
  const val = (e, k) => (k === "re" ? e.re : k === "is" ? (e.iss ? e.an || 0 : 0) : (!e.iss ? e.an || 0 : 0));

  const L1_ORDER = $derived(Object.fromEntries(l1.map((x, i) => [x.id, i])));
  const rows = $derived(data.list.filter((b) => b[lens] > 0).sort((a, b) => b[lens] - a[lens]).slice(0, top).map((b) => {
    const by = new Map();
    for (const e of b.p) { const v = val(e, lens); if (v) by.set(e.l2, (by.get(e.l2) || 0) + v); }
    const segs = [...by.entries()].map(([k, v]) => ({ l2: k, l1: l2[k]?.l1 || "other", label: l2[k]?.label || k, v }))
      .sort((a, b) => L1_ORDER[a.l1] - L1_ORDER[b.l1] || b.v - a.v);
    return { ...b, total: b[lens], segs };
  }));
  const vmax = $derived(Math.max(1, ...rows.map((r) => r.total)));
  // Square-root scale: the largest buyers are 1,000x the smallest, so a linear scale leaves most bars as slivers.
  const width = (v) => 4 + 92 * Math.sqrt(v / vmax);
  const usedL1 = $derived(l1.filter((x) => rows.some((r) => r.segs.some((s) => s.l1 === x.id))));

  let open = $state(null);
  let tip = $state(null);
  $effect(() => { lens; open = null; });
</script>

<section class="bt">
  <div class="head">
    <div>
      <h2>Top buyers, all regions</h2>
      <p class="muted sub">{LENSES[lens].sub()} Top {top} by volume (tCO₂e); bars split by credit type. Click a buyer for its projects.</p>
    </div>
    <div class="lens" role="tablist" aria-label="Lens" style:--i={Object.keys(LENSES).indexOf(lens)}>
      <span class="thumb" aria-hidden="true"></span>
      {#each Object.entries(LENSES) as [k, l]}
        <button role="tab" aria-selected={lens === k} onclick={() => (lens = k)}>{l.label}</button>
      {/each}
    </div>
  </div>
  {#if !rows.length}
    <p class="muted">No buyers with a stated volume yet.</p>
  {:else}
    <div class="legend">
      {#each usedL1 as x}<span><i style:background={L1_COLORS[x.id]}></i>{x.label}</span>{/each}
    </div>
    <ol class="bars">
      {#each rows as r, i (r.n)}
        <li class:open={open === r.n}>
          <div class="row" role="button" tabindex="0" aria-expanded={open === r.n}
            onclick={(e) => { if (!e.target.closest(".nm")) open = open === r.n ? null : r.n; }}
            onkeydown={(e) => (e.key === "Enter" || e.key === " ") && !e.target.closest(".nm") && (e.preventDefault(), (open = open === r.n ? null : r.n))}>
            <span class="name"><span class="rk">{i + 1}</span><button class="nm" title="{r.n} — open buyer profile" onclick={() => onprofile(r.n)}>{r.n}</button></span>
            <span class="track">
              <span class="bar" style:width="{width(r.total)}%">
                {#each r.segs as s}
                  <span class="seg" style:flex-grow={s.v} style:background={L1_COLORS[s.l1]}
                    onmouseenter={() => (tip = { buyer: r.n, ...s, pct: s.v / r.total })} onmouseleave={() => (tip = null)}>{#if (s.v / r.total) * width(r.total) > 14}<span class="sl">{s.label}</span>{/if}</span>
                {/each}
              </span>
              <span class="tot num">{fmt(r.total)}</span>
            </span>
            <span class="chev" aria-hidden="true">{open === r.n ? "▴" : "▾"}</span>
          </div>
          {#if tip && tip.buyer === r.n}
            <div class="segtip">{tip.label}: <span class="num">{fmt(tip.v)}</span> tCO₂e ({(tip.pct * 100).toFixed(0)}%)</div>
          {/if}
          {#if open === r.n}
            <div class="deals">
              <div class="mix">
                {#each r.segs as s}<span><i style:background={L1_COLORS[s.l1]}></i>{s.label} <span class="num">{fmt(s.v)}</span> ({((s.v / r.total) * 100).toFixed(0)}%)</span>{/each}
              </div>
              <BuyerProjects {meta} buyer={r} {l2} {lens} limit={12} {onprofile} />
            </div>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .bt { margin-top: 22px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 12px 14px 10px; }
  .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
  h2 { font-size: 18px; margin: 0; }
  .sub { margin: 3px 0 8px; font-size: 12.5px; max-width: 720px; }
  .lens { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); width: 330px; max-width: 100%; background: var(--chip);
    border: 1px solid var(--line); border-radius: 999px; padding: 3px; }
  .lens button { position: relative; z-index: 1; border: 0; background: none; padding: 5px 10px; border-radius: 999px; cursor: pointer;
    font-size: 13.5px; font-weight: 600; color: var(--muted); transition: color 0.2s; }
  .lens button[aria-selected="true"] { color: #0d2023; }
  .lens .thumb { position: absolute; top: 3px; bottom: 3px; left: 3px; width: calc((100% - 6px) / 3); border-radius: 999px;
    background: var(--choro-hi); transform: translateX(calc(100% * var(--i))); transition: transform 0.25s ease; }
  @media (prefers-reduced-motion: reduce) { .lens .thumb, .lens button { transition: none; } }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12px; color: var(--muted); margin-bottom: 8px; }
  .legend i, .mix i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  .bars { list-style: none; margin: 0; padding: 0; }
  .bars li { border-top: 1px solid var(--line); position: relative; }
  .row { display: grid; grid-template-columns: minmax(140px, 260px) 1fr 14px; gap: 12px; align-items: center; padding: 6px 2px; cursor: pointer; }
  .row:hover, .open .row { background: var(--chip); }
  .name { font-size: 14px; font-weight: 600; display: flex; min-width: 0; }
  .rk { flex: none; }
  .nm { background: none; border: 0; padding: 0; font: inherit; color: var(--ink); cursor: pointer; text-align: left;
    min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .nm:hover { color: var(--accent); text-decoration: underline; }
  .rk { display: inline-block; width: 22px; color: var(--faint); font-weight: 500; }
  .track { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .bar { display: flex; height: 24px; min-width: 4px; border-radius: 4px; overflow: hidden; }
  .seg { height: 100%; min-width: 3px; border-right: 2px solid var(--surface); display: flex; align-items: center; overflow: hidden; }
  .seg:last-child { border-right: 0; }
  .seg:hover { filter: brightness(1.25); }
  .sl { font-size: 11px; font-weight: 600; color: #0d2023; padding: 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tot { font-size: 13px; color: var(--ink); white-space: nowrap; }
  .chev { color: var(--faint); font-size: 11px; }
  .segtip { position: absolute; right: 8px; top: -22px; background: var(--surface); border: 1px solid var(--accent); border-radius: 6px;
    padding: 2px 8px; font-size: 12px; z-index: 3; pointer-events: none; white-space: nowrap; }
  .deals { padding: 4px 4px 12px 26px; font-size: 12.5px; }
  .mix { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 2px 0 6px; color: var(--muted); }
</style>

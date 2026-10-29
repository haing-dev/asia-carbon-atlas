<script>
  // Top 15 buyers through one of three lenses (retired / issued / announced); bars split by credit type.
  // Click a buyer for its projects (announced, issued, retired per project); the name opens the buyer profile.
  import BuyerProjects from "./BuyerProjects.svelte";
  import RegionSwitch from "./RegionSwitch.svelte";
  import { L1_COLORS, L1_TEXT, fmt } from "./data.js";

  let { meta, data, l1, l2, top = 15, onprofile } = $props();
  let region = $state("all");
  let noGov = $state(false);   // leave out governments, public agencies and multilateral funds

  const LENSES = {
    re: { label: "Retired", tip: () => `Credits retired in the buyer's name in registry records, as of ${data.retired_as_of || "—"}` },
    is: { label: "Issued", tip: () => "Announced deals on projects already issuing credits" },
    an: { label: "Announced", tip: () => "Announced deals on projects not issuing yet, or not yet registered" },
  };
  let lens = $state("re");
  const val = (e, k) => (k === "re" ? e.re : k === "is" ? (e.iss ? e.an || 0 : 0) : (!e.iss ? e.an || 0 : 0))
    * (region === "all" ? 1 : e.aw?.[region] || 0);

  const L1_ORDER = $derived(Object.fromEntries(l1.map((x, i) => [x.id, i])));
  const rows = $derived(data.list.filter((b) => !(noGov && b.g)).map((b) => {
    const by = new Map();
    let total = 0;
    for (const e of b.p) { const v = val(e, lens); if (v) { by.set(e.l2, (by.get(e.l2) || 0) + v); total += v; } }
    return { b, by, total };
  }).filter((x) => x.total > 0).sort((x, y) => y.total - x.total).slice(0, top).map(({ b, by, total }) => {
    const segs = [...by.entries()].map(([k, v]) => ({ l2: k, l1: l2[k]?.l1 || "other", label: l2[k]?.label || k, v }))
      .sort((a, c) => L1_ORDER[a.l1] - L1_ORDER[c.l1] || c.v - a.v);
    const p = region === "all" ? b.p : b.p.filter((e) => e.aw?.[region]);
    return { ...b, p, total, segs };
  }));
  const vmax = $derived(Math.max(1, ...rows.map((r) => r.total)));
  // Square-root scale: the largest buyers are 1,000x the smallest, so a linear scale leaves most bars as slivers.
  const width = (v) => 4 + 92 * Math.sqrt(v / vmax);
  const usedL1 = $derived(l1.filter((x) => rows.some((r) => r.segs.some((s) => s.l1 === x.id))));

  let open = $state(null);
  let tip = $state(null);
  $effect(() => { lens; region; noGov; open = null; });
</script>

<section class="bt">
  <div class="head">
    <h2>Which credit types are top global offtakers procuring?</h2>
    <div class="ctl">
      <RegionSwitch areas={meta.areas} bind:value={region} />
      <div class="lens" role="tablist" aria-label="Lens" style:--i={Object.keys(LENSES).indexOf(lens)}>
        <span class="thumb" aria-hidden="true"></span>
        {#each Object.entries(LENSES) as [k, l]}
          <button role="tab" aria-selected={lens === k} title={l.tip()} onclick={() => (lens = k)}>{l.label}</button>
        {/each}
      </div>
      <label class="gov" title="Governments, public agencies, multilateral carbon funds (e.g. World Bank FCPF) and government-led coalitions (LEAF, KliK)">
        <input type="checkbox" bind:checked={noGov} /> Exclude governments</label>
    </div>
  </div>
  {#if !rows.length}
    <p class="muted">No buyers with a stated volume in this region yet.</p>
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
                    onmouseenter={() => (tip = { buyer: r.n, ...s, pct: s.v / r.total })} onmouseleave={() => (tip = null)}>{#if (s.v / r.total) * width(r.total) > 14}<span class="sl" style:color={L1_TEXT[s.l1]}>{s.label}</span>{/if}</span>
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
  .bt { margin-top: 36px; border: 0; border-top: 1px solid var(--black); border-radius: 0; background: none; padding: 14px 0 10px; }
  .head { display: grid; gap: 10px; margin-bottom: 10px; }
  h2 { font: 700 22px/1.25 var(--serif); margin: 0; }
  .gov { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); cursor: pointer; white-space: nowrap; }
  .ctl { display: flex; justify-content: flex-start; align-items: center; gap: 10px; flex-wrap: wrap; }
  .lens { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); width: 330px; max-width: 100%; background: var(--white);
    border: 1px solid var(--black); border-radius: 0; padding: 2px; }
  .lens button { position: relative; z-index: 1; border: 0; background: none; padding: 5px 10px; border-radius: 0; cursor: pointer;
    font-size: 13.5px; font-weight: 700; color: var(--black); transition: color 0.2s; }
  .lens button[aria-selected="true"] { color: var(--white); }
  .lens .thumb { position: absolute; top: 2px; bottom: 2px; left: 2px; width: calc((100% - 4px) / 3); border-radius: 0;
    background: var(--deep-blue); transform: translateX(calc(100% * var(--i))); transition: transform 0.25s ease; }
  @media (prefers-reduced-motion: reduce) { .lens .thumb, .lens button { transition: none; } }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12px; color: var(--muted); margin-bottom: 8px; }
  .legend i, .mix i { display: inline-block; width: 10px; height: 10px; margin-right: 5px; vertical-align: -1px; }
  .bars { list-style: none; margin: 0; padding: 0; }
  .bars li { border-top: 1px solid var(--line); position: relative; }
  .bars li:first-child { border-top: 0; }
  .row { display: grid; grid-template-columns: minmax(140px, 260px) 1fr 14px; gap: 12px; align-items: center; padding: 6px 2px; cursor: pointer; }
  .row:hover, .open .row { background: var(--gray-pale); }
  .name { font-size: 14px; font-weight: 700; display: flex; min-width: 0; }
  .rk { flex: none; }
  .nm { background: none; border: 0; padding: 0; font: inherit; color: var(--ink); cursor: pointer; text-align: left;
    min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .nm:hover { color: var(--electric-blue); text-decoration: underline; }
  .rk { display: inline-block; width: 22px; color: var(--faint); font-weight: 500; }
  .track { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .bar { display: flex; height: 24px; min-width: 4px; overflow: hidden; }
  .seg { height: 100%; min-width: 3px; border-right: 1px solid var(--white); display: flex; align-items: center; overflow: hidden; }
  .seg:last-child { border-right: 0; }
  .seg:hover { opacity: 0.85; }
  .sl { font-size: 11px; font-weight: 700; padding: 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tot { font-size: 13px; color: var(--ink); white-space: nowrap; }
  .chev { color: var(--faint); font-size: 11px; }
  .segtip { position: absolute; right: 8px; top: -22px; background: var(--gray-pale); border: 0; border-top: 1px solid var(--black);
    padding: 2px 8px; font-size: 12px; z-index: 3; pointer-events: none; white-space: nowrap; }
  .deals { padding: 4px 4px 12px 26px; font-size: 12.5px; }
  .mix { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 2px 0 6px; color: var(--muted); }
</style>

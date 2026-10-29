<script>
  import { fmt } from "./data.js";

  let { totals, countries, selected = null, highlight = null, unit, onselect, onhover = () => {} } = $props();

  const rows = $derived.by(() => {
    const list = countries.map((c, i) => ({ ...c, v: totals.get(i) || 0 })).filter((d) => d.v > 0).sort((a, b) => b.v - a.v);
    const max = list[0]?.v || 1;
    const total = list.reduce((a, d) => a + d.v, 0) || 1;
    return list.map((d) => ({ ...d, w: (d.v / max) * 100, pct: (d.v / total) * 100 }));
  });
</script>

<div class="ranking" role="list" aria-label="Countries ranked">
  <div class="head"><span>Country</span><span>{unit}</span></div>
  {#each rows as r (r.id)}
    <button class="row" class:sel={selected === r.id} class:hl={highlight === r.id} role="listitem" onclick={() => onselect(selected === r.id ? null : r.id)}
      onmouseenter={() => onhover(r.id)} onmouseleave={() => onhover(null)} onfocus={() => onhover(r.id)} onblur={() => onhover(null)}>
      <img src="/flags/{r.id}.svg" alt="" width="18" height="13.5" loading="lazy" />
      <span class="name">{r.name}</span>
      <span class="val num">{fmt(r.v)} <small>{r.pct >= 0.1 ? r.pct.toFixed(r.pct >= 10 ? 0 : 1) : "<0.1"}%</small></span>
      <span class="bar" style:width="{Math.max(r.w, 0.6)}%"></span>
    </button>
  {:else}
    <p class="muted empty">No volume for these filters.</p>
  {/each}
</div>

<style>
  .ranking { border: 0; border-top: 1px solid var(--black); border-radius: 0; background: none; padding: 8px 0; overflow: auto; }
  .head { display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; color: var(--black); padding: 2px 4px 6px; border-bottom: 1px solid var(--rule); }
  .row { display: grid; grid-template-columns: 22px 1fr auto; grid-template-rows: auto 5px; align-items: center; column-gap: 6px; row-gap: 3px;
    width: 100%; background: none; border: 0; border-radius: 0; padding: 5px 4px; cursor: pointer; text-align: left; font-size: 13px; }
  .row:hover, .row.hl { background: var(--chip); }
  .row.sel { background: var(--accent-soft); }
  img { outline: 1px solid var(--gray-super-light); }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .val small { color: var(--muted); font-size: 10.5px; }
  .bar { grid-column: 2 / 4; height: 5px; background: var(--deep-blue); }
  .empty { font-size: 13px; padding: 8px 4px; }
</style>

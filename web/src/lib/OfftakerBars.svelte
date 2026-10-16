<script>
  // Top buyers by announced volume, each bar split by the credit types bought; click a bar for that buyer's deals.
  import { L1_COLORS, fmt, fmtFull } from "./data.js";

  let { title, subtitle, data, l1, l2, names, top = 10 } = $props();

  const L1_ORDER = $derived(Object.fromEntries(l1.map((x, i) => [x.id, i])));
  const rows = $derived(data.buyers.filter((b) => b.volume > 0).slice(0, top).map((b) => {
    const by = new Map();
    for (const d of b.deals) if (d.v) by.set(d.l2, (by.get(d.l2) || 0) + d.v);
    const segs = [...by.entries()].map(([k, v]) => ({ l2: k, l1: l2[k]?.l1 || "other", label: l2[k]?.label || k, v }))
      .sort((a, b) => L1_ORDER[a.l1] - L1_ORDER[b.l1] || b.v - a.v);
    return { ...b, segs };
  }));
  const vmax = $derived(Math.max(1, ...rows.map((r) => r.volume)));
  // Square-root scale: the largest deals are 1,000x the smallest, so a linear scale leaves most bars as slivers.
  const width = (v) => 4 + 96 * Math.sqrt(v / vmax);
  const usedL1 = $derived(l1.filter((x) => rows.some((r) => r.segs.some((s) => s.l1 === x.id))));

  let open = $state(null);
  let tip = $state(null);
  const country = (d) => d.c.map((c) => names[c] || c).join(", ");
</script>

<section class="ob">
  <h3>{title}</h3>
  <p class="muted sub">{subtitle}</p>
  {#if !rows.length}
    <p class="muted">No deals with a stated volume yet.</p>
  {:else}
    <div class="legend">
      {#each usedL1 as x}<span><i style:background={L1_COLORS[x.id]}></i>{x.label}</span>{/each}
    </div>
    <ol class="bars">
      {#each rows as r, i (r.name)}
        <li class:open={open === r.name}>
          <button class="row" aria-expanded={open === r.name} onclick={() => (open = open === r.name ? null : r.name)}>
            <span class="name"><span class="rk">{i + 1}</span>{r.name}</span>
            <span class="track">
              <span class="bar" style:width="{width(r.volume)}%">
                {#each r.segs as s}
                  <span class="seg" style:flex-grow={s.v} style:background={L1_COLORS[s.l1]}
                    onmouseenter={() => (tip = { buyer: r.name, ...s, pct: s.v / r.volume })} onmouseleave={() => (tip = null)}>{#if (s.v / r.volume) * width(r.volume) > 14}<span class="sl">{s.label}</span>{/if}</span>
                {/each}
              </span>
              <span class="tot num">{fmt(r.volume)}</span>
            </span>
          </button>
          {#if tip && tip.buyer === r.name}
            <div class="segtip">{tip.label}: <span class="num">{fmt(tip.v)}</span> tCO₂e ({(tip.pct * 100).toFixed(0)}%)</div>
          {/if}
          {#if open === r.name}
            <div class="deals">
              <div class="mix">
                {#each r.segs as s}<span><i style:background={L1_COLORS[s.l1]}></i>{s.label} <span class="num">{fmt(s.v)}</span> ({((s.v / r.volume) * 100).toFixed(0)}%)</span>{/each}
              </div>
              <table>
                <thead><tr><th>Project / supplier</th><th>Country</th><th>Type</th><th class="n">Volume</th><th>Date</th></tr></thead>
                <tbody>
                  {#each r.deals as d}
                    <tr>
                      <td><a href={d.u} target="_blank" rel="noopener" title="Open the announcement">{d.project}</a></td>
                      <td>{country(d)}</td>
                      <td><i class="dot" style:background={L1_COLORS[d.l1]}></i>{l2[d.l2]?.label || d.l2}</td>
                      <td class="n num">{d.v ? fmtFull(d.v) : "not stated"}</td>
                      <td class="num">{d.d || "—"}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .ob { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 12px 14px 10px; }
  h3 { margin: 0; font-size: 15px; }
  .sub { margin: 2px 0 8px; font-size: 12.5px; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12px; color: var(--muted); margin-bottom: 8px; }
  .legend i, .mix i, .dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  .bars { list-style: none; margin: 0; padding: 0; }
  .bars li { border-top: 1px solid var(--line); position: relative; }
  .row { display: grid; grid-template-columns: minmax(140px, 260px) 1fr; gap: 12px; align-items: center; width: 100%; background: none; border: 0;
    padding: 6px 2px; cursor: pointer; text-align: left; color: inherit; font: inherit; }
  .row:hover, .open .row { background: var(--chip); }
  .name { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rk { display: inline-block; width: 18px; color: var(--faint); font-weight: 500; }
  .track { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .bar { display: flex; height: 24px; min-width: 4px; border-radius: 4px; overflow: hidden; }
  .seg { height: 100%; min-width: 3px; border-right: 2px solid var(--surface); display: flex; align-items: center; overflow: hidden; }
  .sl { font-size: 11px; font-weight: 600; color: #0d2023; padding: 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .seg:last-child { border-right: 0; }
  .seg:hover { filter: brightness(1.25); }
  .tot { font-size: 13px; color: var(--ink); white-space: nowrap; }
  .segtip { position: absolute; right: 8px; top: -22px; background: var(--surface); border: 1px solid var(--accent); border-radius: 6px;
    padding: 2px 8px; font-size: 12px; z-index: 3; pointer-events: none; white-space: nowrap; }
  .deals { padding: 4px 4px 10px 30px; font-size: 12.5px; }
  .mix { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 2px 0 6px; color: var(--muted); }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 3px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { font-weight: 600; color: var(--muted); }
  .n { text-align: right; }
</style>

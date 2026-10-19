<script>
  // Per credit type, all regions: how much of what was issued has been retired, and how long projects take to first issuance.
  import { L1_COLORS, fmt } from "./data.js";

  let { types, l1, l2 } = $props();

  let sortKey = $state("is");
  let sortDir = $state(-1);
  let all = $state(false);
  const l1Label = $derived(Object.fromEntries(l1.map((x) => [x.id, x.label])));
  const key = (r) => ({ type: l2[r.l2]?.label || r.l2, n: r.n, is: r.is, re: r.re, share: r.share ?? -1, tt: r.tt ? r.tt[0] : 99 })[sortKey];
  const rows = $derived([...types].sort((a, b) => {
    const x = key(a), y = key(b);
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * sortDir;
  }));
  const shown = $derived(all ? rows : rows.slice(0, 15));
  const TMAX = 10;   // years shown on the timing bar; longer spans are clipped
  const pos = (y) => `${(Math.min(y, TMAX) / TMAX) * 100}%`;
  function sortBy(k) {
    if (sortKey === k) sortDir = -sortDir;
    else { sortKey = k; sortDir = k === "type" || k === "tt" ? 1 : -1; }
  }
  const COLS = [
    { k: "type", label: "Credit type" }, { k: "n", label: "Projects issuing", num: true }, { k: "is", label: "Issued", unit: "tCO₂e", num: true },
    { k: "re", label: "Retired", unit: "tCO₂e", num: true }, { k: "share", label: "Retired share", unit: "of issued" },
    { k: "tt", label: "Years to first issuance", unit: "median · bar = middle half of projects" },
  ];
</script>

<section class="tt">
  <h2>Retired share and time to first issuance, by credit type</h2>
  <p class="muted sub">All regions. Retired share = credits retired ÷ credits issued (projects whose registry reports retirements). Years to first issuance are counted from the project's first registry milestone (listing, validation or crediting start, whichever is earliest); shown for types with at least 5 projects.</p>
  <div class="scroller">
    <table>
      <thead>
        <tr>
          {#each COLS as c}
            <th class:n={c.num} aria-sort={sortKey === c.k ? (sortDir > 0 ? "ascending" : "descending") : "none"}>
              <button onclick={() => sortBy(c.k)}>{c.label}{sortKey === c.k ? (sortDir > 0 ? " ↑" : " ↓") : ""}{#if c.unit}<small>{c.unit}</small>{/if}</button>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each shown as r (r.l2)}
          <tr>
            <td><i class="dot" style:background={L1_COLORS[r.l1]}></i>{l2[r.l2]?.label || r.l2} <span class="muted l1">{l1Label[r.l1]}</span></td>
            <td class="n num">{r.n.toLocaleString()}</td>
            <td class="n num">{fmt(r.is)}</td>
            <td class="n num">{fmt(r.re)}</td>
            <td class="share">
              {#if r.share != null}
                <span class="sbar"><span style:width="{Math.min(1, r.share) * 100}%"></span></span><span class="num">{Math.round(r.share * 100)}%</span>
              {:else}<span class="muted">—</span>{/if}
            </td>
            <td class="time">
              {#if r.tt}
                <span class="tbar" title="Middle half of projects: {r.tt[1]}–{r.tt[2]} years · {r.tt[3]} projects">
                  <span class="iqr" style:left={pos(r.tt[1])} style:width="calc({pos(r.tt[2])} - {pos(r.tt[1])} + 3px)"></span>
                  <span class="med" style:left={pos(r.tt[0])}></span>
                </span>
                <span class="num">{r.tt[0]} yr</span> <span class="muted small">({r.tt[1]}–{r.tt[2]}, n={r.tt[3]})</span>
              {:else}<span class="muted">too few projects</span>{/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if rows.length > 15}
    <p class="more"><button class="link" onclick={() => (all = !all)}>{all ? "Show top 15" : `Show all ${rows.length} credit types`}</button></p>
  {/if}
</section>

<style>
  .tt { margin-top: 22px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 12px 14px 10px; }
  h2 { font-size: 18px; margin: 0; }
  .sub { margin: 3px 0 8px; font-size: 12.5px; max-width: 860px; }
  .scroller { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 820px; font-size: 13px; }
  th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  th { font-weight: 600; color: var(--muted); white-space: nowrap; }
  th button { background: none; border: 0; padding: 0; font: inherit; color: inherit; cursor: pointer; text-align: inherit; }
  th small { display: block; font-weight: 400; color: var(--faint); font-size: 10.5px; }
  .n { text-align: right; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
  .l1 { font-size: 11.5px; margin-left: 4px; }
  .share { white-space: nowrap; min-width: 170px; }
  .sbar { display: inline-block; width: 110px; height: 8px; background: var(--chip); border-radius: 4px; overflow: hidden; vertical-align: middle; margin-right: 8px; }
  .sbar span { display: block; height: 100%; background: var(--choro-hi); border-radius: 4px; }
  .time { white-space: nowrap; min-width: 280px; }
  .tbar { position: relative; display: inline-block; width: 130px; height: 10px; vertical-align: middle; margin-right: 8px;
    background: linear-gradient(to right, var(--line) 1px, transparent 1px) 0 0 / 10% 100%; border-bottom: 1px solid var(--line); }
  .iqr { position: absolute; top: 2px; height: 6px; background: var(--accent-soft); border-radius: 3px; }
  .med { position: absolute; top: 0; width: 3px; height: 10px; background: var(--accent); border-radius: 1px; }
  .small { font-size: 11.5px; }
  .more { margin: 6px 0 0; font-size: 12.5px; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font: inherit; }
</style>

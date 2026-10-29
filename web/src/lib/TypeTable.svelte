<script>
  // Per credit type: projects issuing, issued, retired, % of issued retired, and time to first issuance; by region.
  import Dropdown from "./Dropdown.svelte";
  import RegionSwitch from "./RegionSwitch.svelte";
  import { L1_COLORS, L1_TEXT, fmt } from "./data.js";

  let { types, l1, l2, areas } = $props();

  let region = $state("all");
  let sortKey = $state("is");
  let sortDir = $state(-1);
  let all = $state(false);
  let groups = $state(null);   // Set of l1 indices, or null = all
  const l1Label = $derived(Object.fromEntries(l1.map((x) => [x.id, x.label])));
  const groupOpts = $derived([{ items: l1.map((x, i) => ({ i, label: x.label })) }]);
  const SMALL = 5;   // fewer projects than this: the time figure is marked as a small sample

  const key = (r) => ({ cat: `${l1Label[r.l1]} ${l2[r.l2]?.label || r.l2}`, type: l2[r.l2]?.label || r.l2, n: r.n, is: r.is, re: r.re, share: r.share ?? -1, tt: r.tt ? r.tt[0] : 99 })[sortKey];
  const rows = $derived((types[region] || []).filter((r) => !groups || groups.has(l1.findIndex((x) => x.id === r.l1))).sort((a, b) => {
    const x = key(a), y = key(b);
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * sortDir;
  }));
  const shown = $derived(all ? rows : rows.slice(0, 15));
  const TMAX = 10;   // years shown on the timing bar; longer spans are clipped
  const pos = (y) => `${(Math.min(y, TMAX) / TMAX) * 100}%`;
  function sortBy(k) {
    if (sortKey === k) sortDir = -sortDir;
    else { sortKey = k; sortDir = k === "type" || k === "cat" || k === "tt" ? 1 : -1; }
  }
  const COLS = [
    { k: "cat", label: "Credit Category" }, { k: "type", label: "Credit Type" }, { k: "n", label: "# of Projects Issuing", num: true },
    { k: "is", label: "Volume Issued (tCO₂e)", num: true }, { k: "re", label: "Volume Retired (tCO₂e)", num: true },
    { k: "share", label: "% of Issued Credits Retired" }, { k: "tt", label: "Time to First Issuance*" },
  ];
</script>

<section class="tt">
  <div class="head">
    <h2>Which credit types are fastest to market, in time to issuance and share of retirement?</h2>
    <div class="ctl">
      <RegionSwitch {areas} bind:value={region} />
      <Dropdown label="Credit type" groups={groupOpts} total={l1.length} bind:selected={groups} align="right" />
    </div>
  </div>
  <div class="scroller">
    <table>
      <thead>
        <tr>
          {#each COLS as c}
            <th class:n={c.num} aria-sort={sortKey === c.k ? (sortDir > 0 ? "ascending" : "descending") : "none"}>
              <button onclick={() => sortBy(c.k)}>{c.label}{sortKey === c.k ? (sortDir > 0 ? " ↑" : " ↓") : ""}</button>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each shown as r (r.l2)}
          <tr>
            <td class="cat"><span class="tag" style:background={L1_COLORS[r.l1]} style:color={L1_TEXT[r.l1]}>{l1Label[r.l1]}</span></td>
            <td class="name">{l2[r.l2]?.label || r.l2}</td>
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
                <span class="num">{r.tt[0] < 1 ? "<1" : r.tt[0]} yr{#if r.tt[3] < SMALL}<span class="small-n" title="Fewer than {SMALL} projects">**</span>{/if}</span>
                <span class="muted small">({r.tt[1]}–{r.tt[2]}, n={r.tt[3]})</span>
              {:else}<span class="muted">—</span>{/if}
            </td>
          </tr>
        {/each}
        {#if !shown.length}<tr><td colspan={COLS.length} class="muted empty">No issuing projects for this selection.</td></tr>{/if}
      </tbody>
    </table>
  </div>
  {#if rows.length > 15}
    <p class="more"><button class="link" onclick={() => (all = !all)}>{all ? "Show top 15" : `Show all ${rows.length} credit types`}</button></p>
  {/if}
  <p class="foot muted">* Median years from a project's start (the earliest of listing, validation, crediting start or first vintage) to its first credits issued; the bar shows the middle half of projects. "&lt;1 yr" = same year. ** Fewer than {SMALL} projects.</p>
</section>

<style>
  .tt { margin-top: 36px; border: 0; border-top: 1px solid var(--black); border-radius: 0; background: none; padding: 14px 0 10px; }
  .head { display: grid; gap: 10px; margin-bottom: 10px; }
  .ctl { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
  h2 { font: 700 22px/1.25 var(--serif); margin: 0; }
  .scroller { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 760px; font-size: 13px; }
  th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  th { font-weight: 700; color: var(--black); vertical-align: bottom; border-bottom: 1px solid var(--rule); }
  th button { background: none; border: 0; padding: 0; font: inherit; color: inherit; cursor: pointer; text-align: inherit; }
  .n { text-align: right; }
  .name { min-width: 190px; }
  .cat { white-space: nowrap; }
  .tag { display: inline-block; white-space: nowrap; font-size: 11px; font-weight: 700; padding: 2px 8px; }
  .share { white-space: nowrap; }
  .sbar { display: inline-block; width: 70px; height: 8px; background: var(--gray-pale); overflow: hidden; vertical-align: middle; margin-right: 8px; }
  .sbar span { display: block; height: 100%; background: var(--deep-blue); }
  .time { white-space: nowrap; }
  .tbar { position: relative; display: inline-block; width: 90px; height: 10px; vertical-align: middle; margin-right: 8px;
    background: linear-gradient(to right, var(--line) 1px, transparent 1px) 0 0 / 10% 100%; border-bottom: 1px solid var(--line); }
  .iqr { position: absolute; top: 2px; height: 6px; background: var(--gray-super-light); }
  .med { position: absolute; top: 0; width: 3px; height: 10px; background: var(--deep-blue); }
  .small-n { color: var(--warn); margin-left: 1px; }
  .small { font-size: 11.5px; }
  .empty { text-align: center; padding: 14px; }
  .more { margin: 6px 0 0; font-size: 12.5px; }
  .foot { margin: 8px 0 0; font-size: 11.5px; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font: inherit; }
</style>

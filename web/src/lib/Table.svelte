<script>
  import { L1_COLORS, STAGE_LABELS, fmt, fmtFull } from "./data.js";

  let { rows, index, loading, fnum = () => null } = $props();

  let sortKey = $state("is");
  let sortDir = $state(-1);
  let open = $state(null);
  let limit = $state(200);

  const cols = [
    { k: "name", label: "Project" }, { k: "dev", label: "Developer" }, { k: "off", label: "Announced offtaker(s)", fn: "offtakers" },
    { k: "country", label: "Country", fn: "countries" },
    { k: "type", label: "Credit type" }, { k: "reg", label: "Registry", fn: "registries" }, { k: "st", label: "Stage", fn: "stages" },
    { k: "y_listed", label: "Listed", unit: "year", yr: true, fn: "years" }, { k: "y_registered", label: "Validated", unit: "year", yr: true, fn: "years" },
    { k: "y_first_issuance", label: "1st issued", unit: "year", yr: true, fn: "years" },
    { k: "ea", label: "Est. annual", num: true, unit: "tCO₂e/yr", fn: "estimate" }, { k: "is", label: "Issued", num: true, unit: "tCO₂e", fn: "units" },
    { k: "re", label: "Retired", num: true, unit: "tCO₂e", fn: "units" },
    { k: "pi", label: "% issued", num: true, unit: "of estimate to date", fn: "delivery" }, { k: "pr", label: "% retired", num: true, unit: "of issued", fn: "delivery" },
    { k: "tag", label: "Tag", fn: "tags" },
  ];

  const sorted = $derived.by(() => {
    const key = (r) => ({ name: r.display_name, dev: r.developer || "", country: (r.country_names || r.countries).join(","), type: r.typeLabel, tag: r.tagLabels.join(", ") || "~",
      reg: r.registries.map((x) => x.registry).join(","), st: r.st, y_listed: yr(r, "listed"), y_registered: yr(r, "registered"), y_first_issuance: yr(r, "first_issuance"), ea: vol(r.ea), is: vol(r.is), re: vol(r.re), pi: vol(r.pi), pr: vol(r.pr), off: r.offtakers.length })[sortKey];
    return [...rows].sort((a, b) => {
      const x = key(a), y = key(b);
      return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * sortDir;
    });
  });

  // Missing values (not published by the source) sort last in both directions.
  const vol = (v) => v ?? (sortDir > 0 ? Infinity : -Infinity);
  const yr = (r, k) => r.years?.[k] ?? (sortDir > 0 ? 9999 : 0);

  // Collapsed rows show only the first few items of long lists; clicking the row (outside links) expands it.
  const LIM = { off: 2, reg: 1, tag: 2, cty: 3 };
  const toggle = (id) => (open = open === id ? null : id);
  const LOW = 0.5;   // "% issued" below this is shown in pink (issuing well below the registry estimate)
  const pct = (v) => (v == null ? "—" : v > 3 ? ">300%" : Math.round(v * 100) + "%");
  function rowClick(e, id) {
    if (e.target.closest("a, button") || window.getSelection()?.toString()) return;
    toggle(id);
  }
  const offTip = (o) => [o.type, o.country, o.date, o.volume_tco2e ? fmt(o.volume_tco2e) + " tCO₂e" : "", o.note].filter(Boolean).join(" · ");

  function sortBy(k) {
    if (sortKey === k) sortDir = -sortDir;
    else { sortKey = k; sortDir = ["name", "dev", "country", "type", "tag", "reg"].includes(k) ? 1 : -1; }
  }
</script>

<div class="scroller">
  <table>
    <thead>
      <tr>
        {#each cols as c}
          <th class:num={c.num || c.yr} aria-sort={sortKey === c.k ? (sortDir > 0 ? "ascending" : "descending") : "none"}>
            <button onclick={() => sortBy(c.k)}>{c.label}{sortKey === c.k ? (sortDir > 0 ? " ↑" : " ↓") : ""}{#if c.unit}<small>{c.unit}</small>{/if}</button>{#if c.fn && fnum(c.fn)}<sup class="fn"><a href="#note-{fnum(c.fn)}" aria-label="Note {fnum(c.fn)}">{fnum(c.fn)}</a></sup>{/if}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if loading}
        <tr><td colspan={cols.length} class="empty">Loading…</td></tr>
      {:else if !sorted.length}
        <tr><td colspan={cols.length} class="empty">No projects match these filters.</td></tr>
      {/if}
      {#each sorted.slice(0, limit) as r (r.project_id)}
        {@const ex = open === r.project_id}
        {@const cn = r.country_names || r.countries}
        <tr class="main" class:open={ex} onclick={(e) => rowClick(e, r.project_id)} title={ex ? "" : "Click to expand"}>
          <td class="name"><div class="nw">
            <button class="exp" aria-expanded={open === r.project_id} aria-label="Details" onclick={() => toggle(r.project_id)}>{open === r.project_id ? "−" : "+"}</button>
            <span class="clamp" class:full={ex}>{#if r.project_url}<a href={r.project_url} target="_blank" rel="noopener">{r.display_name}</a>{:else}{r.display_name}{/if}</span>
          </div></td>
          <td><span class="clamp" class:full={ex}>{#if r.developer_url}<a href={r.developer_url} target="_blank" rel="noopener">{r.developer || "—"}</a>{:else}{r.developer || "—"}{/if}</span></td>
          <td class="off">
            {#each ex ? r.offtakers : r.offtakers.slice(0, LIM.off) as o, i}{#if i}, {/if}<a href={o.source_url} target="_blank" rel="noopener" title={offTip(o)}>{o.name}</a>{/each}{#if !ex && r.offtakers.length > LIM.off} <span class="more-n">+{r.offtakers.length - LIM.off}</span>{/if}
            {#if !r.offtakers.length}<span class="muted">—</span>{/if}
          </td>
          <td>{(ex ? cn : cn.slice(0, LIM.cty)).join(", ")}{#if !ex && cn.length > LIM.cty} <span class="more-n">+{cn.length - LIM.cty}</span>{/if}{#if r.countries.length > 1} <span class="badge" title={"Map split by population (UN WPP 2024), hosts in this region only: " + Object.entries(r.country_shares || {}).map(([c, v]) => `${c} ${(v * 100).toFixed(v < 0.01 ? 2 : 0)}%`).join(", ")}>multi</span>{/if}</td>
          <td class="type"><span class="clamp" class:full={ex}><span class="sw" style="background:{L1_COLORS[r.l1]}"></span>{r.typeLabel}</span></td>
          <td class="regs">
            {#each ex ? r.registries : r.registries.slice(0, LIM.reg) as g}<a class="badge" href={g.url} target="_blank" rel="noopener" title={g.registry === "ANN" ? "Open the announcement" : "Open registry record"}>{g.registry === "ANN" ? "Announcement only, unregistered yet" : g.record_id}</a>{/each}{#if !ex && r.registries.length > LIM.reg}<span class="more-n">+{r.registries.length - LIM.reg}</span>{/if}
            {#if r.article6}<span class="badge a6" title={["Article 6", r.article6.status, r.article6.buyer_countries?.length ? "buyer: " + r.article6.buyer_countries.join(", ") : "", r.article6.itmos_transferred ? fmt(r.article6.itmos_transferred) + " ITMOs transferred" : ""].filter(Boolean).join(" · ")}>{r.article6.mechanism}{#if r.article6.buyer_countries?.length} → {r.article6.buyer_countries.join(", ")}{/if}</span>{/if}
          </td>
          <td>{STAGE_LABELS[index.stages[r.st]]}</td>
          <td class="num yr">{r.years?.listed ?? "—"}</td>
          <td class="num yr">{r.years?.registered ?? "—"}</td>
          <td class="num yr">{r.years?.first_issuance ?? "—"}</td>
          <td class="num">{fmt(r.ea)}</td>
          <td class="num">{fmt(r.is)}</td>
          <td class="num">{fmt(r.re)}</td>
          <td class="num pct" class:low={r.pi != null && r.pi < LOW} class:good={r.pi != null && r.pi >= 0.9}
            title={r.pi == null ? "Needs an estimate, a start year and issuance" : r.pi < LOW ? "Issuing well below the registry estimate (under half of the estimate to date)" : "Issued ÷ (estimated annual × crediting years to date)"}>{pct(r.pi)}</td>
          <td class="num pct"><span class="rbar" aria-hidden="true"><span style:width="{Math.min(1, r.pr || 0) * 100}%"></span></span>{pct(r.pr)}</td>
          <td class="tags">{#each ex ? r.tagLabels : r.tagLabels.slice(0, LIM.tag) as t}<span class="tag">{t}</span>{/each}{#if !ex && r.tagLabels.length > LIM.tag}<span class="more-n">+{r.tagLabels.length - LIM.tag}</span>{/if}{#if !r.tagLabels.length}<span class="muted">—</span>{/if}</td>

        </tr>
        {#if open === r.project_id}
          <tr class="detail">
            <td colspan={cols.length}>
              <dl>
                <dt>Registry records</dt>
                <dd>{#each r.registries as g}<div><a href={g.url} target="_blank" rel="noopener">{g.record_id}</a></div>{/each}</dd>
                <dt>Volumes</dt>
                <dd class="num">est. {fmtFull(r.ea)} tCO₂e/yr · issued {fmtFull(r.is)} · retired {fmtFull(r.re)} tCO₂e</dd>
                {#if Object.keys(r.issuance_by_vintage || {}).length}
                  <dt>Issued by vintage</dt>
                  <dd class="vint">
                    {#each Object.entries(r.issuance_by_vintage) as [y, v]}<span class="num">{y}: {fmt(v)}</span>{/each}
                  </dd>
                {/if}
                {#if r.offtakers.length}
                  <dt>Offtakers</dt>
                  <dd>{#each r.offtakers as o}<div><a href={o.source_url} target="_blank" rel="noopener">{o.name}</a> <span class="muted">— {offTip(o)}</span></div>{/each}</dd>
                {/if}
                {#if r.rb?.length}
                  <dt>Retired by</dt>
                  <dd>{#each r.rb as [b, t]}<span class="rbn">{b || "unnamed"} <span class="num muted">{fmt(t)}</span></span>{/each}
                    <span class="muted small">(registry retirement records via CarbonPlan OffsetsDB)</span></dd>
                {/if}
                {#if r.methodology_codes?.length}<dt>Methodology</dt><dd class="num">{r.methodology_codes.join(", ")}</dd>{/if}
                {#if r.crediting?.[0]}<dt>Crediting period</dt><dd class="num">{r.crediting[0]} → {r.crediting[1] || "?"}</dd>{/if}
                {#if r.flags?.length}<dt>Flags</dt><dd>{r.flags.join(", ")}</dd>{/if}
              </dl>
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
</div>
{#if sorted.length > limit}
  <p class="more"><button onclick={() => (limit += 500)}>Show more ({sorted.length - limit} remaining)</button></p>
{/if}

<style>
  .scroller { overflow-x: auto; border: 0; border-top: 1px solid var(--black); background: var(--white); }
  table { border-collapse: collapse; width: 100%; min-width: 1560px; font-size: 13.5px; }
  th { text-align: left; font-weight: 700; border-bottom: 1px solid var(--rule); vertical-align: bottom; position: sticky; top: 0; background: var(--surface); }
  th { white-space: nowrap; }
  th sup { margin-left: -6px; }
  th button { background: none; border: 0; padding: 9px 8px 9px 10px; font-weight: 700; cursor: pointer; text-align: inherit; }
  th small { display: block; font-weight: 400; color: var(--faint); font-size: 11px; }
  th.num, td.num { text-align: right; }
  th.num { font-family: var(--font); font-size: inherit; }
  td { padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tr.main { cursor: pointer; }
  tr.main:hover td { background: var(--gray-pale); }
  tr.main.open td { background: var(--gray-pale); }
  .clamp { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .clamp.full { display: inline; -webkit-line-clamp: unset; line-clamp: unset; }
  .more-n { font-size: 11.5px; color: var(--muted); white-space: nowrap; margin-left: 2px; }
  .regs { white-space: nowrap; }
  tr.open .regs { white-space: normal; }
  .name { min-width: 240px; }
  .nw { display: flex; gap: 6px; align-items: flex-start; }
  .nw .exp { flex: none; margin-right: 0; }
  .exp { width: 20px; height: 20px; border: 1px solid var(--black); background: var(--white); border-radius: 0; margin-right: 6px; cursor: pointer; line-height: 1; }
  .badge { display: inline-block; font: 11px var(--font); padding: 1px 6px; background: var(--gray-pale); color: var(--ink); margin: 0 4px 3px 0; }
  .badge.a6 { background: #AFC3FF; }
  .sw { width: 10px; height: 10px; display: inline-block; margin-right: 6px; }
  .detail td { background: #F7F7F7; }
  dl { display: grid; grid-template-columns: 160px 1fr; gap: 4px 14px; margin: 4px 0 4px 26px; }
  dt { color: var(--muted); }
  dd { margin: 0; }
  .vint { display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .type { min-width: 170px; }
  .tags { min-width: 120px; max-width: 220px; }
  .tag { display: inline-block; font-size: 11.5px; padding: 1px 7px; border: 1px solid var(--gray-light); color: var(--gray-dark); margin: 0 4px 3px 0; white-space: nowrap; }
  .yr { color: var(--muted); }
  .pct { white-space: nowrap; }
  .small { font-size: 11.5px; }
  .rbn { display: inline-block; margin-right: 14px; }
  .pct.low { color: var(--pink); font-weight: 700; }
  .pct.good { color: var(--good); }
  .rbar { display: inline-block; width: 34px; height: 6px; background: var(--gray-pale); overflow: hidden; margin-right: 6px; vertical-align: 1px; }
  .rbar span { display: block; height: 100%; background: var(--deep-blue); }
  .off { min-width: 130px; }
  .empty { text-align: center; color: var(--muted); padding: 28px; }
  .more { text-align: center; }
  .more button { border: 1px solid var(--black); background: var(--white); border-radius: 0; padding: 4px 14px; cursor: pointer; }
</style>

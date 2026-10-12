<script>
  import { L1_COLORS, STAGE_LABELS, fmt, fmtFull } from "./data.js";

  let { rows, index, loading } = $props();

  let sortKey = $state("is");
  let sortDir = $state(-1);
  let open = $state(null);
  let limit = $state(200);

  const cols = [
    { k: "name", label: "Project" }, { k: "dev", label: "Developer" }, { k: "country", label: "Country", fn: 2 },
    { k: "type", label: "Credit type" }, { k: "reg", label: "Registry", fn: 3 }, { k: "st", label: "Stage", fn: 4 },
    { k: "y_listed", label: "Listed", unit: "year", yr: true, fn: 4 }, { k: "y_registered", label: "Validated", unit: "year", yr: true, fn: 4 },
    { k: "y_first_issuance", label: "1st issued", unit: "year", yr: true, fn: 4 },
    { k: "ea", label: "Est. annual", num: true, unit: "tCO₂e/yr", fn: 5 }, { k: "is", label: "Issued", num: true, unit: "tCO₂e", fn: 6 },
    { k: "re", label: "Retired", num: true, unit: "tCO₂e", fn: 6 }, { k: "off", label: "Announced offtaker(s)", fn: 7 },
  ];

  const sorted = $derived.by(() => {
    const key = (r) => ({ name: r.display_name, dev: r.developer || "", country: r.countries.join(","), type: r.typeLabel,
      reg: r.registries.map((x) => x.registry).join(","), st: r.st, y_listed: yr(r, "listed"), y_registered: yr(r, "registered"), y_first_issuance: yr(r, "first_issuance"), ea: r.ea, is: r.is, re: r.re, off: r.offtakers.length })[sortKey];
    return [...rows].sort((a, b) => {
      const x = key(a), y = key(b);
      return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * sortDir;
    });
  });

  // Missing years sort last in both directions.
  const yr = (r, k) => r.years?.[k] ?? (sortDir > 0 ? 9999 : 0);

  function sortBy(k) {
    if (sortKey === k) sortDir = -sortDir;
    else { sortKey = k; sortDir = ["name", "dev", "country", "type", "reg"].includes(k) ? 1 : -1; }
  }
</script>

<div class="scroller">
  <table>
    <thead>
      <tr>
        {#each cols as c}
          <th class:num={c.num || c.yr} aria-sort={sortKey === c.k ? (sortDir > 0 ? "ascending" : "descending") : "none"}>
            <button onclick={() => sortBy(c.k)}>{c.label}{sortKey === c.k ? (sortDir > 0 ? " ↑" : " ↓") : ""}{#if c.unit}<small>{c.unit}</small>{/if}</button>{#if c.fn}<sup class="fn"><a href="#note-{c.fn}" aria-label="Note {c.fn}">{c.fn}</a></sup>{/if}
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
        <tr class="main" class:open={open === r.project_id}>
          <td class="name">
            <button class="exp" aria-expanded={open === r.project_id} aria-label="Details" onclick={() => (open = open === r.project_id ? null : r.project_id)}>{open === r.project_id ? "−" : "+"}</button>
            {#if r.project_url}<a href={r.project_url} target="_blank" rel="noopener">{r.display_name}</a>{:else}{r.display_name}{/if}
          </td>
          <td>{#if r.developer_url}<a href={r.developer_url} target="_blank" rel="noopener">{r.developer || "—"}</a>{:else}{r.developer || "—"}{/if}</td>
          <td>{r.countries.join(", ")}{#if r.countries.length > 1} <span class="badge">multi</span>{/if}</td>
          <td><span class="sw" style="background:{L1_COLORS[r.l1]}"></span>{r.typeLabel}</td>
          <td class="regs">
            {#each r.registries as g}<a class="badge" href={g.url} target="_blank" rel="noopener" title="Open registry record">{g.record_id}</a>{/each}
            {#if r.article6}<span class="badge a6" title={["Article 6", r.article6.status, r.article6.buyer_countries?.length ? "buyer: " + r.article6.buyer_countries.join(", ") : "", r.article6.itmos_transferred ? fmt(r.article6.itmos_transferred) + " ITMOs transferred" : ""].filter(Boolean).join(" · ")}>{r.article6.mechanism}{#if r.article6.buyer_countries?.length} → {r.article6.buyer_countries.join(", ")}{/if}</span>{/if}
          </td>
          <td>{STAGE_LABELS[index.stages[r.st]]}</td>
          <td class="num yr">{r.years?.listed ?? "—"}</td>
          <td class="num yr">{r.years?.registered ?? "—"}</td>
          <td class="num yr">{r.years?.first_issuance ?? "—"}</td>
          <td class="num">{fmt(r.ea)}</td>
          <td class="num">{fmt(r.is)}</td>
          <td class="num">{fmt(r.re)}</td>
          <td>
            {#each r.offtakers as o, i}{#if i}, {/if}<a href={o.source_url} target="_blank" rel="noopener" title={o.type}>{o.name}</a>{/each}
            {#if !r.offtakers.length}<span class="muted">—</span>{/if}
          </td>
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
  .scroller { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
  table { border-collapse: collapse; width: 100%; min-width: 1250px; font-size: 13.5px; }
  th { text-align: left; font-weight: 600; border-bottom: 1px solid var(--line); position: sticky; top: 0; background: var(--surface); }
  th { white-space: nowrap; }
  th sup { margin-left: -6px; }
  th button { background: none; border: 0; padding: 9px 8px 9px 10px; font-weight: 600; cursor: pointer; text-align: inherit; }
  th small { display: block; font-weight: 400; color: var(--faint); font-size: 11px; }
  th.num, td.num { text-align: right; }
  th.num { font-family: var(--font); font-size: inherit; }
  td { padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tr.main:hover td { background: var(--chip); }
  .name { min-width: 240px; }
  .exp { width: 20px; height: 20px; border: 1px solid var(--line); background: var(--surface); border-radius: 4px; margin-right: 6px; cursor: pointer; line-height: 1; }
  .badge { display: inline-block; font: 11px var(--mono); padding: 1px 6px; border-radius: 4px; background: var(--chip); color: var(--ink); margin: 0 4px 3px 0; }
  .badge.a6 { background: var(--accent-soft); }
  .sw { width: 8px; height: 8px; border-radius: 2px; display: inline-block; margin-right: 6px; }
  .detail td { background: var(--bg); }
  dl { display: grid; grid-template-columns: 160px 1fr; gap: 4px 14px; margin: 4px 0 4px 26px; }
  dt { color: var(--muted); }
  dd { margin: 0; }
  .vint { display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .yr { color: var(--muted); }
  .empty { text-align: center; color: var(--muted); padding: 28px; }
  .more { text-align: center; }
  .more button { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 4px 14px; cursor: pointer; }
</style>

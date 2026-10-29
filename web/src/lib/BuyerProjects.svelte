<script>
  // One buyer's projects: announced deal volume, the project's issued total, and what the buyer retired there.
  import { L1_COLORS, fmt, fmtFull, urlFor } from "./data.js";

  let { meta, buyer, l2, lens = "re", limit = 0, onprofile = null } = $props();

  const val = (e) => (lens === "all" ? Math.max(e.re, e.an || 0) : lens === "re" ? e.re : lens === "is" ? (e.iss ? e.an || 0 : 0) : (!e.iss ? e.an || 0 : 0));
  const rows = $derived([...buyer.p].sort((a, b) => val(b) - val(a) || b.re - a.re || (b.an || 0) - (a.an || 0)));
  const shown = $derived(limit ? rows.slice(0, limit) : rows);
  const country = (e) => e.c.map((c) => meta.names?.[c] || c).join(", ");
  const href = (e) => (e.rg.startsWith("ANN:") ? e.dl[0]?.[2] : urlFor(meta, e.rg)) || e.dl[0]?.[2];
  const yr = (d) => (d ? d.slice(0, 4) : "");
</script>

<div class="bp">
  <table>
    <thead>
      <tr>
        <th>Project</th><th>Country</th><th>Credit type</th>
        <th class="n">Announced<small>tCO₂e, deal total</small></th>
        <th class="n">Issued<small>project total</small></th>
        <th class="n">Retired<small>by this buyer</small></th>
      </tr>
    </thead>
    <tbody>
      {#each shown as e (e.id)}
        <tr class:hl={val(e) > 0}>
          <td><a href={href(e)} target="_blank" rel="noopener" title={e.rg.startsWith("ANN:") ? "Open the announcement" : "Open the registry record"}>{e.nm}</a>
            {#if e.rg.startsWith("ANN:")}<span class="ann">announcement only</span>{:else if !e.iss}<span class="ann">not issuing yet</span>{/if}</td>
          <td>{country(e)}</td>
          <td><i class="dot" style:background={L1_COLORS[e.l1]}></i>{l2[e.l2]?.label || e.l2}</td>
          <td class="n num">
            {#if e.dl.length}
              {#each e.dl as [v, d, u, sh], i}<div><a href={u} target="_blank" rel="noopener" title="Open the announcement">{v ? fmtFull(v) : "not stated"}</a> <span class="muted">{yr(d)}</span>{#if sh}<div class="shr">{sh}</div>{/if}</div>{/each}
            {:else}<span class="muted">—</span>{/if}
          </td>
          <td class="n num">{e.rg.startsWith("ANN:") ? "—" : fmtFull(e.pis)}</td>
          <td class="n num">{#if e.re}{fmtFull(e.re)}{#if e.rd}<div class="shr">{yr(e.rd[0])}{yr(e.rd[1]) !== yr(e.rd[0]) ? "–" + yr(e.rd[1]) : ""}</div>{/if}{:else}<span class="muted">—</span>{/if}</td>
        </tr>
      {/each}
    </tbody>
  </table>
  {#if (limit && rows.length > limit) || buyer.np > buyer.p.length || onprofile}
    <p class="more">
      {#if limit && rows.length > limit}<span class="muted">{rows.length - limit} more projects.</span>{/if}
      {#if onprofile}<button class="link" onclick={() => onprofile(buyer.n)}>Open buyer profile →</button>{/if}
    </p>
  {/if}
</div>

<style>
  .bp { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 720px; font-size: 12.5px; }
  th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { font-weight: 700; color: var(--black); white-space: nowrap; vertical-align: bottom; border-bottom: 1px solid var(--rule); }
  th small { display: block; font-weight: 400; color: var(--faint); font-size: 10.5px; }
  .n { text-align: right; }
  tr:not(.hl) td { color: var(--muted); }
  .dot { display: inline-block; width: 10px; height: 10px; margin-right: 5px; vertical-align: -1px; }
  .ann { font-size: 10.5px; color: var(--faint); margin-left: 6px; white-space: nowrap; }
  .shr { font: 11px var(--font); color: var(--muted); }
  .more { margin: 6px 0 0; font-size: 12.5px; display: flex; gap: 14px; align-items: center; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font: inherit; }
</style>

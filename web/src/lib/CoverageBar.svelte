<script>
  // Small bar above a region's map: share of the region's issued credits that sit in registries the atlas covers.
  import { fmt } from "./data.js";

  let { cov } = $props();
  let open = $state(false);
  const missing = $derived(cov.programmes.filter((x) => x.issued == null));
  const counted = $derived(cov.programmes.filter((x) => x.issued != null));
</script>

<div class="cov">
  <button class="head" aria-expanded={open} onclick={() => (open = !open)}
    title="Credits issued in covered registries ÷ (that + credits issued in this region's programmes not covered yet)">
    <span class="lbl">Coverage</span>
    {#if cov.pct != null}
      <span class="track"><span class="fill" style:width="{cov.pct * 100}%"></span></span>
      <strong class="num">{(cov.pct * 100).toFixed(cov.pct > 0.995 && cov.pct < 1 ? 1 : 0)}%</strong>
    {:else}
      <span class="track pending"></span><strong class="pend">being measured</strong>
    {/if}
    <span class="muted small">{missing.length ? `${missing.length} programme${missing.length > 1 ? "s" : ""} without a published total` : "of credits issued in this region"} {open ? "▴" : "▾"}</span>
  </button>
  {#if open}
    <div class="panel">
      <p class="muted small">Covered registries: <span class="num">{fmt(cov.covered)}</span> tCO₂e issued. Programmes in this region the atlas does not cover yet:</p>
      <ul>
        {#each counted as x}<li><a href={x.url} target="_blank" rel="noopener">{x.name}</a> <span class="num">{fmt(x.issued)}</span>{#if x.as_of}<span class="muted"> · {x.as_of}</span>{/if}</li>{/each}
        {#each missing as x}<li><a href={x.url} target="_blank" rel="noopener">{x.name}</a> <span class="muted">total not yet sourced{x.major ? " (large)" : ""}</span></li>{/each}
        {#if !cov.programmes.length}<li class="muted">None known.</li>{/if}
      </ul>
    </div>
  {/if}
</div>

<style>
  .cov { position: relative; font-size: 13px; }
  .head { display: flex; align-items: center; gap: 8px; background: none; border: 0; padding: 0; color: inherit; font: inherit; cursor: pointer; }
  .lbl { color: var(--muted); }
  .track { display: inline-block; width: 120px; height: 8px; background: var(--chip); border-radius: 4px; overflow: hidden; }
  .track.pending { background: repeating-linear-gradient(45deg, var(--chip) 0 4px, var(--line) 4px 8px); }
  .fill { display: block; height: 100%; background: var(--choro-hi); border-radius: 4px; }
  .pend { font-weight: 600; color: var(--muted); }
  .small { font-size: 12px; }
  .panel { position: absolute; z-index: 6; top: calc(100% + 6px); left: 0; width: min(440px, calc(100vw - 32px)); background: var(--surface);
    border: 1px solid var(--line); border-radius: var(--radius); padding: 8px 12px; box-shadow: 0 6px 24px rgba(0,0,0,.3); }
  .panel p { margin: 0 0 6px; }
  ul { margin: 0; padding-left: 16px; display: grid; gap: 3px; }
</style>

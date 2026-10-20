<script>
  // Compact region switch (All Regions + each region) used by the All Regions tables.
  let { areas, value = $bindable("all") } = $props();
  const opts = $derived([{ id: "all", label: "All Regions" }, ...areas.map((a) => ({ id: a.id, label: a.label }))]);
</script>

<div class="rs" role="tablist" aria-label="Region" style:--n={opts.length} style:--i={Math.max(0, opts.findIndex((o) => o.id === value))}>
  <span class="thumb" aria-hidden="true"></span>
  {#each opts as o}
    <button role="tab" aria-selected={value === o.id} onclick={() => (value = o.id)}>{o.label}</button>
  {/each}
</div>

<style>
  .rs { position: relative; display: grid; grid-template-columns: repeat(var(--n), 1fr); max-width: 760px; background: var(--chip);
    border: 1px solid var(--line); border-radius: 999px; padding: 3px; }
  button { position: relative; z-index: 1; border: 0; background: none; padding: 4px 8px; border-radius: 999px; cursor: pointer;
    font-size: 12.5px; font-weight: 600; color: var(--muted); transition: color 0.2s; white-space: nowrap; }
  button[aria-selected="true"] { color: #0d2023; }
  .thumb { position: absolute; top: 3px; bottom: 3px; left: 3px; width: calc((100% - 6px) / var(--n)); border-radius: 999px;
    background: var(--choro-hi); transform: translateX(calc(100% * var(--i))); transition: transform 0.25s ease; }
  @media (prefers-reduced-motion: reduce) { .thumb, button { transition: none; } }
  @media (max-width: 640px) { .rs { border-radius: 14px; } button { font-size: 11px; padding: 4px 2px; white-space: normal; line-height: 1.15; } }
</style>

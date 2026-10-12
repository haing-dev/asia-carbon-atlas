<script>
  import { L1_COLORS, STAGE_LABELS } from "./data.js";

  let { index, f = $bindable(), onclear } = $props();

  let typesOpen = $state(false);
  let expanded = $state({});

  const groups = $derived(index.l1.map((g) => ({
    ...g,
    items: index.l2.map((x, i) => ({ ...x, i })).filter((x) => x.l1 === g.id),
  })));

  const allL2 = () => new Set(index.l2.map((_, i) => i));
  function toggleL2(i) {
    const s = f.l2 ? new Set(f.l2) : allL2();
    s.has(i) ? s.delete(i) : s.add(i);
    f.l2 = s.size === index.l2.length ? null : s;
  }
  function toggleGroup(items) {
    const s = f.l2 ? new Set(f.l2) : allL2();
    const allOn = items.every((x) => s.has(x.i));
    for (const x of items) allOn ? s.delete(x.i) : s.add(x.i);
    f.l2 = s.size === index.l2.length ? null : s;
  }
  const groupState = (items) => {
    if (!f.l2) return "all";
    const n = items.filter((x) => f.l2.has(x.i)).length;
    return n === 0 ? "none" : n === items.length ? "all" : "some";
  };
  function toggleStage(i) {
    const s = new Set(f.stages);
    s.has(i) ? s.delete(i) : s.add(i);
    f.stages = s;
  }
  function toggleRegistry(i) {
    const s = f.registries ? new Set(f.registries) : new Set(index.registries.map((_, j) => j));
    s.has(i) ? s.delete(i) : s.add(i);
    f.registries = s.size === index.registries.length ? null : s;
  }
  const typeSummary = $derived(f.l2 ? `${f.l2.size} of ${index.l2.length} types` : "All types");
</script>

<div class="filters">
  <div class="row">
    <div class="types">
      <button class="pill" class:on={!!f.l2} aria-expanded={typesOpen} onclick={() => (typesOpen = !typesOpen)}>
        Credit type: {typeSummary} <span aria-hidden="true">{typesOpen ? "▴" : "▾"}</span>
      </button>
      {#if typesOpen}
        <div class="panel" role="group" aria-label="Credit types">
          <div class="panel-actions">
            <button class="link" onclick={() => (f.l2 = null)}>Select all</button>
            <button class="link" onclick={() => (f.l2 = new Set())}>Clear</button>
          </div>
          {#each groups as g}
            {@const st = groupState(g.items)}
            <div class="group">
              <label class="l1">
                <input type="checkbox" checked={st === "all"} indeterminate={st === "some"} onchange={() => toggleGroup(g.items)} />
                <span class="sw" style="background:{L1_COLORS[g.id]}"></span>{g.label}
              </label>
              <button class="link small" aria-expanded={!!expanded[g.id]} onclick={() => (expanded[g.id] = !expanded[g.id])}>
                {expanded[g.id] ? "hide" : g.items.length + " types"}
              </button>
              {#if expanded[g.id]}
                <div class="l2s">
                  {#each g.items as x}
                    <label><input type="checkbox" checked={!f.l2 || f.l2.has(x.i)} onchange={() => toggleL2(x.i)} />{x.label}</label>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <div class="pills" role="group" aria-label="Project stage">
      {#each index.stages as s, i}
        <button class="pill" class:on={f.stages.has(i)} aria-pressed={f.stages.has(i)} onclick={() => toggleStage(i)}>{STAGE_LABELS[s]}</button>
      {/each}
    </div>
  </div>

  <div class="row">
    <div class="pills" role="group" aria-label="Registry">
      {#each index.registries as r, i}
        <button class="pill" class:on={!f.registries || f.registries.has(i)} aria-pressed={!f.registries || f.registries.has(i)} onclick={() => toggleRegistry(i)}>{r.label}</button>
      {/each}
    </div>
  </div>

  <div class="row">
    <label class="toggle"><input type="checkbox" bind:checked={f.a6} /> Article 6 only</label>
    <input class="search" type="search" placeholder="Search project or developer" bind:value={f.q} aria-label="Search" />
    <button class="link" onclick={onclear}>Clear filters</button>
  </div>
</div>

<style>
  .filters { display: grid; gap: 8px; margin: 14px 0; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .pills { display: flex; flex-wrap: wrap; gap: 6px; }
  .pill { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 3px 11px; font-size: 13px; cursor: pointer; color: var(--muted); }
  .pill.on { border-color: var(--accent); color: var(--ink); background: var(--accent-soft); }
  .types { position: relative; }
  .panel { position: absolute; z-index: 5; top: calc(100% + 6px); left: 0; width: min(420px, calc(100vw - 32px)); max-height: 60vh; overflow: auto;
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 10px 12px; box-shadow: 0 6px 24px rgba(0,0,0,.12); }
  .panel-actions { display: flex; gap: 12px; margin-bottom: 6px; }
  .group { display: grid; grid-template-columns: 1fr auto; align-items: center; padding: 3px 0; border-top: 1px solid var(--line); }
  .l1 { display: flex; align-items: center; gap: 6px; font-size: 14px; }
  .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .l2s { grid-column: 1 / -1; display: grid; gap: 2px; padding: 4px 0 6px 26px; font-size: 13px; }
  .l2s label { display: flex; gap: 6px; align-items: center; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font-size: 13px; }
  .small { font-size: 12px; color: var(--muted); }
  .toggle { font-size: 13px; display: flex; gap: 6px; align-items: center; }
  .search { flex: 1 1 220px; min-width: 0; border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; background: var(--surface); font-size: 14px; }
</style>

<script>
  // A pill button that opens a checklist panel. `groups`: [{label, color?, items:[{i, label}]}]
  // `selected`: Set of item indices, or null meaning "all".
  let { label, groups, total, selected = $bindable(), wide = false } = $props();

  let open = $state(false);
  let root;

  const allSet = () => new Set(groups.flatMap((g) => g.items.map((x) => x.i)));
  const isOn = (i) => !selected || selected.has(i);
  function commit(s) { selected = s.size === total ? null : s; }
  function toggle(i) {
    const s = selected ? new Set(selected) : allSet();
    s.has(i) ? s.delete(i) : s.add(i);
    commit(s);
  }
  function toggleGroup(g) {
    const s = selected ? new Set(selected) : allSet();
    const allOn = g.items.every((x) => s.has(x.i));
    for (const x of g.items) allOn ? s.delete(x.i) : s.add(x.i);
    commit(s);
  }
  const groupState = (g) => {
    const n = g.items.filter((x) => isOn(x.i)).length;
    return n === 0 ? "none" : n === g.items.length ? "all" : "some";
  };
  const summary = $derived(!selected ? "All" : selected.size === 0 ? "None" : `${selected.size} of ${total}`);

  function onDocClick(e) { if (open && root && !root.contains(e.target)) open = false; }
</script>

<svelte:document onclick={onDocClick} onkeydown={(e) => e.key === "Escape" && (open = false)} />

<div class="dd" bind:this={root}>
  <button class="pill" class:on={!!selected} aria-expanded={open} onclick={() => (open = !open)}>
    {label}: <strong>{summary}</strong> <span aria-hidden="true">{open ? "▴" : "▾"}</span>
  </button>
  {#if open}
    <div class="panel" class:wide role="group" aria-label={label}>
      <div class="actions">
        <button class="link" onclick={() => (selected = null)}>Select all</button>
        <button class="link" onclick={() => (selected = new Set())}>Clear</button>
      </div>
      {#each groups as g}
        {#if g.label}
          {@const st = groupState(g)}
          <div class="group">
            <label class="head">
              <input type="checkbox" checked={st === "all"} indeterminate={st === "some"} onchange={() => toggleGroup(g)} />
              {#if g.color}<span class="sw" style="background:{g.color}"></span>{/if}{g.label}
            </label>
            <div class="subs">
              {#each g.items as x}
                <label><input type="checkbox" checked={isOn(x.i)} onchange={() => toggle(x.i)} />{x.label}</label>
              {/each}
            </div>
          </div>
        {:else}
          <div class="flat">
            {#each g.items as x}
              <label><input type="checkbox" checked={isOn(x.i)} onchange={() => toggle(x.i)} />{x.label}</label>
            {/each}
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .dd { position: relative; }
  .pill { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 4px 12px; font-size: 13px; cursor: pointer; color: var(--muted); }
  .pill strong { color: var(--ink); font-weight: 600; }
  .pill.on { border-color: var(--accent); background: var(--accent-soft); }
  .panel { position: absolute; z-index: 5; top: calc(100% + 6px); left: 0; width: min(280px, calc(100vw - 32px)); max-height: 65vh; overflow: auto;
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 10px 12px; box-shadow: 0 6px 24px rgba(0,0,0,.12); font-size: 13px; }
  .panel.wide { width: min(440px, calc(100vw - 32px)); }
  .actions { display: flex; gap: 14px; padding-bottom: 6px; }
  .group { border-top: 1px solid var(--line); padding: 6px 0; }
  .head { display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 13.5px; }
  .subs { display: grid; gap: 2px; padding: 3px 0 0 24px; }
  .flat { display: grid; gap: 4px; border-top: 1px solid var(--line); padding-top: 6px; }
  label { display: flex; gap: 6px; align-items: center; cursor: pointer; }
  .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font-size: 13px; }
</style>

<script>
  import Dropdown from "./Dropdown.svelte";
  import { L1_COLORS, STAGE_LABELS } from "./data.js";

  let { index, f = $bindable(), onclear } = $props();

  const typeGroups = $derived(index.l1.map((g) => ({
    label: g.label, color: L1_COLORS[g.id],
    items: index.l2.map((x, i) => ({ i, label: x.label, l1: x.l1 })).filter((x) => x.l1 === g.id),
  })));
  const stageGroups = $derived([{ items: index.stages.map((s, i) => ({ i, label: STAGE_LABELS[s] })) }]);
  const registryGroups = $derived(["Independent standards", "Government & UN mechanisms", "Announcements"].map((g) => ({
    label: g, items: index.registries.map((r, i) => ({ i, label: r.label, group: r.group })).filter((x) => x.group === g),
  })));
</script>

<div class="filters">
  <Dropdown label="Credit type" groups={typeGroups} total={index.l2.length} bind:selected={f.l2} wide />
  <Dropdown label="Project stage" groups={stageGroups} total={index.stages.length} bind:selected={f.stages} />
  <Dropdown label="Registry" groups={registryGroups} total={index.registries.length} bind:selected={f.registries} />
  <label class="toggle"><input type="checkbox" bind:checked={f.a6} /> Article 6 only</label>
  <input class="search" type="search" placeholder="Search project or developer" bind:value={f.q} aria-label="Search" />
  <button class="link" onclick={onclear}>Clear filters</button>
</div>

<style>
  .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 14px 0; }
  .toggle { font-size: 13px; display: flex; gap: 6px; align-items: center; }
  .search { flex: 1 1 200px; min-width: 0; border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; background: var(--surface); font-size: 14px; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font-size: 13px; }
</style>

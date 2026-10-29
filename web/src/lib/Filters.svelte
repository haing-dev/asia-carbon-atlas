<script>
  import Dropdown from "./Dropdown.svelte";
  import { L1_COLORS, STAGE_LABELS } from "./data.js";

  let { index, f = $bindable(), onclear } = $props();

  const typeGroups = $derived(index.l1.map((g) => ({
    label: g.label, color: L1_COLORS[g.id],
    items: index.l2.map((x, i) => ({ i, label: x.label, l1: x.l1 })).filter((x) => x.l1 === g.id),
  })));
  const stageGroups = $derived([{ items: index.stages.map((s, i) => ({ i, label: STAGE_LABELS[s] })) }]);
  const eligGroups = $derived([{ items: (index.eligibility || []).map((e, i) => ({ i, label: e.label, title: "Source: " + (e.source || ""),
    n: index.projects.filter((p) => p.el >> i & 1).length })) }]);
  const registryGroups = $derived(["Independent standards", "Government & UN mechanisms", "Announcements"].map((g) => ({
    label: g, items: index.registries.map((r, i) => ({ i, label: r.label, group: r.group, present: r.present !== false }))
      .filter((x) => x.group === g && x.present),
  })).filter((g) => g.items.length));
</script>

<div class="filters">
  <Dropdown label="Credit type" groups={typeGroups} total={index.l2.length} bind:selected={f.l2} wide />
  <Dropdown label="Project stage" groups={stageGroups} total={index.stages.length} bind:selected={f.stages} />
  <Dropdown label="Registry" groups={registryGroups} total={index.registries.filter((r) => r.present !== false).length} bind:selected={f.registries} />
  <Dropdown label="Eligibility" groups={eligGroups} total={(index.eligibility || []).length} bind:selected={f.el} optIn
    title="Tick labels to show only projects that carry them" />
  <input class="search" type="search" placeholder="Search project, developer, offtaker or tag (e.g. AWD, ERW)" bind:value={f.q} aria-label="Search" />
  <button class="link" onclick={onclear}>Clear filters</button>
</div>

<style>
  .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 14px 0; }
  .search { flex: 1 1 200px; min-width: 0; border: 0; border-bottom: 1px solid var(--black); border-radius: 0; padding: 4px 2px; background: var(--white); font-size: 14px; }
  .link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font-size: 13px; }
</style>

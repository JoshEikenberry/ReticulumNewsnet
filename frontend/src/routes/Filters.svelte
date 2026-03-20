<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { filters } from '../lib/stores';
  import type { Filter } from '../lib/types';

  let newType: Filter['type'] = 'word';
  let newMode: Filter['mode'] = 'blacklist';
  let newPattern = '';
  let addError = '';

  onMount(async () => {
    filters.set(await api.listFilters());
  });

  async function addFilter() {
    if (!newPattern.trim()) { addError = 'Pattern is required.'; return; }
    addError = '';
    try {
      await api.addFilter({ type: newType, mode: newMode, pattern: newPattern.trim() });
      newPattern = '';
      filters.set(await api.listFilters());
    } catch (e: any) {
      addError = e.message;
    }
  }

  async function removeFilter(f: Filter) {
    await api.removeFilter(f);
    filters.set(await api.listFilters());
  }
</script>

<div class="filters-page">
  <h2>Content Filters</h2>
  <p class="muted">Filtered content is blocked from being stored or forwarded to other nodes.</p>

  {#each $filters as f}
    <div class="filter-row">
      <span class="tag {f.mode}">{f.mode}</span>
      <span class="tag type">{f.type}</span>
      <code>{f.pattern}</code>
      <button on:click={() => removeFilter(f)}>Remove</button>
    </div>
  {/each}

  {#if $filters.length === 0}
    <p class="muted">No filters yet.</p>
  {/if}

  <div class="add-filter">
    <select bind:value={newType}>
      <option value="word">Word</option>
      <option value="author">Author hash</option>
      <option value="newsgroup">Newsgroup</option>
    </select>
    <select bind:value={newMode}>
      <option value="blacklist">Block</option>
      <option value="whitelist">Allow only</option>
    </select>
    <input type="text" bind:value={newPattern} placeholder="Pattern..." />
    <button class="primary" on:click={addFilter}>Add</button>
  </div>
  {#if addError}<p class="error">{addError}</p>{/if}
</div>

<style>
  .filters-page { max-width: 600px; }
  h2 { margin-bottom: 8px; }
  .muted { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 12px; }
  .filter-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--border); }
  .filter-row code { flex: 1; font-size: 0.85rem; color: #aef; }
  .tag { font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; }
  .tag.blacklist { background: #500; color: #f99; }
  .tag.whitelist { background: #050; color: #9f9; }
  .tag.type { background: var(--border); color: var(--text-muted); }
  .add-filter { display: flex; gap: 8px; margin-top: 16px; }
  .add-filter input { flex: 1; }
  .add-filter select { width: auto; }
  .error { color: var(--accent); font-size: 0.85rem; margin-top: 6px; }
</style>

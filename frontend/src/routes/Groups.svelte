<script lang="ts">
  import { groups, selectedGroup, articlesByGroup, currentArticles } from '../lib/stores';
  import { api } from '../lib/api';

  async function selectGroup(g: string) {
    selectedGroup.set(g);
    const articles = await api.listArticles(g);
    articlesByGroup.update(m => ({ ...m, [g]: articles }));
    window.location.hash = `#/group/${encodeURIComponent(g)}`;
  }

  function unreadCount(g: string): number {
    // For now, show total article count per group
    return 0; // placeholder until read-tracking is implemented
  }
</script>

<div class="groups-panel">
  <div class="section-header">GROUPS</div>
  {#each $groups as g}
    <button
      class="group-item"
      class:active={$selectedGroup === g}
      on:click={() => selectGroup(g)}
    >
      <span class="group-name">{g}</span>
    </button>
  {/each}

  <div class="section-header peers-header">
    <a href="#/peers">PEERS</a>
  </div>
  <div class="section-header">
    <a href="#/filters">FILTERS</a>
  </div>
</div>

<style>
  .groups-panel { padding: 8px 0; font-size: 0.85rem; }
  .section-header {
    padding: 6px 12px 2px;
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .section-header a { color: var(--text-muted); text-decoration: none; }
  .section-header a:hover { color: var(--text); }
  .group-item {
    display: flex;
    justify-content: space-between;
    width: 100%;
    padding: 5px 12px;
    border: none;
    background: transparent;
    color: var(--text);
    text-align: left;
    border-radius: 0;
    font-size: 0.85rem;
  }
  .group-item:hover { background: var(--border); }
  .group-item.active { background: var(--accent); color: white; }
</style>

<script lang="ts">
  import { syncStatus, nodeReady, lastSyncCount } from '../lib/stores';
</script>

<div class="statusbar-inner">
  <span class="brand">ReticulumNewsnet</span>

  <span class="status">
    {#if !$nodeReady}
      <span class="dot starting">●</span> Starting up...
    {:else if $syncStatus === 'syncing'}
      <span class="dot syncing">●</span> Syncing...
    {:else}
      <span class="dot ready">●</span> Up to date
    {/if}
  </span>

  <nav>
    <a href="#/settings">⚙</a>
  </nav>
</div>

<style>
  .statusbar-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 12px;
    height: 100%;
    font-size: 0.85rem;
  }
  .brand { font-weight: 600; }
  .dot { font-size: 0.6rem; }
  .dot.starting { color: orange; }
  .dot.syncing { color: #4af; }
  .dot.ready { color: #4f4; }
  nav a { color: var(--text-muted); text-decoration: none; font-size: 1.1rem; }
</style>

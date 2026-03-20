<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { rnsPeers, tcpPeers } from '../lib/stores';

  let newPeerAddr = '';
  let addError = '';

  onMount(async () => {
    const data = await api.listPeers();
    rnsPeers.set(data.rns_peers);
    tcpPeers.set(data.tcp_peers);
  });

  async function addPeer() {
    addError = '';
    try {
      await api.addPeer(newPeerAddr.trim());
      newPeerAddr = '';
      const data = await api.listPeers();
      tcpPeers.set(data.tcp_peers);
    } catch (e: any) {
      addError = e.message;
    }
  }

  async function removePeer(addr: string) {
    await api.removePeer(addr);
    const data = await api.listPeers();
    tcpPeers.set(data.tcp_peers);
  }
</script>

<div class="peers-page">
  <h2>Connected Neighbors</h2>

  <section>
    <h3>Auto-Discovered (same network)</h3>
    {#if $rnsPeers.length === 0}
      <p class="muted">No neighbors found yet. They'll appear when other Newsnet nodes announce themselves.</p>
    {:else}
      {#each $rnsPeers as p}
        <div class="peer-row">
          <span>{p.display_name ?? p.destination_hash.slice(0, 16) + '...'}</span>
          <span class="muted">{p.last_seen ? new Date(p.last_seen * 1000).toLocaleString() : 'never'}</span>
        </div>
      {/each}
    {/if}
  </section>

  <section>
    <h3>Remote Nodes (TCP)</h3>
    {#each $tcpPeers as p}
      <div class="peer-row">
        <span class:connected={p.connected} class:disconnected={!p.connected}>
          {p.connected ? '●' : '○'} {p.address}
        </span>
        {#if p.fail_count > 0}<span class="muted">{p.fail_count} failures</span>{/if}
        <button on:click={() => removePeer(p.address)}>Remove</button>
      </div>
    {/each}

    <div class="add-peer">
      <input type="text" bind:value={newPeerAddr} placeholder="192.168.1.x:4965" />
      <button class="primary" on:click={addPeer}>Add Node</button>
    </div>
    {#if addError}<p class="error">{addError}</p>{/if}
  </section>
</div>

<style>
  .peers-page { max-width: 600px; }
  h2 { margin-bottom: 16px; }
  h3 { font-size: 0.85rem; color: var(--text-muted); margin: 16px 0 8px; text-transform: uppercase; }
  section { margin-bottom: 24px; }
  .peer-row { display: flex; align-items: center; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
  .peer-row span:first-child { flex: 1; }
  .connected { color: #4f4; }
  .disconnected { color: var(--text-muted); }
  .muted { color: var(--text-muted); font-size: 0.8rem; }
  .add-peer { display: flex; gap: 8px; margin-top: 12px; }
  .add-peer input { flex: 1; }
  .error { color: var(--accent); font-size: 0.85rem; margin-top: 6px; }
</style>

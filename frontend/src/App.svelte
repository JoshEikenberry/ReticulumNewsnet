<script lang="ts">
  import { onMount } from 'svelte';
  import { token, nodeReady, groups, identity, syncStatus, lastSyncCount, rnsPeers, tcpPeers, filters, config as configStore } from './lib/stores';
  import { api } from './lib/api';
  import { connectWs, onWsEvent } from './lib/ws';
  import StatusBar from './components/StatusBar.svelte';
  import './app.css';

  // Hash-based routing (no dependencies)
  let route = window.location.hash || '#/';
  window.addEventListener('hashchange', () => { route = window.location.hash; });

  let tokenInput = '';
  let authError = '';

  async function tryAuth() {
    token.set(tokenInput.trim());
    try {
      const id = await api.getIdentity();
      identity.set(id);
      authError = '';
      bootstrap();
    } catch (e: any) {
      authError = e.message === 'unauthorized' ? 'Incorrect token.' : e.message;
      token.set('');
    }
  }

  async function bootstrap() {
    connectWs($token);
    onWsEvent((e) => {
      if (e.type === 'node_ready') nodeReady.set(true);
      if (e.type === 'sync_started') syncStatus.set('syncing');
      if (e.type === 'sync_done') {
        syncStatus.set('idle');
        lastSyncCount.set((e.count as number) ?? 0);
      }
    });

    try {
      const [g, id, cfg] = await Promise.all([
        api.listGroups(),
        api.getIdentity(),
        api.getConfig(),
      ]);
      groups.set(g);
      identity.set(id);
      configStore.set(cfg);
      nodeReady.set(true);
    } catch (e: any) {
      if (e.message === 'starting up') {
        // Will become ready when node_ready WS event arrives
        nodeReady.set(false);
      }
    }
  }

  onMount(async () => {
    // If token is in the URL (?token=...), store it and clean the URL
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get('token');
    if (urlToken) {
      token.set(urlToken);
      const clean = window.location.pathname + window.location.hash;
      window.history.replaceState(null, '', clean);
    }

    // For localhost connections, fetch the token automatically — no manual entry needed.
    // (Remote/phone users still use the token gate.)
    if (!$token) {
      try {
        const res = await fetch('/api/local-auth');
        if (res.ok) {
          const data = await res.json();
          token.set(data.token);
        }
      } catch (_) { /* not localhost or server not ready */ }
    }

    if ($token) bootstrap();
  });
</script>

{#if !$token}
  <!-- Token entry screen -->
  <div class="auth-screen">
    <h1>ReticulumNewsnet</h1>
    <p>Enter your node access token to connect.</p>
    <input type="password" bind:value={tokenInput} placeholder="Access token" on:keydown={(e) => e.key === 'Enter' && tryAuth()} />
    {#if authError}<p class="error">{authError}</p>{/if}
    <button class="primary" on:click={tryAuth}>Connect</button>
  </div>
{:else}
  <div class="layout">
    <div class="statusbar"><StatusBar /></div>

    <aside class="sidebar">
      <!-- Sidebar content loaded by Groups route -->
      {#await import('./routes/Groups.svelte') then { default: Groups }}
        <svelte:component this={Groups} />
      {/await}
    </aside>

    <main class="main">
      {#if route === '#/' || route.startsWith('#/group')}
        {#await import('./routes/Thread.svelte') then { default: Thread }}
          <svelte:component this={Thread} />
        {/await}
      {:else if route === '#/peers'}
        {#await import('./routes/Peers.svelte') then { default: Peers }}
          <svelte:component this={Peers} />
        {/await}
      {:else if route === '#/filters'}
        {#await import('./routes/Filters.svelte') then { default: Filters }}
          <svelte:component this={Filters} />
        {/await}
      {:else if route === '#/settings'}
        {#await import('./routes/Settings.svelte') then { default: Settings }}
          <svelte:component this={Settings} />
        {/await}
      {/if}
    </main>
  </div>
{/if}

<style>
  .auth-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: 12px;
    max-width: 320px;
    margin: auto;
  }
  .auth-screen h1 { font-size: 1.4rem; }
  .error { color: var(--accent); font-size: 0.85rem; }
</style>

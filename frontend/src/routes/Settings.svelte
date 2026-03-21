<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { identity, config as configStore, token } from '../lib/stores';
  import type { Config } from '../lib/types';

  let cfg: Config | null = null;
  let saving = false;
  let saved = false;
  let restartNeeded = false;
  let saveError = '';

  onMount(async () => {
    const [id, c] = await Promise.all([api.getIdentity(), api.getConfig()]);
    identity.set(id);
    configStore.set(c);
    cfg = { ...c };
  });

  async function save() {
    if (!cfg) return;
    saving = true;
    saved = false;
    saveError = '';
    try {
      const res = await api.patchConfig(cfg);
      restartNeeded = res.restart_required;
      saved = true;
      configStore.set(cfg);
    } catch (e: any) {
      saveError = e.message;
    } finally {
      saving = false;
    }
  }

  function disconnect() {
    token.set('');
    window.location.reload();
  }
</script>

<div class="settings-page">
  <h2>Settings</h2>

  {#if $identity}
    <section>
      <h3>Your Identity</h3>
      <p class="identity-words">{$identity.identity_words}</p>
      <p class="mono">{$identity.identity_hash}</p>
      <p class="muted">Your identity words are a human-readable label for your cryptographic identity. Share them so others can recognise you. Every post you write is signed with this identity.</p>
      {#if $identity.tcp_address}
        <p><strong>Node address:</strong> <code>{$identity.tcp_address}</code>
          <span class="muted"> — share this with friends to connect over the internet</span></p>
      {:else}
        <p class="muted">Your node is only accessible on this machine. To allow remote connections, change API Host to <code>0.0.0.0</code> below.</p>
      {/if}
    </section>
  {/if}

  <section>
    <h3>Access Token</h3>
    <code class="token-display">{$token}</code>
    <p class="muted">This token is required to connect any client to your node.</p>
  </section>

  {#if cfg}
    <section>
      <h3>Node Configuration</h3>

      <label>
        Display Name
        <input type="text" bind:value={cfg.display_name} />
      </label>

      <label>
        Retention (hours, 1–720)
        <input type="number" min="1" max="720" bind:value={cfg.retention_hours} />
      </label>

      <label>
        Sync Interval (minutes)
        <input type="number" min="1" bind:value={cfg.sync_interval_minutes} />
      </label>

      <label class="checkbox-label">
        <input type="checkbox" bind:checked={cfg.strict_filtering} />
        Strict filtering (filter content before forwarding to peers)
      </label>

      <label>
        API Host <span class="muted">(requires restart)</span>
        <input type="text" bind:value={cfg.api_host} />
      </label>

      <label>
        API Port <span class="muted">(requires restart)</span>
        <input type="number" bind:value={cfg.api_port} />
      </label>

      {#if saveError}<p class="error">{saveError}</p>{/if}
      {#if restartNeeded}<p class="warn">Some changes require restarting the daemon to take effect.</p>{/if}
      {#if saved && !restartNeeded}<p class="success">Saved.</p>{/if}

      <button class="primary" on:click={save} disabled={saving}>
        {saving ? 'Saving...' : 'Save'}
      </button>
    </section>
  {/if}

  <section>
    <h3>Connection</h3>
    <button on:click={disconnect}>Disconnect</button>
    <p class="muted">Clears the token from this browser. The node keeps running.</p>
  </section>
</div>

<style>
  .settings-page { max-width: 500px; }
  h2 { margin-bottom: 16px; }
  h3 { font-size: 0.85rem; color: var(--text-muted); margin: 20px 0 10px; text-transform: uppercase; }
  section { border-top: 1px solid var(--border); padding-top: 12px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 0.85rem; margin-bottom: 10px; }
  .checkbox-label { flex-direction: row; align-items: center; gap: 8px; }
  .checkbox-label input { width: auto; }
  .identity-words { font-size: 1.15rem; font-weight: 600; letter-spacing: 0.03em; margin-bottom: 4px; }
  .mono { font-family: monospace; font-size: 0.8rem; word-break: break-all; color: var(--text-muted); }
  .token-display { display: block; font-size: 0.8rem; word-break: break-all; margin-bottom: 4px; }
  .muted { color: var(--text-muted); font-size: 0.8rem; }
  .error { color: var(--accent); font-size: 0.85rem; }
  .warn { color: orange; font-size: 0.85rem; }
  .success { color: #4f4; font-size: 0.85rem; }
  code { font-size: 0.85rem; color: #aef; }
</style>

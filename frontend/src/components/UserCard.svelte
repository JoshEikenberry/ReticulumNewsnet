<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let display_name: string;
  export let author_words: string;
  export let author_hash: string;

  const dispatch = createEventDispatcher();

  function close() { dispatch('close'); }

  function copyHash() {
    navigator.clipboard?.writeText(author_hash);
  }
</script>

<svelte:window on:keydown={(e) => e.key === 'Escape' && close()} />

<!-- Backdrop -->
<div class="backdrop" on:click|self={close} role="button" tabindex="-1">
  <div class="card">
    <div class="display-name">{display_name}</div>
    <div class="words">{author_words}</div>
    <div class="hash-row">
      <code class="hash">{author_hash}</code>
      <button class="copy" on:click={copyHash} title="Copy hash">⎘</button>
    </div>
    <p class="muted">Identity words are derived from this user's cryptographic public key and never change.</p>
    <button class="close-btn" on:click={close}>Close</button>
  </div>
</div>

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.5);
    display: flex; align-items: center; justify-content: center;
    z-index: 200;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    width: 90%; max-width: 380px;
    display: flex; flex-direction: column; gap: 10px;
  }
  .display-name { font-size: 1.2rem; font-weight: 600; }
  .words { font-size: 1.05rem; letter-spacing: 0.04em; color: var(--accent); }
  .hash-row { display: flex; align-items: center; gap: 6px; }
  .hash { font-size: 0.72rem; word-break: break-all; color: var(--text-muted); flex: 1; }
  .copy {
    background: none; border: 1px solid var(--border);
    color: var(--text-muted); border-radius: 4px;
    padding: 2px 6px; cursor: pointer; font-size: 0.9rem; flex-shrink: 0;
  }
  .copy:hover { color: var(--text); }
  .muted { font-size: 0.78rem; color: var(--text-muted); margin: 0; }
  .close-btn { align-self: flex-end; margin-top: 4px; }
</style>

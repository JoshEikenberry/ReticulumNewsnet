<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { api } from '../lib/api';
  import { groups } from '../lib/stores';

  export let newsgroup: string = '';
  export let replyTo: string | null = null;
  export let replySubject: string = '';

  const dispatch = createEventDispatcher();

  let subject = replySubject;
  let body = '';
  let selectedGroup = newsgroup;
  let submitting = false;
  let error = '';

  async function submit() {
    if (!selectedGroup.trim() || !subject.trim() || !body.trim()) {
      error = 'Group, subject, and body are required.';
      return;
    }
    submitting = true;
    error = '';
    try {
      await api.postArticle({
        newsgroup: selectedGroup.trim(),
        subject: subject.trim(),
        body: body.trim(),
        references: replyTo ? [replyTo] : [],
      });
      dispatch('close', { newsgroup: selectedGroup.trim() });
    } catch (e: any) {
      error = e.message;
    } finally {
      submitting = false;
    }
  }
</script>

<div class="compose-backdrop" on:click|self={() => dispatch('close')} role="button" tabindex="-1">
  <div class="compose-modal">
    <h2>{replyTo ? 'Reply' : 'New Post'}</h2>

    <label>
      Group
      <input
        type="text"
        list="groups-list"
        bind:value={selectedGroup}
        placeholder="e.g. tech.linux"
      />
      <datalist id="groups-list">
        {#each $groups as g}<option value={g} />{/each}
      </datalist>
    </label>

    <label>
      Subject
      <input type="text" bind:value={subject} placeholder="Subject" />
    </label>

    <label>
      Body
      <textarea bind:value={body} rows="8" placeholder="Write your message..."></textarea>
    </label>

    {#if error}<p class="error">{error}</p>{/if}

    <div class="actions">
      <button on:click={() => dispatch('close')}>Cancel</button>
      <button class="primary" on:click={submit} disabled={submitting}>
        {submitting ? 'Posting...' : 'Post'}
      </button>
    </div>
  </div>
</div>

<style>
  .compose-backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center;
    z-index: 100;
  }
  .compose-modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    width: 90%;
    max-width: 520px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 0.85rem; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }
  .error { color: var(--accent); font-size: 0.85rem; }
</style>

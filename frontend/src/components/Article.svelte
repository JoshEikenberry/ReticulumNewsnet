<script lang="ts">
  import type { Article } from '../lib/types';
  import UserCard from './UserCard.svelte';

  export let article: Article;
  export let depth: number = 0;
  export let compact: boolean = false;

  const indent = depth * 20;
  const date = new Date(article.timestamp * 1000).toLocaleString();

  let showUserCard = false;

  function openUserCard(e: MouseEvent) {
    e.stopPropagation();
    showUserCard = true;
  }
</script>

{#if showUserCard}
  <UserCard
    display_name={article.display_name}
    author_words={article.author_words}
    author_hash={article.author_hash}
    on:close={() => showUserCard = false}
  />
{/if}

<div class="article" style="margin-left: {indent}px">
  {#if compact}
    <div class="article-compact">
      <span class="arrow">{depth > 0 ? '└─' : '▶'}</span>
      <span class="subject">{article.subject}</span>
      <span class="meta">
        <button class="author-btn" on:click={openUserCard}>{article.display_name}</button>
        · {date}
      </span>
    </div>
  {:else}
    <div class="article-full">
      <div class="header">
        <strong>{article.subject}</strong>
        <span class="meta">
          <button class="author-btn" on:click={openUserCard}>{article.display_name}</button>
          · {date}
        </span>
      </div>
      <div class="body">{article.body}</div>
    </div>
  {/if}
</div>

<style>
  .article { border-bottom: 1px solid var(--border); }
  .article-compact {
    display: flex;
    align-items: baseline;
    gap: 6px;
    padding: 6px 8px;
    cursor: pointer;
    font-size: 0.88rem;
  }
  .article-compact:hover { background: var(--surface); }
  .arrow { color: var(--text-muted); font-size: 0.75rem; }
  .subject { flex: 1; }
  .meta { font-size: 0.75rem; color: var(--text-muted); white-space: nowrap; }
  .author-btn {
    background: none; border: none; padding: 0;
    color: var(--text-muted); font-size: inherit;
    cursor: pointer; text-decoration: underline dotted;
  }
  .author-btn:hover { color: var(--text); }
  .article-full { padding: 12px; }
  .header { display: flex; justify-content: space-between; margin-bottom: 8px; }
  .body { white-space: pre-wrap; font-size: 0.9rem; line-height: 1.5; }
</style>

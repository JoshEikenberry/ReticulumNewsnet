<script lang="ts">
  import { currentArticles, selectedGroup, selectedArticleId, articlesByGroup, groups } from '../lib/stores';
  import { api } from '../lib/api';
  import ThreadTree from '../components/ThreadTree.svelte';
  import ArticleComp from '../components/Article.svelte';
  import { onWsEvent } from '../lib/ws';

  let showCompose = false;

  async function refreshGroup(newsgroup: string) {
    // Ensure the group appears in the sidebar
    const allGroups = await api.listGroups();
    groups.set(allGroups);
    // Load its articles and navigate to it
    const articles = await api.listArticles(newsgroup);
    articlesByGroup.update(m => ({ ...m, [newsgroup]: articles }));
    selectedGroup.set(newsgroup);
    window.location.hash = `#/group/${encodeURIComponent(newsgroup)}`;
  }

  // Listen for new articles over WS and refresh current group
  onWsEvent(async (e) => {
    if (e.type === 'new_article' && e.article && $selectedGroup) {
      const articles = await api.listArticles($selectedGroup);
      articlesByGroup.update(m => ({ ...m, [$selectedGroup!]: articles }));
    }
  });

  $: selectedArticle = $selectedArticleId
    ? $currentArticles.find(a => a.message_id === $selectedArticleId) ?? null
    : null;
</script>

{#if !$selectedGroup}
  <div class="empty-state">
    <p>Select a group to start reading, or create the first post.</p>
    <button class="primary" on:click={() => showCompose = true}>+ New Post</button>
  </div>
  {#if showCompose}
    {#await import('./Compose.svelte') then { default: Compose }}
      <svelte:component
        this={Compose}
        newsgroup=""
        replyTo={null}
        replySubject=""
        on:close={(e) => { showCompose = false; if (e.detail?.newsgroup) refreshGroup(e.detail.newsgroup); }}
      />
    {/await}
  {/if}
{:else}
  <div class="thread-layout">
    <div class="thread-list">
      <div class="group-header">
        <span>{$selectedGroup}</span>
        <button class="primary" on:click={() => showCompose = true}>+ Compose</button>
      </div>
      <ThreadTree articles={$currentArticles} />
    </div>

    {#if selectedArticle}
      <div class="article-detail">
        <ArticleComp article={selectedArticle} compact={false} />
        <button on:click={() => { showCompose = true; }}>Reply</button>
      </div>
    {/if}
  </div>

  {#if showCompose}
    {#await import('./Compose.svelte') then { default: Compose }}
      <svelte:component
        this={Compose}
        newsgroup={$selectedGroup}
        replyTo={selectedArticle?.message_id ?? null}
        replySubject={selectedArticle ? `Re: ${selectedArticle.subject}` : ''}
        on:close={(e) => { showCompose = false; if (e.detail?.newsgroup) refreshGroup(e.detail.newsgroup); }}
      />
    {/await}
  {/if}
{/if}

<style>
  .empty-state { color: var(--text-muted); padding: 24px; }
  .thread-layout { display: flex; gap: 0; height: 100%; }
  .thread-list { flex: 1; overflow-y: auto; }
  .article-detail { flex: 1; padding: 12px; border-left: 1px solid var(--border); }
  .group-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
    font-weight: 600;
  }
</style>

<script lang="ts">
  import type { Article } from '../lib/types';
  import ArticleComp from './Article.svelte';
  import { selectedArticleId } from '../lib/stores';

  export let articles: Article[];
  export let depth: number = 0;
  export let parentId: string | null = null;

  // Build reply tree — keyed by parent message_id (null = root)
  function buildTree(all: Article[]): Map<string | null, Article[]> {
    const tree = new Map<string | null, Article[]>();
    for (const a of all) {
      const refs: string[] = typeof a.references === 'string'
        ? JSON.parse(a.references)
        : a.references;
      const parent = refs.length > 0 ? refs[refs.length - 1] : null;
      if (!tree.has(parent)) tree.set(parent, []);
      tree.get(parent)!.push(a);
    }
    return tree;
  }

  // Full tree is built at every level but parentId controls which children render
  $: tree = buildTree(articles);
  $: roots = tree.get(parentId) ?? [];

  function selectArticle(id: string) {
    selectedArticleId.set(id);
  }
</script>

{#each roots as root}
  <div on:click={() => selectArticle(root.message_id)} role="button" tabindex="0">
    <ArticleComp article={root} depth={depth} compact={true} />
  </div>
  {#if tree.has(root.message_id)}
    <svelte:self {articles} depth={depth + 1} parentId={root.message_id} />
  {/if}
{/each}

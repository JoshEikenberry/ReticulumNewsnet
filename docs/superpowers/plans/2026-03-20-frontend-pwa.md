# Frontend PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Svelte-based Progressive Web App that connects to the ReticulumNewsnet daemon API, providing a responsive UI for reading threads, posting articles, managing peers/filters, and configuring the node.

**Architecture:** Svelte SPA served as static files from `frontend/dist/`. The daemon API (defined in `docs/superpowers/specs/2026-03-20-platform-redesign-design.md`) is the only backend. Real-time updates via WebSocket. Built output is bundled into the PyInstaller binary.

**Tech Stack:** Svelte 5, TypeScript, Vite (build), PWA via vite-plugin-pwa. No CSS framework — plain CSS. Node.js required for build only.

**Prerequisite:** The API layer plan (`2026-03-20-api-layer.md`) must be complete before end-to-end testing, but frontend can be built independently against the API contract.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/` | Svelte project root |
| Create | `frontend/src/lib/api.ts` | REST API client (typed fetch wrappers) |
| Create | `frontend/src/lib/ws.ts` | WebSocket client (event bus) |
| Create | `frontend/src/lib/stores.ts` | Svelte stores for groups, articles, peers, config |
| Create | `frontend/src/App.svelte` | Root component, routing, auth gate |
| Create | `frontend/src/routes/Groups.svelte` | Groups sidebar + article list layout |
| Create | `frontend/src/routes/Thread.svelte` | Threaded article view |
| Create | `frontend/src/routes/Compose.svelte` | New article / reply modal |
| Create | `frontend/src/routes/Peers.svelte` | Peers panel (RNS + TCP) |
| Create | `frontend/src/routes/Filters.svelte` | Filters management panel |
| Create | `frontend/src/routes/Settings.svelte` | Node config, identity, token display |
| Create | `frontend/src/components/StatusBar.svelte` | Sync status + connection indicator |
| Create | `frontend/src/components/Article.svelte` | Single article display |
| Create | `frontend/src/components/ThreadTree.svelte` | Recursive thread indentation |
| Create | `frontend/public/manifest.json` | PWA manifest |
| Create | `frontend/src/service-worker.ts` | Service worker (app shell cache) |
| Modify | `frontend/vite.config.ts` | Vite + PWA plugin config |

---

## Task 1: Scaffold Svelte Project

**Files:**
- `frontend/` (already scaffolded — skip to Step 4)

- [ ] **Step 1: Verify scaffold is present**

```bash
ls /c/vibecode/reticulumnewsnet/frontend/src/
```

Expected output includes: `App.svelte`, `app.css`, `lib/`, `main.ts`

If `frontend/` is missing, run:
```bash
cd /c/vibecode/reticulumnewsnet
npm create vite@latest frontend -- --template svelte-ts
cd frontend && npm install
npm install -D vite-plugin-pwa workbox-window --legacy-peer-deps
```

- [ ] **Step 2: Verify dev server starts**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npm run dev
```

Expected: Dev server at http://localhost:5173. Ctrl+C to stop.

- [ ] **Step 3: Verify `.gitignore` has frontend entries**

```bash
grep "frontend/node_modules" /c/vibecode/reticulumnewsnet/.gitignore
```

Expected: line found. If missing, add to `.gitignore`:
```
frontend/node_modules/
frontend/dist/
```

---

## Task 2: API Client and Type Definitions

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: Create `frontend/src/lib/types.ts`**

```typescript
export interface Article {
  message_id: string;
  newsgroup: string;
  subject: string;
  body: string;
  author_hash: string;
  display_name: string;
  timestamp: number;
  references: string[];
  received_at: number;
}

export interface Peer {
  destination_hash: string;
  display_name: string | null;
  last_seen: number | null;
  last_synced: number | null;
}

export interface TcpPeer {
  address: string;
  connected: boolean;
  fail_count: number;
}

export interface PeersResponse {
  rns_peers: Peer[];
  tcp_peers: TcpPeer[];
}

export interface Filter {
  type: 'author' | 'newsgroup' | 'word';
  mode: 'blacklist' | 'whitelist';
  pattern: string;
}

export interface Identity {
  identity_hash: string;
  display_name: string;
  tcp_address: string | null;
}

export interface Config {
  display_name: string;
  retention_hours: number;
  sync_interval_minutes: number;
  strict_filtering: boolean;
  api_host: string;
  api_port: number;
}

export interface WsEvent {
  type: 'new_article' | 'peer_found' | 'peer_lost' | 'sync_started' | 'sync_done' | 'node_ready';
  [key: string]: unknown;
}
```

- [ ] **Step 2: Create `frontend/src/lib/api.ts`**

```typescript
/**
 * REST API client for the ReticulumNewsnet daemon.
 *
 * Token is read from localStorage key "newsnet_token".
 * All requests include Authorization: Bearer <token>.
 */
import type { Article, Config, Filter, Identity, PeersResponse } from './types';

const BASE = '/api';

function getToken(): string {
  return localStorage.getItem('newsnet_token') ?? '';
}

function headers(extra?: Record<string, string>): Record<string, string> {
  return {
    'Authorization': `Bearer ${getToken()}`,
    'Content-Type': 'application/json',
    ...extra,
  };
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: headers(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) throw new Error('unauthorized');
  if (res.status === 503) throw new Error('starting up');
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? 'request failed');
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Identity
  getIdentity: () => request<Identity>('GET', '/identity'),

  // Config
  getConfig: () => request<Config>('GET', '/config'),
  patchConfig: (patch: Partial<Config>) => request<{ restart_required: boolean; changed: string[] }>('PATCH', '/config', patch),

  // Groups
  listGroups: () => request<string[]>('GET', '/groups'),

  // Articles
  listArticles: (group?: string, after?: number) => {
    const params = new URLSearchParams();
    if (group) params.set('group', group);
    if (after !== undefined) params.set('after', String(after));
    const qs = params.toString();
    return request<Article[]>('GET', `/articles${qs ? '?' + qs : ''}`);
  },
  getArticle: (messageId: string) =>
    request<{ article: Article; thread: Article[] }>('GET', `/articles/${messageId}`),
  postArticle: (data: { newsgroup: string; subject: string; body: string; references: string[] }) =>
    request<{ message_id: string }>('POST', '/articles', data),

  // Peers
  listPeers: () => request<PeersResponse>('GET', '/peers'),
  addPeer: (address: string) => request<{ address: string }>('POST', '/peers', { address }),
  removePeer: (address: string) => request<{ removed: string }>('DELETE', `/peers/${encodeURIComponent(address)}`),

  // Sync
  triggerSync: () => request<{ synced_peers: number; status: string }>('POST', '/sync'),

  // Filters
  listFilters: () => request<Filter[]>('GET', '/filters'),
  addFilter: (f: Filter) => request<{ added: boolean }>('POST', '/filters', f),
  removeFilter: (f: Filter) =>
    request<{ removed: boolean }>('DELETE', `/filters/${encodeURIComponent(`${f.type}:${f.mode}:${f.pattern}`)}`),
};
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/src/lib/
/c/vibecode/rtk.exe git commit -m "feat: add typed API client and type definitions"
```

---

## Task 3: WebSocket Client and Svelte Stores

**Files:**
- Create: `frontend/src/lib/ws.ts`
- Create: `frontend/src/lib/stores.ts`

- [ ] **Step 1: Create `frontend/src/lib/ws.ts`**

```typescript
/**
 * WebSocket client. Connects to /ws?token=<token>.
 * Emits events to registered handlers.
 * Auto-reconnects on close.
 */
import type { WsEvent } from './types';

type Handler = (event: WsEvent) => void;

let socket: WebSocket | null = null;
const handlers: Set<Handler> = new Set();
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function onWsEvent(handler: Handler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

export function connectWs(token: string): void {
  if (socket && socket.readyState < 2) return; // already open or connecting

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws?token=${encodeURIComponent(token)}`;
  socket = new WebSocket(url);

  socket.onmessage = (e) => {
    try {
      const event: WsEvent = JSON.parse(e.data);
      for (const h of handlers) h(event);
    } catch {
      // ignore malformed messages
    }
  };

  socket.onclose = () => {
    socket = null;
    // Reconnect after 3 seconds
    reconnectTimer = setTimeout(() => connectWs(token), 3000);
  };

  socket.onerror = () => {
    socket?.close();
  };
}

export function disconnectWs(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  socket?.close();
  socket = null;
}
```

- [ ] **Step 2: Create `frontend/src/lib/stores.ts`**

```typescript
/**
 * Svelte stores for shared application state.
 * Components subscribe to these; ws.ts and api calls update them.
 */
import { writable, derived } from 'svelte/store';
import type { Article, Config, Filter, Identity, Peer, TcpPeer } from './types';

// Auth
export const token = writable<string>(localStorage.getItem('newsnet_token') ?? '');
token.subscribe((v) => localStorage.setItem('newsnet_token', v));

// Node state
export const nodeReady = writable<boolean>(false);
export const syncStatus = writable<'idle' | 'syncing'>('idle');
export const lastSyncCount = writable<number>(0);

// Identity
export const identity = writable<Identity | null>(null);

// Groups
export const groups = writable<string[]>([]);
export const selectedGroup = writable<string | null>(null);

// Articles
export const articlesByGroup = writable<Record<string, Article[]>>({});
export const selectedArticleId = writable<string | null>(null);

// Derived: articles for selected group
export const currentArticles = derived(
  [articlesByGroup, selectedGroup],
  ([$articles, $group]) => ($group ? $articles[$group] ?? [] : [])
);

// Peers
export const rnsPeers = writable<Peer[]>([]);
export const tcpPeers = writable<TcpPeer[]>([]);

// Filters
export const filters = writable<Filter[]>([]);

// Config
export const config = writable<Config | null>(null);
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/src/lib/
/c/vibecode/rtk.exe git commit -m "feat: add WebSocket client and Svelte stores"
```

---

## Task 4: App Shell — Layout, Routing, Auth Gate, Loading State

**Files:**
- Modify: `frontend/src/App.svelte`
- Create: `frontend/src/app.css`
- Create: `frontend/src/components/StatusBar.svelte`

- [ ] **Step 1: Create `frontend/src/app.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --border: #0f3460;
  --accent: #e94560;
  --text: #eaeaea;
  --text-muted: #888;
  --sidebar-w: 220px;
}

body {
  font-family: system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  height: 100vh;
  overflow: hidden;
}

button {
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 0.9rem;
}

button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

input, textarea, select {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.9rem;
  width: 100%;
}

.layout {
  display: grid;
  grid-template-rows: 40px 1fr;
  grid-template-columns: var(--sidebar-w) 1fr;
  height: 100vh;
}

.statusbar { grid-column: 1 / -1; }

.sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 8px 0;
}

.main {
  overflow-y: auto;
  padding: 16px;
}

/* Mobile: collapse sidebar */
@media (max-width: 600px) {
  .layout {
    grid-template-columns: 1fr;
    grid-template-rows: 40px auto 1fr;
  }
  .sidebar { display: none; }
  .sidebar.open { display: block; }
}
```

- [ ] **Step 2: Create `frontend/src/components/StatusBar.svelte`**

```svelte
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
```

- [ ] **Step 3: Rewrite `frontend/src/App.svelte`**

```svelte
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

  onMount(() => {
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
```

- [ ] **Step 4: Verify dev server still works**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npm run dev
```

Expected: No build errors.

- [ ] **Step 5: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/src/
/c/vibecode/rtk.exe git commit -m "feat: add app shell with auth gate, layout, and status bar"
```

---

## Task 5: Groups Sidebar and Thread View

**Files:**
- Create: `frontend/src/routes/Groups.svelte`
- Create: `frontend/src/routes/Thread.svelte`
- Create: `frontend/src/components/Article.svelte`
- Create: `frontend/src/components/ThreadTree.svelte`

- [ ] **Step 1: Create `frontend/src/routes/Groups.svelte`**

```svelte
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
```

- [ ] **Step 2: Create `frontend/src/components/Article.svelte`**

```svelte
<script lang="ts">
  import type { Article } from '../lib/types';
  export let article: Article;
  export let depth: number = 0;
  export let compact: boolean = false;

  const indent = depth * 20;
  const date = new Date(article.timestamp * 1000).toLocaleString();
</script>

<div class="article" style="margin-left: {indent}px">
  {#if compact}
    <div class="article-compact">
      <span class="arrow">{depth > 0 ? '└─' : '▶'}</span>
      <span class="subject">{article.subject}</span>
      <span class="meta">{article.display_name} · {date}</span>
    </div>
  {:else}
    <div class="article-full">
      <div class="header">
        <strong>{article.subject}</strong>
        <span class="meta">{article.display_name} · {date}</span>
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
  .article-full { padding: 12px; }
  .header { display: flex; justify-content: space-between; margin-bottom: 8px; }
  .body { white-space: pre-wrap; font-size: 0.9rem; line-height: 1.5; }
</style>
```

- [ ] **Step 3: Create `frontend/src/components/ThreadTree.svelte`**

```svelte
<script lang="ts">
  import type { Article } from '../lib/types';
  import ArticleComp from './Article.svelte';
  import { selectedArticleId } from '../lib/stores';

  export let articles: Article[];
  export let depth: number = 0;

  // Build reply tree
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

  $: tree = buildTree(articles);
  $: roots = tree.get(null) ?? [];

  function selectArticle(id: string) {
    selectedArticleId.set(id);
    window.location.hash = `#/article/${encodeURIComponent(id)}`;
  }
</script>

{#each roots as root}
  <div on:click={() => selectArticle(root.message_id)} role="button" tabindex="0">
    <ArticleComp article={root} depth={depth} compact={true} />
  </div>
  {#if tree.has(root.message_id)}
    <svelte:self articles={tree.get(root.message_id) ?? []} depth={depth + 1} />
  {/if}
{/each}
```

- [ ] **Step 4: Create `frontend/src/routes/Thread.svelte`**

```svelte
<script lang="ts">
  import { currentArticles, selectedGroup, selectedArticleId, articlesByGroup } from '../lib/stores';
  import { api } from '../lib/api';
  import ThreadTree from '../components/ThreadTree.svelte';
  import ArticleComp from '../components/Article.svelte';
  import { onWsEvent } from '../lib/ws';

  let showCompose = false;

  // Listen for new articles over WS and refresh group
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
  <div class="empty-state">Select a group to start reading.</div>
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
        on:close={() => showCompose = false}
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
```

- [ ] **Step 5: Verify build**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npm run build
```

Expected: Build succeeds, output in `frontend/dist/`.

- [ ] **Step 6: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/src/
/c/vibecode/rtk.exe git commit -m "feat: add groups sidebar, thread tree, and article view"
```

---

## Task 6: Compose, Peers, Filters, and Settings

**Files:**
- Create: `frontend/src/routes/Compose.svelte`
- Create: `frontend/src/routes/Peers.svelte`
- Create: `frontend/src/routes/Filters.svelte`
- Create: `frontend/src/routes/Settings.svelte`

- [ ] **Step 1: Create `frontend/src/routes/Compose.svelte`**

```svelte
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
      dispatch('close');
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
```

- [ ] **Step 2: Create `frontend/src/routes/Peers.svelte`**

```svelte
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
```

- [ ] **Step 3: Create `frontend/src/routes/Filters.svelte`**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { filters } from '../lib/stores';
  import type { Filter } from '../lib/types';

  let newType: Filter['type'] = 'word';
  let newMode: Filter['mode'] = 'blacklist';
  let newPattern = '';
  let addError = '';

  onMount(async () => {
    filters.set(await api.listFilters());
  });

  async function addFilter() {
    if (!newPattern.trim()) { addError = 'Pattern is required.'; return; }
    addError = '';
    try {
      await api.addFilter({ type: newType, mode: newMode, pattern: newPattern.trim() });
      newPattern = '';
      filters.set(await api.listFilters());
    } catch (e: any) {
      addError = e.message;
    }
  }

  async function removeFilter(f: Filter) {
    await api.removeFilter(f);
    filters.set(await api.listFilters());
  }
</script>

<div class="filters-page">
  <h2>Content Filters</h2>
  <p class="muted">Filtered content is blocked from being stored or forwarded to other nodes.</p>

  {#each $filters as f}
    <div class="filter-row">
      <span class="tag {f.mode}">{f.mode}</span>
      <span class="tag type">{f.type}</span>
      <code>{f.pattern}</code>
      <button on:click={() => removeFilter(f)}>Remove</button>
    </div>
  {/each}

  {#if $filters.length === 0}
    <p class="muted">No filters yet.</p>
  {/if}

  <div class="add-filter">
    <select bind:value={newType}>
      <option value="word">Word</option>
      <option value="author">Author hash</option>
      <option value="newsgroup">Newsgroup</option>
    </select>
    <select bind:value={newMode}>
      <option value="blacklist">Block</option>
      <option value="whitelist">Allow only</option>
    </select>
    <input type="text" bind:value={newPattern} placeholder="Pattern..." />
    <button class="primary" on:click={addFilter}>Add</button>
  </div>
  {#if addError}<p class="error">{addError}</p>{/if}
</div>

<style>
  .filters-page { max-width: 600px; }
  h2 { margin-bottom: 8px; }
  .muted { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 12px; }
  .filter-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--border); }
  .filter-row code { flex: 1; font-size: 0.85rem; color: #aef; }
  .tag { font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; }
  .tag.blacklist { background: #500; color: #f99; }
  .tag.whitelist { background: #050; color: #9f9; }
  .tag.type { background: var(--border); color: var(--text-muted); }
  .add-filter { display: flex; gap: 8px; margin-top: 16px; }
  .add-filter input { flex: 1; }
  .add-filter select { width: auto; }
  .error { color: var(--accent); font-size: 0.85rem; margin-top: 6px; }
</style>
```

- [ ] **Step 4: Create `frontend/src/routes/Settings.svelte`**

```svelte
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
      <p class="mono">{$identity.identity_hash}</p>
      <p class="muted">This is your cryptographic identity. Every post you write is signed with it.</p>
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
  .mono { font-family: monospace; font-size: 0.8rem; word-break: break-all; color: var(--text-muted); }
  .token-display { display: block; font-size: 0.8rem; word-break: break-all; margin-bottom: 4px; }
  .muted { color: var(--text-muted); font-size: 0.8rem; }
  .error { color: var(--accent); font-size: 0.85rem; }
  .warn { color: orange; font-size: 0.85rem; }
  .success { color: #4f4; font-size: 0.85rem; }
  code { font-size: 0.85rem; color: #aef; }
</style>
```

- [ ] **Step 5: Build and verify**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 6: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/src/routes/
/c/vibecode/rtk.exe git commit -m "feat: add Compose, Peers, Filters, and Settings screens"
```

---

## Task 7: PWA Manifest and Service Worker

**Files:**
- Create: `frontend/public/manifest.json`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Create `frontend/public/manifest.json`**

```json
{
  "name": "ReticulumNewsnet",
  "short_name": "Newsnet",
  "description": "Decentralized peer-to-peer news network",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#16213e",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 2: Create placeholder icons**

Create two minimal PNG placeholders (they will be replaced with real icons later):

```bash
cd /c/vibecode/reticulumnewsnet/frontend/public
# Create 1x1 pixel PNGs as placeholders using Python
python3 -c "
import struct, zlib

def make_png(size):
    w = h = size
    raw = b'\\x00' + b'\\x00\\x0f\\x3c' * w  # dark blue pixels
    raw = b''.join(b'\\x00' + b'\\x00\\x0f\\x3c' * w for _ in range(h))
    def chunk(name, data):
        c = struct.pack('>I', len(data)) + name + data
        return c + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    return b'\\x89PNG\\r\\n\\x1a\\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

open('icon-192.png', 'wb').write(make_png(192))
open('icon-512.png', 'wb').write(make_png(512))
print('Created placeholder icons')
"
```

- [ ] **Step 3: Update `frontend/vite.config.ts`**

Read the current file first, then replace its contents:

```typescript
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: false,  // We provide our own manifest.json in public/
      workbox: {
        // Cache app shell (JS/CSS/HTML) — cache-first
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Network-first for all /api/* routes — never serve from cache
        runtimeCaching: [
          {
            urlPattern: /^\/api\//,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^\/ws/,
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
```

- [ ] **Step 4: Build with PWA**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npm run build
```

Expected: Build succeeds. `frontend/dist/` contains `manifest.json`, `sw.js`, and the app bundle.

- [ ] **Step 5: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/
/c/vibecode/rtk.exe git commit -m "feat: add PWA manifest and service worker with app-shell caching"
```

---

## Task 8: Build Integration and End-to-End Smoke Test

**Files:**
- Create: `frontend/build.sh` (build helper)
- Verify: PyInstaller sees `frontend/dist/`

- [ ] **Step 1: Add npm build script for CI**

Create `frontend/build.sh`:
```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
npm ci
npm run build
echo "[newsnet-frontend] Build complete: dist/"
```

Make executable on Unix: `chmod +x frontend/build.sh`

- [ ] **Step 2: Add frontend build to pyproject.toml build notes**

In `pyproject.toml`, add a comment under `[build-system]`:
```toml
# Before building the Python binary, run: cd frontend && npm ci && npm run build
# This generates frontend/dist/ which is bundled by PyInstaller.
```

- [ ] **Step 3: End-to-end smoke test (requires API layer plan to be complete)**

Start the daemon:
```bash
cd /c/vibecode/reticulumnewsnet && python newsnet_main.py
```

Open browser to `http://localhost:8765`. Expected:
- Token entry screen appears
- Enter token from wizard output
- Groups sidebar loads (may be empty on fresh node)
- Status bar shows "Up to date"
- Peers page accessible
- Settings page shows identity hash and token

- [ ] **Step 4: Test PWA install on mobile**

On a phone connected to the same WiFi:
1. Open `http://<your-machine-ip>:8765` in browser
2. Android Chrome: tap "Add to Home Screen" in menu
3. iOS Safari: tap Share → "Add to Home Screen"
4. App should open full-screen from home screen icon

- [ ] **Step 5: Commit**

```bash
cd /c/vibecode/reticulumnewsnet
/c/vibecode/rtk.exe git add frontend/build.sh pyproject.toml
/c/vibecode/rtk.exe git commit -m "chore: add frontend build script and integration notes"
```

---

## Final Verification

- [ ] **Full frontend build passes**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npm run build
```

- [ ] **TypeScript has no errors**

```bash
cd /c/vibecode/reticulumnewsnet/frontend && npx tsc --noEmit
```

- [ ] **`frontend/dist/` is non-empty**

```bash
ls /c/vibecode/reticulumnewsnet/frontend/dist/
```

Expected: `index.html`, `manifest.json`, `sw.js`, and asset bundles.

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

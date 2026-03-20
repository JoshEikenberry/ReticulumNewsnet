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

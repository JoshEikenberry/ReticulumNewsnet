export interface Article {
  message_id: string;
  newsgroup: string;
  subject: string;
  body: string;
  author_hash: string;
  author_words: string;
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
  identity_words: string;
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

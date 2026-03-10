# TCP Peer Auto-Retry — Design

## Overview

Automatically retry failed TCP peer connections on each sync loop iteration.
Track consecutive failure counts in memory. Show failure counts in the TUI
peer list, and raise a notification when a peer exceeds 5 consecutive failures.

## Decisions

- **Retry strategy:** Always retry, never stop. Hubs are intentionally added
  and may come back.
- **Failure tracking:** In-memory only. Resets on app restart.
- **Retry location:** Inside the existing sync loop, before syncing.
- **TUI behavior:** Show consecutive failure count per peer. Notify at 5
  failures. Keep showing count above 5.

## PeerManager Changes

- Add `_fail_counts: dict[str, int]` — normalized address to consecutive
  failure count.
- `connect()` increments `_fail_counts[addr]` on failure, resets to 0 on
  success.
- New `retry_disconnected()` method — iterates `list_peers()`, calls
  `connect()` for any peer not currently in `_interfaces`.
- New `fail_count(address)` method — returns current failure count.

## Node Changes

- `_periodic_sync_loop`: call `self._peer_mgr.retry_disconnected()` before
  `sync_all_peers()`.
- `list_tcp_peers()`: include `fail_count` in returned dicts.

## TUI Changes

- Peer table: add "Failures" column (shows count when > 0, empty when
  connected).
- When loading peers, if any peer's `fail_count` crosses 5, show a
  notification warning.

## CLI Changes

- `peer list`: show failure count column when > 0.

## What Doesn't Change

- `peers.txt` format — no persistence of failure state.
- Retry cadence — same as sync interval, no backoff.
- Never auto-remove a peer.

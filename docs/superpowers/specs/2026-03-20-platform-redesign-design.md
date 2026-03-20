# ReticulumNewsnet Platform Redesign
**Date:** 2026-03-20
**Status:** Approved

## Overview

Evolve ReticulumNewsnet from a Python TUI-only application into a cross-platform system accessible on Windows, Linux, macOS, Android, and iOS devices. The existing `newsnet/` core library remains unchanged. New work is additive: an HTTP/WebSocket API layer, a Svelte-based Progressive Web App frontend, an extensible interface configuration system, and a first-run setup wizard.

The Python daemon is the only component that touches Reticulum. All clients (browser, TUI, CLI) communicate with the daemon via a local API.

---

## Goals

- **Cross-platform access**: Any device with a browser can connect to a user's node
- **Non-technical users**: Minimal jargon, opinionated defaults, guided first-run experience
- **Pull model as a security guarantee**: Nodes only receive articles they explicitly request — no peer can push unsolicited data
- **Extensible interface config**: Architecture supports future RNS interface types (LoRa, I2P, serial) without restructuring
- **Preserve existing clients**: TUI and CLI remain fully functional

---

## Non-Goals

- Native iOS or Android apps (PWA covers mobile sufficiently)
- Reticulum propagation node support (deferred — pull model is preferred for DDoS safety)
- LoRa/RNode implementation (deferred — requires hardware to test)
- Nomad Network compatibility (kept fully independent)
- Multi-user daemon (single-user personal node)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  newsnet binary                      │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │          newsnet/ core (unchanged)           │    │
│  │  Node · SyncEngine · Store · Filters        │    │
│  │  Article · Identity · Config · PeerManager  │    │
│  └────────────────────┬────────────────────────┘    │
│                        │                             │
│  ┌─────────────────────▼────────────────────────┐   │
│  │                 api/ (new)                   │   │
│  │   FastAPI app · REST routes · WebSocket hub  │   │
│  │   Serves compiled Svelte frontend as static  │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │  cli/ (keep) │  │  tui/ (keep)                 │  │
│  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
         ↕ HTTP/WebSocket (local or over network)
┌─────────────────────┐    ┌──────────────────────────┐
│  Browser on desktop │    │  Phone/tablet browser    │
│  (same machine)     │    │  (local WiFi or remote)  │
└─────────────────────┘    └──────────────────────────┘
```

- FastAPI runs in the same process as the daemon — no separate server to manage
- The compiled Svelte frontend (`frontend/dist/`) is bundled into the PyInstaller binary and served as static files
- The daemon binds to `localhost` by default; optionally exposed on LAN/internet via config
- TUI and CLI remain as first-class clients for power users

---

## Components

### 1. `api/` — FastAPI Layer (new)

Wraps the existing `Node` object. Two communication patterns:

**REST endpoints:**
```
GET    /api/groups                     list newsgroups
GET    /api/articles?group=&after=     list articles (paginated)
GET    /api/articles/{message_id}      single article + thread
POST   /api/articles                   post new article
GET    /api/peers                      list peers (RNS + TCP)
POST   /api/peers                      add TCP peer
DELETE /api/peers/{address}            remove TCP peer
POST   /api/sync                       trigger manual sync
GET    /api/filters                    list filters
POST   /api/filters                    add filter
DELETE /api/filters/{id}               remove filter
GET    /api/identity                   identity hash + display name (see response shape below)
GET    /api/config                     current config
PATCH  /api/config                     update config (see patchable fields below)
```

**`GET /api/identity` response shape:**
```json
{
  "identity_hash": "a3f9d2c1...",
  "display_name": "alice",
  "tcp_address": "192.168.1.50:8765"
}
```
`identity_hash` is the hex-encoded RNS identity hash (used for author attribution and filtering). `tcp_address` is the local machine's LAN IP + configured port — what users share with friends for TCP peering. If the daemon is bound to `localhost` only, `tcp_address` is omitted (null) and the UI shows a note explaining remote peering requires `api_host` to be set.

**WebSocket at `/ws`:**
```
Server → Client events:
  { type: "new_article",    article: {...}        }
  { type: "peer_found",     peer: {...}           }
  { type: "peer_lost",      destination_hash: "" }
  { type: "sync_started",   peer: "..."          }
  { type: "sync_done",      count: N             }
  { type: "node_ready"                           }
```
`peer_lost` is emitted when a TCP peer disconnects or fails. `node_ready` is emitted once after startup when the Node and RNS are fully initialized (see Startup Sequencing).

**Auth:** Single shared Bearer token, auto-generated (UUID4) on first launch and stored in `config.toml` as `api_token`. Never user-chosen. Displayed in the terminal wizard completion screen and on the web UI settings page so users can retrieve it if lost. Clients send it as `Authorization: Bearer <token>` on all REST requests.

WebSocket auth: token passed as `?token=<value>` query parameter on the initial HTTP upgrade request. The token is validated before the upgrade completes. On auth failure: HTTP 401 is returned and the upgrade is rejected (connection never becomes a WebSocket). Already-connected WebSocket sessions are not affected by token rotation — they remain valid for their lifetime. Rotating the token requires a daemon restart.

Missing or invalid token on REST routes → HTTP 401 `{ "error": "unauthorized" }`.

---

### 2. `frontend/` — Svelte PWA (new)

A standard Svelte project. Builds to `frontend/dist/` which is bundled into the binary.

**Screen layout:**
```
┌──────────────────────────────────────────────────┐
│  ☰  ReticulumNewsnet   [● syncing...]  [⚙ config]│
├───────────────┬──────────────────────────────────┤
│ GROUPS        │  tech.linux                      │
│               │  ─────────────────────────────── │
│ tech.linux  5 │  ▶ Help with kernel params   [2] │
│ net.mesh    2 │    └─ Re: Help with kernel   [1] │
│ local.chat 12 │  ▶ New RNS release announced  [0]│
│               │  ▶ Setting up a LoRa node     [5]│
│ [+ new group] │    └─ Re: LoRa node setup     [2]│
│               │       └─ Got it working!      [0]│
│ PEERS      3● │                                  │
│ FILTERS       │  [+ compose]                     │
└───────────────┴──────────────────────────────────┘
```

**UX principles for non-technical users:**
- Plain language everywhere — no jargon in primary UI. "Your address" not "identity hash". "Connected neighbors" not "RNS peers". Technical details available on hover/detail views for power users.
- Status bar in human terms: "Up to date" / "Syncing with 2 neighbors..." / "Offline"
- Compose is prominent — large button, simple form (group, subject, body). Group auto-completes from known groups.
- Threaded view uses visual indentation — no graph theory required
- Mobile-responsive: sidebar collapses to bottom nav on small screens

**PWA specifics:**
- `manifest.json` with name, icon, theme color — installable on Android and iOS home screens
- Service worker uses a **cache-first strategy for the app shell only** (HTML, JS, CSS bundles) and **network-first for all `/api/*` routes** — live data always comes from the daemon, never from cache. The specific service worker implementation (workbox vs. hand-written) is deferred to implementation.
- Works on Android Chrome, iOS Safari, Firefox, Edge

---

### 3. First-Run Setup Wizard

Runs on first launch only. Re-configuration through web UI settings or `config.toml` directly.

```
Welcome to ReticulumNewsnet!
════════════════════════════
Let's get you set up. This will only take a minute.

Step 1 of 3 — What should we call you?
Your display name is shown alongside your posts.
It can be anything you like.

  Display name: _

────────────────────────────────────────────────────
Step 2 of 3 — Where should your data be stored?
We'll save your articles, identity, and settings here.

  [✓] Use default location (~/.config/reticulum-newsnet/)
  [ ] Choose a different location

────────────────────────────────────────────────────
Step 3 of 3 — Connect to a friend's node (optional)
If someone you know is already running Newsnet, ask them
for their node address (looks like: 192.168.1.x:4965)
and enter it here to start syncing right away.

On the same WiFi? Skip this — you'll find each other
automatically.

  Node address (or press Enter to skip): _

────────────────────────────────────────────────────
All done! Starting your node...

  Node address:  192.168.1.50:8765  (share with friends to connect)
  Web interface: http://localhost:8080
  Access token:  a7f2c9d1-...  (saved to config — shown on Settings page)

  Open in browser? [Y/n]
```

**Bootstrapping note:** The wizard runs in the terminal on first launch on all platforms, including Windows. This is intentional — the daemon must be running before the web UI is accessible. A non-technical Windows user will see this terminal wizard once, then use the browser UI for everything thereafter. Future work may provide a GUI installer wrapper, but that is out of scope for this spec.

**Principles:**
- 3 steps maximum
- Every step has a sensible default — user can press Enter through entirely
- No networking jargon in wizard copy
- "Node address" shown is the machine's local IP + configured port — what to share with friends for TCP peering
- Auth token is auto-generated, displayed once here, and always accessible on the Settings page
- Immediately offers to open the browser on completion

---

### 4. Addressing — Three Concepts Clearly Separated

The UI uses plain language to distinguish three distinct concepts:

| Technical term       | UI label             | Purpose                                              |
|----------------------|----------------------|------------------------------------------------------|
| Identity hash        | "Your identity"      | Cryptographic author ID; signs every post you write |
| Destination hash     | (internal only)      | How the RNS mesh routes to your node; auto-managed  |
| TCP peer address     | "Node address"       | IP:port shared with friends for internet peering    |

On a local network, nodes auto-discover each other via RNS announces — no address exchange needed. TCP peer addresses are only needed for internet peering. Identity hashes are never manually exchanged; they are displayed on the profile/settings page for reference.

---

### 5. Extensible Interface Configuration

`config.toml` supports `[[interface]]` blocks structured to accommodate future RNS interface types:

```toml
[[interface]]
type = "tcp"
host = "somehost.example.com"
port = 4965

# Future (not yet implemented):
# [[interface]]
# type = "rnode"
# port = "/dev/ttyUSB0"
# frequency = 868000000
```

Only TCP is implemented and exposed in the UI. LoRa/RNode support is deferred until hardware testing is available.

**Patchable config fields via `PATCH /api/config`:**

Fields that take effect immediately (no restart):
- `display_name` (string, non-empty)
- `retention_hours` (integer, 1–720; out-of-range → 422 with `{ "error": "retention_hours must be between 1 and 720" }`)
- `sync_interval_minutes` (integer, ≥1)
- `strict_filtering` (boolean)

Fields that require a daemon restart (stored immediately but not applied until restart):
- `api_host` (string — bind address, e.g. `0.0.0.0` to expose on LAN)
- `api_port` (integer, 1–65535)

For restart-required fields, the response is HTTP 200 with body `{ "restart_required": true, "changed": ["api_host"] }`. The value is written to `config.toml` immediately so it persists on restart. The client displays a "Restart required to apply changes" notice.

Invalid field types → HTTP 422 with `{ "error": "<field> must be <type>" }`.
Unknown fields → HTTP 422 with `{ "error": "unknown field: <name>" }`.

`[[interface]]` blocks are **not** patchable via the API — they require direct `config.toml` editing and a daemon restart.

---

## API Startup Sequencing

FastAPI starts immediately when the binary launches and accepts connections before `Node` is fully initialized. This prevents timeout errors on slow hardware (e.g., Raspberry Pi).

States:
```
STARTING  → RNS and Node not yet ready
            /api/* routes return HTTP 503 { "error": "starting up" }
            /ws accepts connections and queues events (does NOT return 503)
            Auth is still enforced on /ws during STARTING
READY     → Node initialized, RNS connected
            All /api/* routes functional
            /ws emits { type: "node_ready" } to all connected clients
```

`/ws` is explicitly excluded from the 503 rule so clients can connect early and receive `node_ready` as soon as the daemon is ready, without polling. The frontend displays a "Starting up..." banner until `node_ready` arrives or until a `/api/*` route returns non-503.

---

## Pull Model Security Guarantee

Nodes ONLY receive articles they explicitly request. No peer can push unsolicited data. Sync is always initiated outbound by the local node on its own schedule (`sync_interval_minutes` or manual trigger).

**Transport-level clarification:** The local node opens RNS Links in two modes:
- **Initiator** (outbound): local node opens the link, initiates the ID-list exchange, and requests specific articles. All `RNS.Resource` transfers are received in response to an explicit `ArticleRequestMessage` sent by the local node first.
- **Responder** (inbound): the local node accepts inbound links from peers who initiate sync. In responder mode, the local node still controls what it requests — it receives the peer's ID list, computes what it's missing, and sends its own `ArticleRequestMessage`. The peer cannot send article data that was not requested.

In both modes, `Store.store_article()` is only called after `SyncEngine.process_received_article()` validates the article against a locally-generated request. No code path writes to the store from unsolicited inbound data.

**Mechanism:** `SyncSession` maintains a `_requested_ids: set[str]` field. An article ID is added to this set only when the local node sends an `ArticleRequestMessage` containing that ID. `process_received_article()` checks `message_id in _requested_ids` before calling `store_article()`. Articles arriving outside of this set are discarded and logged as a protocol violation. The set is scoped to the session lifetime and discarded on teardown.

This guarantee has an explicit test (`test_pull_guarantee.py`): construct a `SyncSession` in responder mode, inject an `ArticleDataMessage` without a prior `ArticleRequestMessage` from the local side, and assert `store_article()` is never called.

---

## Testing Strategy

**Existing tests (unchanged):**
`test_article.py`, `test_store.py`, `test_sync.py`, `test_sync_engine.py`, `test_sync_session.py`, `test_peers.py`, `test_filters.py`, `test_identity.py`, `test_config.py`, `test_node.py`, `test_cli.py`, `test_tui.py`

**New tests:**
- `test_api.py` — FastAPI REST endpoints via `TestClient` with mock `Node`
- `test_api_websocket.py` — WebSocket event delivery
- `test_setup_wizard.py` — First-run wizard flow, default values, skip behavior
- `test_pull_guarantee.py` — Assert no unsolicited writes to store

Frontend component tests (Svelte/Vitest) are optional and low priority for initial implementation.

---

## Future Features (out of scope for this spec)

### Human-Readable Identity Words

Identity hashes displayed as a deterministic sequence of human-readable words derived from the hash — similar to What3Words or BIP-39 mnemonic phrases.

```
Input:        The first 4 bytes of SHA-256(identity.get_public_key())
              (the full 32-byte Ed25519 public key, not the truncated
               RNS destination hash or display hash)
Display form: "Apple·Bark·City"  (derived deterministically, never changes)
```

Implementation: a pure `hash_to_words(public_key_bytes) -> str` display transform. Input is always `identity.get_public_key()` (32 bytes, Ed25519 public key). Zero changes to crypto, storage, or sync protocol.

Recommended wordlist: EFF large wordlist (7776 words = 12.9 bits/word).

Derivation (3 words):
```
digest = SHA-256(public_key_bytes)   # 32 bytes
# Need ceil(3 * log2(7776)) = ceil(38.7) = 39 bits minimum → use first 5 bytes (40 bits)
n = int.from_bytes(digest[:5], "big")  # 40-bit integer
w3 = n % 7776;          n //= 7776
w2 = n % 7776;          n //= 7776
w1 = n % 7776
words = [wordlist[w1], wordlist[w2], wordlist[w3]]
```
- 3 words → ~38.7 bits → ~1 in 450 billion collision chance (sufficient for most networks)
- 4 words → use first 7 bytes (56 bits) → ~51.6 bits → ~1 in 3.7 quadrillion (if extra comfort desired)

Words serve as a human-readable backup identity label when no display name is set.

### Network Stress Testing

A dedicated stress-testing tool to measure:
- Maximum node count before resource constraints
- Maximum article throughput per node
- Sync latency under load
- Memory and CPU profiles at scale

Goal: identify bottlenecks and set documented throughput targets for the network.

### LoRa / RNode Interface Support

Requires physical RNode hardware (flashed LoRa radio). Deferred until hardware is available for testing. The extensible `[[interface]]` config block is already designed to accommodate this without architectural changes.

---

## Distribution

- Single binary per platform via PyInstaller (existing approach)
- Binary includes: Python runtime, all dependencies, compiled Svelte frontend
- Platforms: Windows (x64), Linux (x64, ARM), macOS (x64, ARM)
- Android/iOS: accessed via browser connecting to a node running on another machine
- macOS is a supported daemon platform despite not being listed in the primary goal (Windows, Linux, Android, iOS). It is included in distribution because PyInstaller supports it and the user base may run macOS servers.

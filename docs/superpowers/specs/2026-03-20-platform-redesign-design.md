# ReticulumNewsnet Platform Redesign
**Date:** 2026-03-20
**Status:** Approved

## Overview

Evolve ReticulumNewsnet from a Python TUI-only application into a cross-platform system accessible on Windows, Linux, Android, and iOS devices. The existing `newsnet/` core library remains unchanged. New work is additive: an HTTP/WebSocket API layer, a Svelte-based Progressive Web App frontend, an extensible interface configuration system, and a first-run setup wizard.

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
GET    /api/identity                   identity hash + display name
GET    /api/config                     current config
PATCH  /api/config                     update config
```

**WebSocket at `/ws`:**
```
Server → Client events:
  { type: "new_article",  article: {...} }
  { type: "peer_found",   peer: {...}    }
  { type: "sync_started", peer: "..."   }
  { type: "sync_done",    count: N      }
```

**Auth:** Single shared Bearer token set during first-run wizard, stored in `config.toml`. Not multi-user — this is a personal node.

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
- Service worker caches the app shell for instant load
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

  Your address: a3f9d2...  (share this so others can find you)
  Web interface: http://localhost:8080
  Open in browser? [Y/n]
```

**Principles:**
- 3 steps maximum
- Every step has a sensible default — user can press Enter through entirely
- No networking jargon in wizard copy
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

---

## Pull Model Security Guarantee

Nodes ONLY receive articles they explicitly request. No peer can push unsolicited data. Sync is always initiated outbound by the local node on its own schedule (`sync_interval_minutes` or manual trigger).

This prevents any single overwhelmed or malicious node from flooding its peers — there is no mechanism by which a remote node can cause the local node to write to its store without a local request.

This guarantee has an explicit test: assert that no article is ever written to the store without the local node having requested it.

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
Identity hash: a3f9d2c1... (256 bits, cryptographic)
Display form:  "Apple·Bark·City"  (derived, never changes)
```

Implementation: a pure `hash_to_words(identity_hash)` display transform. Zero changes to crypto, storage, or sync protocol.

Recommended wordlist: EFF large wordlist (~7776 words, 12.9 bits/word).
- 3 words ≈ 38 bits → ~1 in 274 billion collision chance (sufficient for most networks)
- 4 words ≈ 51 bits → ~1 in 2.25 quadrillion (if extra comfort desired)

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

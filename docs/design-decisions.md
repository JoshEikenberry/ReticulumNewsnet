# Reticulum-Newsnet: Design Decisions Log

## Project Overview

Reticulum-newsnet is a Usenet-inspired federated discussion system built on the
Reticulum Network Stack. It combines the threaded newsgroup model of NNTP/Usenet
with the cryptographic identity and decentralized transport of Reticulum.

The project is written in Python to stay compatible with the Reticulum ecosystem.
Target platform is Linux to start.

## Decisions

### 1. Network Model: Full Peer-to-Peer

Every running instance of reticulum-newsnet is both client and server. There are
no dedicated servers or infrastructure nodes. Messages propagate organically
between peers.

**Rationale:** Decentralization is a core project value. Leveraging Reticulum's
native P2P capabilities avoids introducing central points of failure or requiring
anyone to run dedicated infrastructure.

### 2. Scope: Usenet Clone First, Real-Time Chat Later

The initial focus is on the asynchronous threaded discussion model (like Usenet),
not real-time chat (like IRC). Real-time chat may be explored in a future
iteration.

**Rationale:** Several IRC-like solutions already exist in the Reticulum
ecosystem (MeshChat, RRC, Nomad Network). The Usenet-style threaded discussion
model is the distinctive contribution of this project.

### 3. Peer Discovery: Announce-Based

Peers discover each other automatically using Reticulum's native announce
mechanism. Each node announces itself as a reticulum-newsnet peer on the network.
When nodes discover each other, they establish links and sync articles.

**Rationale:** Leverages existing Reticulum features rather than building custom
discovery. Requires zero configuration from users - peers just find each other.

### 4. Article Sync: Recent-Window

Peers sync articles within a configurable time window (1 hour to 30 days). Only
articles within the window are exchanged during sync. Delivery is best-effort.

**Rationale:** Keeps sync lightweight, especially on bandwidth-constrained links
(e.g. LoRa). Bloom filter-based sync may be added later as an optimization, so
the sync interface should be kept clean and abstract to allow for this.

### 5. Retention: Same as Sync Window

A single setting controls both the sync window and local retention. Articles
older than the configured window are deleted locally and not propagated to peers.

**Rationale:** Simplicity. Posts are intended to be somewhat ephemeral. This
avoids encouraging unbounded storage growth and keeps the system lightweight.

### 6. Article Format: Plain Unicode Text Only

Articles contain:
- Author identity (Reticulum Identity hash, cryptographically verifiable)
- Display name (human-readable, chosen by the author)
- Newsgroup (single group, dotted naming convention)
- Subject line
- Message-ID (unique hash derived from content + author identity)
- References (list of parent message IDs for threading)
- Timestamp
- Body (plain unicode text)

No attachments, no markdown, no formatting. Plain unicode text is an explicit
design feature, not a limitation.

**Rationale:** Keeps things simple, bandwidth-friendly, and aligned with the
Reticulum ethos. Full unicode support provides expressive range without the
complexity of rich formatting.

### 7. No Cross-Posting

An article belongs to exactly one newsgroup. Cross-posting to multiple groups
is not supported.

**Rationale:** Departure from Usenet. Cross-posting was one of Usenet's more
abused features and adds complexity to sync and deduplication.

### 8. Cryptographic Signing: Mandatory

Every article must be signed with the author's Reticulum cryptographic identity.
No unsigned or anonymous posts are allowed.

**Rationale:** Reticulum's built-in cryptographic identity system makes this
essentially free. Mandatory signing enables trustworthy author verification,
reliable blacklisting (based on cryptographic identity rather than spoofable
display names), and tamper detection.

### 9. Newsgroup Naming: Dotted Convention, Freeform

Newsgroup names use a dotted hierarchy syntax (e.g. `tech.linux.kernel`,
`music.jazz.miles-davis`) but the hierarchy is not enforced. Any dotted name
is valid. There is no formal namespace governance.

**Rationale:** The dotted syntax provides visual structure and convention without
enforcing a rigid taxonomy. Users can organize groups however they see fit.

### 10. Newsgroup Creation: Post-to-Create

A newsgroup comes into existence the moment someone posts an article to it. There
is no separate creation step, no voting process, no announcement protocol.

**Rationale:** Simplicity and freedom. A newsgroup is just a label that articles
carry. The set of "known groups" on a node is whatever group names have been seen
in received articles.

### 11. Moderation: Local Filtering

There is no network-level moderation. Each user controls their own experience
through local whitelist/blacklist rules covering:
- Words (content filtering)
- Authors (by cryptographic identity)
- Newsgroups (by name)

**Rationale:** Consistent with the decentralized, no-authority philosophy. Users
have full sovereignty over what they see without imposing restrictions on others.

### 12. Storage: SQLite

All article data is stored in a single SQLite database.

**Rationale:** Zero additional dependencies (part of Python's stdlib), natural
fit for structured article data, easy retention management
(`DELETE WHERE timestamp < cutoff`), fast threading and search queries, simple
backup (single file).

### 13. User Interface: CLI + TUI Hybrid

A terminal UI (curses-based) for interactive browsing and reading, combined with
CLI commands for scripting and automation. A web UI may be added as a separate
frontend in a future iteration.

**Rationale:** Minimal dependencies, fits the Reticulum ecosystem aesthetic,
runs in any terminal. CLI commands make the tool scriptable and composable.
The core is designed as a library/daemon so alternative frontends (web, GUI)
can be added later without rewriting the backend.

### 14. Web UI: Future Possibility

Reticulum works well with web applications. The established pattern in the
ecosystem (used by MeshChat and others) is a Python backend bridging Reticulum
to a local WebSocket/HTTP server, with the browser connecting to localhost.
This remains a viable future frontend option.

## Open Questions

- Detailed sync protocol design (handshake, ID exchange, article transfer)
- Article size limits
- Configuration file format and location
- TUI layout and keybindings
- CLI command structure
- Package distribution strategy

# Reticulum-Newsnet: Design Document

## Overview

Reticulum-newsnet is a Usenet-inspired, fully peer-to-peer threaded discussion
system built on the Reticulum Network Stack. Every running instance is both
client and server. There are no dedicated infrastructure nodes.

Articles are plain unicode text, cryptographically signed with the author's
Reticulum Identity, and propagated between peers using Reticulum's native
announce-based discovery. Moderation is handled locally through per-user
filtering, and the network self-moderates through the aggregate filtering
behavior of individual nodes.

Written in Python. Linux-first.

## Architecture

The system follows a library-core pattern. All protocol logic, storage, sync,
and filtering live in the `newsnet` library. Frontends (CLI, TUI, and
potentially a web UI in the future) are thin wrappers that import the library.

```
┌────────────────────────────────────────┐
│            newsnet library             │
│                                        │
│  ┌──────────┐ ┌────────┐ ┌─────────┐  │
│  │Reticulum │ │  Sync  │ │ SQLite  │  │
│  │Integration│ │ Engine │ │  Store  │  │
│  └──────────┘ └────────┘ └─────────┘  │
│  ┌──────────┐ ┌────────────────────┐   │
│  │ Filtering│ │  Article Manager   │   │
│  └──────────┘ └────────────────────┘   │
└──────────┬──────────────────┬──────────┘
           │                  │
    ┌──────▼──────┐    ┌──────▼──────┐
    │  CLI runner │    │  TUI runner │
    └─────────────┘    └─────────────┘
```

Third parties can build their own frontends by importing the library.

## Project Structure

```
reticulum-newsnet/
├── newsnet/                  # Core library
│   ├── __init__.py
│   ├── identity.py           # Identity management (create, load, persist)
│   ├── article.py            # Article model (create, sign, verify, serialize)
│   ├── store.py              # SQLite storage (CRUD, retention, queries)
│   ├── sync.py               # Sync engine (peer discovery, article exchange)
│   ├── filters.py            # Whitelist/blacklist filtering
│   ├── node.py               # Top-level orchestrator (wires everything together)
│   └── config.py             # Configuration loading and defaults
├── cli/
│   ├── __init__.py
│   └── main.py               # CLI commands (post, list, read, sync, etc.)
├── tui/
│   ├── __init__.py
│   └── app.py                # Curses-based interactive reader
├── config.example.toml       # Example configuration file
├── pyproject.toml             # Package metadata and dependencies
└── docs/
    ├── design-decisions.md
    └── plans/
        └── 2026-03-03-reticulum-newsnet-design.md  (this file)
```

## Data Model

All data is stored in a single SQLite database at
`~/.config/reticulum-newsnet/newsnet.db`.

### articles

| Column       | Type | Notes                                                    |
|--------------|------|----------------------------------------------------------|
| message_id   | TEXT | PRIMARY KEY. SHA-256 hash of canonical article form.     |
| author_hash  | TEXT | NOT NULL. Reticulum Identity hash of the author.         |
| author_key   | BLOB | NOT NULL. Author's public key for standalone verification.|
| display_name | TEXT | NOT NULL. Human-readable name chosen by the author.      |
| newsgroup    | TEXT | NOT NULL. Single dotted-hierarchy name.                  |
| subject      | TEXT | NOT NULL.                                                |
| body         | TEXT | NOT NULL. Plain unicode text.                            |
| references   | TEXT | JSON array of parent message_ids for threading.          |
| timestamp    | REAL | NOT NULL. Unix timestamp set by author.                  |
| signature    | BLOB | NOT NULL. Reticulum Identity signature over message_id.  |
| received_at  | REAL | NOT NULL. When this node received the article.           |

### peers

| Column           | Type | Notes                                      |
|------------------|------|--------------------------------------------|
| destination_hash | TEXT | PRIMARY KEY. Reticulum destination hash.   |
| display_name     | TEXT | Peer's announced name, if any.             |
| first_seen       | REAL | NOT NULL.                                  |
| last_seen        | REAL | NOT NULL.                                  |
| last_synced      | REAL | Last successful sync timestamp.            |

### filters

| Column      | Type    | Notes                                            |
|-------------|---------|--------------------------------------------------|
| id          | INTEGER | PRIMARY KEY AUTOINCREMENT.                       |
| filter_type | TEXT    | NOT NULL. "word", "author", or "newsgroup".      |
| filter_mode | TEXT    | NOT NULL. "whitelist" or "blacklist".             |
| pattern     | TEXT    | NOT NULL. Value or glob pattern (for newsgroups).|
| created_at  | REAL    | NOT NULL.                                        |

### tombstones

| Column     | Type | Notes                                               |
|------------|------|-----------------------------------------------------|
| message_id | TEXT | PRIMARY KEY. ID of a filtered/discarded article.    |
| created_at | REAL | NOT NULL. When it was filtered.                     |

Tombstones prevent re-requesting articles that were already received and
discarded by filters. They are pruned on the same retention schedule as articles.

## Article Format

### Fields

- **message_id**: SHA-256 hash of the canonical form (see below)
- **author_hash**: Reticulum Identity hash of the author
- **author_key**: Author's full public key (for standalone verification)
- **display_name**: Human-readable author name
- **newsgroup**: Single dotted-hierarchy group name (e.g. `tech.linux.kernel`)
- **subject**: Subject line
- **body**: Plain unicode text (no markdown, no attachments, no formatting)
- **references**: JSON array of parent message_ids (for threading)
- **timestamp**: Unix timestamp (float), set by the author
- **signature**: Reticulum Identity signature over the message_id

### Constraints

- One newsgroup per article (no cross-posting)
- Body is plain unicode text only
- Every article must be signed

### Canonical Form and Signing

The message_id is derived from a canonical byte string to ensure consistent
hashing across nodes:

```
canonical = newsgroup + "\n" + subject + "\n" + body + "\n" + author_hash + "\n" + str(timestamp)
message_id = SHA-256(canonical.encode("utf-8"))
```

The author signs the message_id with their Reticulum Identity private key.

Verification on receipt:
1. Recompute message_id from the article fields
2. Verify the recomputed message_id matches the one in the article
3. Verify the signature against the author's public key
4. If either check fails, discard the article

### Serialization

Articles are serialized using msgpack for compact wire representation. The
serialized form includes all fields plus the author's public key, making each
article self-contained and independently verifiable.

## Newsgroup Model

- Names use dotted-hierarchy syntax (e.g. `music.jazz.miles-davis`)
- The hierarchy is convention only, not enforced
- Any valid dotted string is a valid newsgroup name
- A newsgroup comes into existence when someone posts to it (post-to-create)
- The set of "known groups" on a node is the set of distinct newsgroup values
  in its articles table

## Sync Protocol

### Peer Discovery

Each node creates a Reticulum Destination with app name `newsnet.peer` and
announces it on the network. Nodes register an announce handler filtered to
`newsnet.peer` to discover other nodes.

When a new peer is discovered, its destination hash is recorded in the peers
table.

### Sync Handshake

Sync is periodic (configurable, default 15 minutes) and also triggered
immediately when a new peer is discovered.

```
Node A                          Node B
  |                               |
  |---- Establish Link ---------->|
  |                               |
  |---- My article IDs --------->|
  |<--- Your article IDs --------|
  |                               |
  |---- Request [id1, id2...] -->|
  |<--- Request [id5, id8...] ---|
  |                               |
  |<--- Articles [id1, id2...] --|
  |---- Articles [id5, id8...] ->|
  |                               |
  |---- Teardown --------------->|
  |                               |
```

1. **Establish Link**: Initiating node opens a Reticulum Link to the peer
2. **Exchange article IDs**: Both sides send a list of `(message_id, timestamp)`
   tuples for articles within the retention window, using a custom Channel
   message type
3. **Request missing articles**: Each side identifies IDs the other has that it
   lacks (excluding tombstoned IDs) and requests them
4. **Transfer articles**: Requested articles are sent as serialized msgpack blobs
5. **Verify and filter**: Each received article is verified (signature check),
   run through local filters, and either stored or tombstoned
6. **Teardown**: Link is closed, `last_synced` updated in peers table

### Future Optimization

The sync interface will be designed with a `SyncStrategy` abstraction so that
the ID-list exchange (step 2) can be replaced with bloom filters in a future
iteration without changing the rest of the protocol.

### Sync Window

Only articles within the retention window are exchanged. The retention window
is configurable from 1 hour to 30 days (default: 7 days). This single setting
controls both sync scope and local retention. Articles and tombstones older than
the window are deleted.

## Identity Management

### Node Identity

Each node has a persistent Reticulum Identity stored at
`~/.config/reticulum-newsnet/identity`.

On first run:
1. Generate a new Reticulum Identity
2. Save it to the identity file
3. Create the `newsnet.peer` Destination
4. Begin announcing on the network

### Display Name

Set in `config.toml`. Included in articles for human readability but never
trusted for filtering. All author-based filtering uses the cryptographic
identity hash.

### Article Signing Flow

```
Author composes article
         |
         v
Assemble canonical form
         |
         v
Generate message_id = SHA-256(canonical)
         |
         v
Sign message_id with Reticulum Identity private key
         |
         v
Attach signature and public key to article
```

### Verification Flow (on receipt from peer)

```
Receive article
       |
       v
Recompute message_id from article fields
       |
       v
Check recomputed message_id matches sent message_id
       |
       v
Verify signature against author's public key
       |
       v
Apply local filters
       |
       v
Store article  --or--  Discard and tombstone
```

## Filtering System

### Principles

- Filtering is per-user and local
- No network-level moderation exists
- Filtered articles are discarded on receipt by default (strict filtering)
- Discarded articles are tombstoned to prevent re-requesting
- The network self-moderates through aggregate individual filtering: content
  that most nodes filter out naturally stops propagating

### Filter Types

| Filter    | Mode      | Effect                                                 |
|-----------|-----------|--------------------------------------------------------|
| Author    | Blacklist | Articles from this identity hash are discarded         |
| Author    | Whitelist | Only articles from these identity hashes are kept      |
| Newsgroup | Blacklist | Articles in matching groups are discarded              |
| Newsgroup | Whitelist | Only articles in matching groups are kept              |
| Word      | Blacklist | Articles containing this word (subject/body) discarded |
| Word      | Whitelist | Only articles containing a whitelisted word are kept   |

Newsgroup filters support glob patterns (e.g. `tech.*`).

### Evaluation Order

1. If any whitelist filters of a given type exist, only matching articles pass
2. Blacklist filters then remove from what remains
3. If no filters of a given type exist, everything passes

### Propagation Implications

Because filtered articles are discarded and never stored, they are also never
forwarded to other peers. A node only propagates content it hasn't filtered out.
This means widely-filtered content (spam, abuse) naturally dies off across the
network without any central authority.

## Configuration

File: `~/.config/reticulum-newsnet/config.toml`

```toml
# Identity & Display
display_name = "your_name_here"

# Retention & Sync
retention_hours = 168              # 7 days (valid: 1-720)
sync_interval_minutes = 15         # how often to sync with known peers

# Filtering
strict_filtering = true            # discard filtered articles on receipt
```

All files live under `~/.config/reticulum-newsnet/`:
- `config.toml` - user configuration
- `identity` - persistent Reticulum Identity
- `newsnet.db` - SQLite database

Reticulum's own configuration (`~/.reticulum/`) is not touched. The application
connects to whatever Reticulum instance is available or starts one with defaults.

## User Interface

### CLI Commands

```
newsnet post <newsgroup> --subject "Subject"    # compose and post an article
newsnet read <message_id>                       # read a specific article
newsnet list [newsgroup]                        # list articles, optionally in a group
newsnet groups                                  # list known newsgroups
newsnet sync                                    # trigger immediate sync with all peers
newsnet peers                                   # list known peers
newsnet filter add --blacklist --author <hash>  # add a filter rule
newsnet filter add --whitelist --group "tech.*" # add a filter rule
newsnet filter list                             # list active filters
newsnet filter remove <id>                      # remove a filter
newsnet identity                                # show your identity hash and display name
newsnet tui                                     # launch the interactive TUI
```

### TUI

Curses-based interactive interface for browsing and reading. Layout and
keybindings to be designed in a later iteration. The TUI imports the `newsnet`
library and provides an interactive wrapper around the same operations available
via CLI.

## Dependencies

- **Python 3.11+** (for stdlib TOML support)
- **rns** (Reticulum Network Stack)
- **msgpack** (article serialization)
- **curses** (TUI, stdlib)
- **sqlite3** (storage, stdlib)

Minimal external dependencies by design.

## Open Questions for Future Iterations

- Article size limits (may be constrained by Reticulum Resource transfer limits)
- TUI layout and keybinding design
- Bloom filter sync optimization
- Web UI frontend
- Package distribution (PyPI, system packages)
- Rate limiting during sync to avoid overwhelming constrained links
- Handling of very large peer networks (announce flooding)

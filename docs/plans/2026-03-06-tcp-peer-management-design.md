# TCP Peer Management — Design

## Overview

Add the ability for newsnet users to connect to remote Reticulum TCP hubs
from within the app. This enables peer discovery and article sync beyond the
local network, without requiring users to hand-edit the RNS config file.

## Approach: Runtime API (Option B)

Newsnet manages its own peer list and creates `TCPClientInterface` objects
programmatically via the RNS Python API. The RNS config file is never
touched.

## Scope

- **Client-only** — newsnet connects out to existing TCP servers/hubs.
  Server mode (accepting inbound connections) is a future enhancement.
- **CLI and TUI** interfaces for managing peers.
- **Dynamic connections** — adding a peer connects immediately; removing
  tears down the connection. Peers are also loaded at startup.

## Storage

- File: `peers.txt` in the newsnet config directory
  (`~/.config/reticulum-newsnet/peers.txt`)
- Format: one `host:port` entry per line
- Blank lines and `#` comment lines are ignored
- Port defaults to `4965` (RNS default) when omitted

Example:
```
# Community hub
hub.example.com:4242

# Friend's node
192.168.1.50
2001:db8::1:4965
```

## Connection Lifecycle

1. **Startup** — `Node.start()` reads `peers.txt`, creates a
   `TCPClientInterface` for each entry after `RNS.Reticulum()` initializes.
2. **Add peer** — validates address, appends to `peers.txt`, creates
   `TCPClientInterface` immediately.
3. **Remove peer** — removes from `peers.txt`, tears down the interface.
4. **Failure handling** — connection failures log a warning but do not block
   startup or crash the app. Retry logic is out of scope for v1.

## CLI Commands

```
newsnet peer add <address>       # add and connect
newsnet peer remove <address>    # disconnect and remove
newsnet peer list                # show peers and connection status
```

Address format: `host`, `host:port`, `[ipv6]:port`

## TUI

- New peers panel/screen showing TCP peers with connection status.
- Add and remove actions accessible from the TUI.

## Code Changes

| File | Change |
|------|--------|
| `newsnet/peers.py` | New — `PeerManager` class: read/write `peers.txt`, connect/disconnect via RNS API |
| `newsnet/node.py` | Instantiate `PeerManager`, call it on startup, expose add/remove/list |
| `cli/main.py` | Add `peer` subcommand with `add`, `remove`, `list` |
| `tui/app.py` | Add peers panel/screen with add/remove UI |

## Future Work

- TCP server mode (accept inbound connections)
- Auto-retry / reconnect on failure
- Other RNS interfaces: I2P, serial, LoRa (RNode)

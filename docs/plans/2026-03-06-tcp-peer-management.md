# TCP Peer Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users add/remove TCP hub addresses from within newsnet (CLI and TUI), with immediate connect/disconnect via the RNS runtime API.

**Architecture:** A new `PeerManager` class reads/writes `peers.txt` (one address per line) and creates/destroys `TCPClientInterface` objects against the running RNS instance. `Node` owns the `PeerManager` and exposes add/remove/list. CLI and TUI both delegate to `Node`.

**Tech Stack:** Python 3.11+, RNS (`TCPClientInterface`), Textual (TUI)

---

### Task 1: PeerManager — file I/O

**Files:**
- Create: `newsnet/peers.py`
- Create: `tests/test_peers.py`

**Step 1: Write failing tests for peers.txt read/write**

```python
# tests/test_peers.py
import pytest
from newsnet.peers import PeerManager


@pytest.fixture
def pm(tmp_path):
    return PeerManager(tmp_path)


def test_list_empty(pm):
    """No peers.txt file returns empty list."""
    assert pm.list_peers() == []


def test_add_and_list(pm):
    pm.add("hub.example.com:4242")
    assert pm.list_peers() == ["hub.example.com:4242"]


def test_add_default_port(pm):
    pm.add("hub.example.com")
    assert pm.list_peers() == ["hub.example.com:4965"]


def test_add_ipv6(pm):
    pm.add("[2001:db8::1]:4242")
    assert pm.list_peers() == ["[2001:db8::1]:4242"]


def test_add_ipv6_default_port(pm):
    pm.add("[2001:db8::1]")
    assert pm.list_peers() == ["[2001:db8::1]:4965"]


def test_add_duplicate_ignored(pm):
    pm.add("hub.example.com:4242")
    pm.add("hub.example.com:4242")
    assert pm.list_peers() == ["hub.example.com:4242"]


def test_remove(pm):
    pm.add("hub.example.com:4242")
    pm.add("other.host:1234")
    pm.remove("hub.example.com:4242")
    assert pm.list_peers() == ["other.host:1234"]


def test_remove_nonexistent(pm):
    pm.remove("nope:1234")  # should not raise


def test_comments_and_blanks_preserved(tmp_path):
    peers_file = tmp_path / "peers.txt"
    peers_file.write_text("# My hubs\nhub.example.com:4242\n\n# Another\nother:1234\n")
    pm = PeerManager(tmp_path)
    assert pm.list_peers() == ["hub.example.com:4242", "other:1234"]


def test_parse_address_valid():
    assert PeerManager.parse_address("host:1234") == ("host", 1234)
    assert PeerManager.parse_address("host") == ("host", 4965)
    assert PeerManager.parse_address("[::1]:4242") == ("::1", 4242)
    assert PeerManager.parse_address("[::1]") == ("::1", 4965)


def test_parse_address_invalid():
    with pytest.raises(ValueError):
        PeerManager.parse_address("")
    with pytest.raises(ValueError):
        PeerManager.parse_address("host:notaport")
    with pytest.raises(ValueError):
        PeerManager.parse_address("host:99999")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_peers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'newsnet.peers'`

**Step 3: Implement PeerManager file I/O**

```python
# newsnet/peers.py
"""Manage TCP peer addresses stored in peers.txt."""
from __future__ import annotations

from pathlib import Path

_DEFAULT_PORT = 4965
_FILENAME = "peers.txt"
_HEADER = "# TCP peer addresses (one per line: host:port)"


class PeerManager:
    def __init__(self, config_dir: Path):
        self._path = Path(config_dir) / _FILENAME

    @staticmethod
    def parse_address(address: str) -> tuple[str, int]:
        """Parse 'host:port', 'host', '[ipv6]:port', or '[ipv6]'.

        Returns (host, port). Raises ValueError on bad input.
        """
        addr = address.strip()
        if not addr:
            raise ValueError("Empty address")

        if addr.startswith("["):
            # IPv6: [host]:port or [host]
            bracket_end = addr.find("]")
            if bracket_end == -1:
                raise ValueError(f"Unclosed bracket in: {addr}")
            host = addr[1:bracket_end]
            rest = addr[bracket_end + 1:]
            if rest == "":
                return host, _DEFAULT_PORT
            if rest.startswith(":"):
                port_str = rest[1:]
            else:
                raise ValueError(f"Invalid IPv6 address format: {addr}")
        elif addr.count(":") == 1:
            host, port_str = addr.split(":", 1)
        else:
            # bare hostname or IPv4 without port
            return addr, _DEFAULT_PORT

        try:
            port = int(port_str)
        except ValueError:
            raise ValueError(f"Invalid port: {port_str}")
        if not (1 <= port <= 65535):
            raise ValueError(f"Port out of range: {port}")
        return host, port

    @staticmethod
    def normalize(address: str) -> str:
        """Normalize an address to 'host:port' or '[ipv6]:port' form."""
        host, port = PeerManager.parse_address(address)
        if ":" in host:
            return f"[{host}]:{port}"
        return f"{host}:{port}"

    def list_peers(self) -> list[str]:
        if not self._path.exists():
            return []
        results = []
        for line in self._path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            results.append(stripped)
        return results

    def add(self, address: str) -> str:
        """Add a peer. Returns the normalized address. No-op if duplicate."""
        normalized = self.normalize(address)
        existing = self.list_peers()
        if normalized in existing:
            return normalized
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(_HEADER + "\n")
        with open(self._path, "a") as f:
            f.write(normalized + "\n")
        return normalized

    def remove(self, address: str) -> None:
        """Remove a peer by address. No-op if not found."""
        if not self._path.exists():
            return
        try:
            normalized = self.normalize(address)
        except ValueError:
            return
        lines = self._path.read_text().splitlines()
        new_lines = [
            line for line in lines
            if line.strip() != normalized
        ]
        self._path.write_text("\n".join(new_lines) + "\n" if new_lines else "")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_peers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add newsnet/peers.py tests/test_peers.py
git commit -m "feat: add PeerManager for peers.txt file I/O"
```

---

### Task 2: PeerManager — RNS connect/disconnect

**Files:**
- Modify: `newsnet/peers.py`
- Modify: `tests/test_peers.py`

**Step 1: Write failing tests for connect/disconnect**

```python
# Append to tests/test_peers.py
from unittest.mock import patch, MagicMock


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_connect_creates_interface(MockTCP, tmp_path):
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    MockTCP.assert_called_once()
    assert "hub.example.com" in pm.connections()


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_disconnect_tears_down(MockTCP, tmp_path):
    mock_iface = MagicMock()
    MockTCP.return_value = mock_iface
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    pm.disconnect("hub.example.com:4242")
    mock_iface.detach.assert_called_once()
    assert "hub.example.com" not in pm.connections()


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_connect_failure_logs_warning(MockTCP, tmp_path, caplog):
    MockTCP.side_effect = Exception("Connection refused")
    pm = PeerManager(tmp_path)
    pm.connect("bad.host:1234")  # should not raise
    assert "bad.host" not in pm.connections()


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_connect_all_on_startup(MockTCP, tmp_path):
    peers_file = tmp_path / "peers.txt"
    peers_file.write_text("hub1.com:4242\nhub2.com:4242\n")
    pm = PeerManager(tmp_path)
    pm.connect_all()
    assert MockTCP.call_count == 2


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_disconnect_all(MockTCP, tmp_path):
    mock_iface = MagicMock()
    MockTCP.return_value = mock_iface
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    pm.disconnect_all()
    mock_iface.detach.assert_called_once()
    assert len(pm.connections()) == 0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_peers.py -v -k "connect or disconnect"`
Expected: FAIL — `AttributeError: 'PeerManager' object has no attribute 'connect'`

**Step 3: Add connect/disconnect to PeerManager**

Add these imports and methods to `newsnet/peers.py`:

```python
# Add to top of file
import logging

log = logging.getLogger(__name__)

# Add to PeerManager class:

    def __init__(self, config_dir: Path):
        self._path = Path(config_dir) / _FILENAME
        self._interfaces: dict[str, object] = {}  # normalized_addr -> TCPClientInterface

    def connect(self, address: str) -> None:
        """Create a TCPClientInterface for the given address."""
        from RNS.Interfaces.TCPInterface import TCPClientInterface

        normalized = self.normalize(address)
        if normalized in self._interfaces:
            return
        host, port = self.parse_address(address)
        try:
            iface = TCPClientInterface(
                RNS.Transport,
                f"TCP:{normalized}",
                host,
                port,
                False,   # kiss_framing
            )
            iface.OUT = True
            self._interfaces[normalized] = iface
            log.info(f"Connected to TCP peer {normalized}")
        except Exception:
            log.warning(f"Failed to connect to TCP peer {normalized}", exc_info=True)

    def disconnect(self, address: str) -> None:
        """Tear down connection to a peer."""
        try:
            normalized = self.normalize(address)
        except ValueError:
            return
        iface = self._interfaces.pop(normalized, None)
        if iface is not None:
            try:
                iface.detach()
            except Exception:
                log.warning(f"Error detaching {normalized}", exc_info=True)

    def connections(self) -> dict[str, object]:
        """Return dict of normalized_addr -> interface for active connections."""
        return dict(self._interfaces)

    def connect_all(self) -> None:
        """Connect to all peers in peers.txt."""
        for addr in self.list_peers():
            self.connect(addr)

    def disconnect_all(self) -> None:
        """Tear down all connections."""
        for addr in list(self._interfaces.keys()):
            self.disconnect(addr)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_peers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add newsnet/peers.py tests/test_peers.py
git commit -m "feat: add TCP connect/disconnect to PeerManager"
```

---

### Task 3: Integrate PeerManager into Node

**Files:**
- Modify: `newsnet/node.py`
- Modify: `tests/test_node.py`

**Step 1: Write failing test**

```python
# Append to tests/test_node.py

@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_start_connects_peers(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()

    MockPM.return_value.connect_all.assert_called_once()


@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_shutdown_disconnects_peers(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    node.shutdown()

    MockPM.return_value.disconnect_all.assert_called_once()


@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_add_peer(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()
    MockPM.return_value.add.return_value = "hub.example.com:4242"

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    result = node.add_tcp_peer("hub.example.com:4242")

    assert result == "hub.example.com:4242"
    MockPM.return_value.add.assert_called_once_with("hub.example.com:4242")
    MockPM.return_value.connect.assert_called_once_with("hub.example.com:4242")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_node.py -v -k "peer"`
Expected: FAIL

**Step 3: Integrate PeerManager into Node**

In `newsnet/node.py`, add these changes:

```python
# Add import at top:
from newsnet.peers import PeerManager

# In Node.__init__, add:
        self._peer_mgr = PeerManager(config.config_dir)

# Add property:
    @property
    def peer_manager(self) -> PeerManager:
        return self._peer_mgr

# At end of Node.start(), add:
        self._peer_mgr.connect_all()

# In Node.shutdown(), before self._store.close(), add:
        self._peer_mgr.disconnect_all()

# Add methods:
    def add_tcp_peer(self, address: str) -> str:
        """Add a TCP peer, save to file, and connect immediately."""
        normalized = self._peer_mgr.add(address)
        self._peer_mgr.connect(address)
        return normalized

    def remove_tcp_peer(self, address: str) -> None:
        """Disconnect and remove a TCP peer."""
        self._peer_mgr.disconnect(address)
        self._peer_mgr.remove(address)

    def list_tcp_peers(self) -> list[dict]:
        """List TCP peers with connection status."""
        connections = self._peer_mgr.connections()
        result = []
        for addr in self._peer_mgr.list_peers():
            result.append({
                "address": addr,
                "connected": addr in connections,
            })
        return result
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_node.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add newsnet/node.py newsnet/peers.py tests/test_node.py
git commit -m "feat: integrate PeerManager into Node startup/shutdown"
```

---

### Task 4: CLI peer subcommand

**Files:**
- Modify: `cli/main.py`
- Modify: `tests/test_cli.py`

**Step 1: Write failing tests**

```python
# Append to tests/test_cli.py

def test_parser_peer_add():
    parser = build_parser()
    args = parser.parse_args(["peer", "add", "hub.example.com:4242"])
    assert args.command == "peer"
    assert args.peer_command == "add"
    assert args.address == "hub.example.com:4242"


def test_parser_peer_remove():
    parser = build_parser()
    args = parser.parse_args(["peer", "remove", "hub.example.com:4242"])
    assert args.command == "peer"
    assert args.peer_command == "remove"
    assert args.address == "hub.example.com:4242"


def test_parser_peer_list():
    parser = build_parser()
    args = parser.parse_args(["peer", "list"])
    assert args.command == "peer"
    assert args.peer_command == "list"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v -k "peer"`
Expected: FAIL — `error: argument command: invalid choice: 'peer'`

**Step 3: Add peer subcommand to CLI**

In `cli/main.py`, add to `build_parser()` after the filter subparser block:

```python
    # peer
    peer_p = sub.add_parser("peer", help="Manage TCP peers")
    peer_sub = peer_p.add_subparsers(dest="peer_command")

    peer_add = peer_sub.add_parser("add", help="Add a TCP peer")
    peer_add.add_argument("address", help="host:port (port defaults to 4965)")

    peer_rm = peer_sub.add_parser("remove", help="Remove a TCP peer")
    peer_rm.add_argument("address", help="host:port to remove")

    peer_sub.add_parser("list", help="List TCP peers")
```

Add the command handler function:

```python
def cmd_peer(node, args):
    if args.peer_command == "add":
        try:
            result = node.add_tcp_peer(args.address)
            print(f"Added peer: {result}")
        except ValueError as e:
            print(f"Invalid address: {e}")
    elif args.peer_command == "remove":
        node.remove_tcp_peer(args.address)
        print(f"Removed peer: {args.address}")
    elif args.peer_command == "list":
        peers = node.list_tcp_peers()
        if not peers:
            print("No TCP peers configured.")
            return
        for p in peers:
            status = "connected" if p["connected"] else "disconnected"
            print(f"  {p['address']:30s}  {status}")
```

Add to the `COMMANDS` dict:

```python
    "peer": lambda node, args: cmd_peer(node, args),
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add cli/main.py tests/test_cli.py
git commit -m "feat: add 'newsnet peer' CLI subcommand"
```

---

### Task 5: TUI Peers Screen

**Files:**
- Modify: `tui/app.py`

**Step 1: Add AddPeerScreen**

```python
class AddPeerScreen(Screen):
    """Screen for adding a new TCP peer."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Add TCP Peer", id="peer-form-title")
        yield Label("Address (host:port, port defaults to 4965):")
        yield Input(placeholder="e.g. hub.example.com:4242", id="peer-address-input")
        yield Static("[Enter] to add | [Escape] to cancel", id="peer-form-help")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#peer-address-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        address = event.value.strip()
        if not address:
            self.notify("Address is required", severity="error")
            return
        try:
            result = self.app._node.add_tcp_peer(address)
            self.notify(f"Added peer: {result}")
            self.app.pop_screen()
        except ValueError as e:
            self.notify(f"Invalid address: {e}", severity="error")

    def action_cancel(self) -> None:
        self.app.pop_screen()
```

**Step 2: Add PeerScreen**

```python
class PeerScreen(Screen):
    """Screen for viewing and managing TCP peers."""

    BINDINGS = [
        Binding("a", "add_peer", "Add"),
        Binding("d", "delete_peer", "Delete"),
        Binding("delete", "delete_peer", "Delete"),
        Binding("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("TCP Peers", id="peer-title")
        yield DataTable(id="peer-table")
        yield Static("[a] Add | [d/Delete] Remove | [Escape] Back", id="peer-help")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#peer-table", DataTable)
        table.add_columns("Address", "Status")
        table.cursor_type = "row"
        self._load_peers()

    def _load_peers(self) -> None:
        table = self.query_one("#peer-table", DataTable)
        table.clear()
        self._peers = self.app._node.list_tcp_peers()
        for p in self._peers:
            status = "Connected" if p["connected"] else "Disconnected"
            table.add_row(p["address"], status)

    def on_screen_resume(self) -> None:
        self._load_peers()

    def action_add_peer(self) -> None:
        self.app.push_screen(AddPeerScreen())

    def action_delete_peer(self) -> None:
        table = self.query_one("#peer-table", DataTable)
        if not self._peers:
            return
        row_index = table.cursor_row
        if 0 <= row_index < len(self._peers):
            p = self._peers[row_index]
            self.app._node.remove_tcp_peer(p["address"])
            self.notify(f"Removed peer: {p['address']}")
            self._load_peers()

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

**Step 3: Add keybinding to NewsnetApp**

Add to `NewsnetApp.BINDINGS`:

```python
        Binding("t", "tcp_peers", "TCP Peers"),
```

Add action method to `NewsnetApp`:

```python
    def action_tcp_peers(self) -> None:
        self.push_screen(PeerScreen())
```

**Step 4: Run existing TUI tests to check nothing broke**

Run: `python -m pytest tests/test_tui.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tui/app.py
git commit -m "feat: add TCP Peers screen to TUI"
```

---

### Task 6: Update PyInstaller spec and final verification

**Files:**
- Modify: `newsnet.spec` (line 19, hiddenimports)

**Step 1: Add hidden import for peers module**

Add to the `hiddenimports` list in `newsnet.spec`:

```python
        'newsnet.peers',
```

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add newsnet.spec
git commit -m "chore: add newsnet.peers to PyInstaller hiddenimports"
```

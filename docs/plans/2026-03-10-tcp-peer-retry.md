# TCP Peer Auto-Retry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically retry failed TCP peer connections on each sync loop iteration, track consecutive failures, and surface failure counts in CLI and TUI.

**Architecture:** PeerManager gains a `_fail_counts` dict tracking consecutive failures per address. `connect()` updates it on success/failure. A new `retry_disconnected()` method is called from the sync loop. Node and UI layers pass through the failure count.

**Tech Stack:** Python 3.11+, Textual (TUI)

---

### Task 1: PeerManager failure tracking

**Files:**
- Modify: `newsnet/peers.py`
- Modify: `tests/test_peers.py`

**Step 1: Write failing tests**

Add to the end of `tests/test_peers.py`:

```python
def test_fail_count_starts_at_zero(tmp_path):
    pm = PeerManager(tmp_path)
    assert pm.fail_count("hub.example.com:4242") == 0


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_successful_connect_resets_fail_count(MockTCP, tmp_path):
    pm = PeerManager(tmp_path)
    pm._fail_counts["hub.example.com:4242"] = 3
    pm.connect("hub.example.com:4242")
    assert pm.fail_count("hub.example.com:4242") == 0


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_failed_connect_increments_fail_count(MockTCP, tmp_path):
    MockTCP.side_effect = Exception("refused")
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    assert pm.fail_count("hub.example.com:4242") == 1
    pm.connect("hub.example.com:4242")
    assert pm.fail_count("hub.example.com:4242") == 2


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_remove_clears_fail_count(MockTCP, tmp_path):
    pm = PeerManager(tmp_path)
    pm.add("hub.example.com:4242")
    pm._fail_counts["hub.example.com:4242"] = 5
    pm.remove("hub.example.com:4242")
    assert pm.fail_count("hub.example.com:4242") == 0
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_peers.py -v -k "fail_count or resets_fail or increments_fail or clears_fail"`
Expected: FAIL — `AttributeError: 'PeerManager' object has no attribute 'fail_count'`

**Step 3: Implement failure tracking**

In `newsnet/peers.py`, make these changes:

1. Add `_fail_counts` to `__init__`:
```python
    def __init__(self, config_dir: Path):
        self._path = Path(config_dir) / _FILENAME
        self._interfaces: dict[str, object] = {}
        self._fail_counts: dict[str, int] = {}
```

2. Add `fail_count` method:
```python
    def fail_count(self, address: str) -> int:
        """Return consecutive failure count for an address."""
        try:
            normalized = self.normalize(address)
        except ValueError:
            return 0
        return self._fail_counts.get(normalized, 0)
```

3. In `connect()`, after `self._interfaces[normalized] = iface` and `log.info(...)`, add:
```python
            self._fail_counts.pop(normalized, None)
```

4. In `connect()`, in the `except Exception:` block after `log.warning(...)`, add:
```python
            self._fail_counts[normalized] = self._fail_counts.get(normalized, 0) + 1
```

5. In `remove()`, after the file write at the end, add:
```python
        self._fail_counts.pop(normalized, None)

```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_peers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add newsnet/peers.py tests/test_peers.py
git commit -m "feat: track consecutive connection failure counts in PeerManager"
```

---

### Task 2: PeerManager retry_disconnected

**Files:**
- Modify: `newsnet/peers.py`
- Modify: `tests/test_peers.py`

**Step 1: Write failing tests**

Add to `tests/test_peers.py`:

```python
@patch("newsnet.peers.TCPClientInterface", create=True)
def test_retry_disconnected_reconnects(MockTCP, tmp_path):
    peers_file = tmp_path / "peers.txt"
    peers_file.write_text("hub1.com:4242\nhub2.com:4242\n")
    pm = PeerManager(tmp_path)
    # Only hub1 is connected
    pm._interfaces["hub1.com:4242"] = MagicMock()
    pm.retry_disconnected()
    # Should only try to connect hub2
    MockTCP.assert_called_once()
    call_args = MockTCP.call_args
    assert call_args[0][2] == "hub2.com"  # host argument


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_retry_disconnected_no_peers(MockTCP, tmp_path):
    pm = PeerManager(tmp_path)
    pm.retry_disconnected()  # should not raise
    MockTCP.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_peers.py -v -k "retry"`
Expected: FAIL — `AttributeError: 'PeerManager' object has no attribute 'retry_disconnected'`

**Step 3: Implement retry_disconnected**

Add to `PeerManager` class in `newsnet/peers.py`:

```python
    def retry_disconnected(self) -> None:
        """Attempt to reconnect any peers not currently connected."""
        for addr in self.list_peers():
            normalized = self.normalize(addr)
            if normalized not in self._interfaces:
                self.connect(addr)
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_peers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add newsnet/peers.py tests/test_peers.py
git commit -m "feat: add retry_disconnected to PeerManager"
```

---

### Task 3: Wire retry into sync loop and list_tcp_peers

**Files:**
- Modify: `newsnet/node.py`
- Modify: `tests/test_node.py`

**Step 1: Write failing tests**

Add to `tests/test_node.py`:

```python
@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_list_tcp_peers_includes_fail_count(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()
    MockPM.return_value.list_peers.return_value = ["hub.example.com:4242"]
    MockPM.return_value.connections.return_value = {}
    MockPM.return_value.fail_count.return_value = 3

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    peers = node.list_tcp_peers()

    assert len(peers) == 1
    assert peers[0]["fail_count"] == 3
    assert peers[0]["connected"] is False
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_node.py -v -k "fail_count"`
Expected: FAIL — `KeyError: 'fail_count'`

**Step 3: Implement changes**

In `newsnet/node.py`:

1. Update `list_tcp_peers()` to include fail_count:
```python
    def list_tcp_peers(self) -> list[dict]:
        """List TCP peers with connection status."""
        connections = self._peer_mgr.connections()
        result = []
        for addr in self._peer_mgr.list_peers():
            result.append({
                "address": addr,
                "connected": addr in connections,
                "fail_count": self._peer_mgr.fail_count(addr),
            })
        return result
```

2. Update `_periodic_sync_loop()` to retry before syncing:
```python
    def _periodic_sync_loop(self):
        while self._running:
            try:
                self._peer_mgr.retry_disconnected()
                self.sync_all_peers()
            except Exception:
                log.exception("Error in periodic sync")
            # Sleep in small increments so shutdown is responsive
            interval = self._sync_engine.sync_interval_seconds
            elapsed = 0.0
            while elapsed < interval and self._running:
                time.sleep(1.0)
                elapsed += 1.0
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_node.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add newsnet/node.py tests/test_node.py
git commit -m "feat: retry disconnected peers in sync loop, add fail_count to list"
```

---

### Task 4: CLI and TUI failure count display

**Files:**
- Modify: `cli/main.py`
- Modify: `tui/app.py`

**Step 1: Update CLI peer list**

In `cli/main.py`, update the `cmd_peer` function's list branch:

```python
    elif args.peer_command == "list":
        peers = node.list_tcp_peers()
        if not peers:
            print("No TCP peers configured.")
            return
        for p in peers:
            if p["connected"]:
                status = "connected"
            elif p["fail_count"] > 0:
                status = f"disconnected (failures: {p['fail_count']})"
            else:
                status = "disconnected"
            print(f"  {p['address']:30s}  {status}")
```

**Step 2: Update TUI PeerScreen**

In `tui/app.py`, update `PeerScreen`:

1. Change `on_mount` columns:
```python
    def on_mount(self) -> None:
        table = self.query_one("#peer-table", DataTable)
        table.add_columns("Address", "Status", "Failures")
        table.cursor_type = "row"
        self._load_peers()
```

2. Update `_load_peers`:
```python
    def _load_peers(self) -> None:
        table = self.query_one("#peer-table", DataTable)
        table.clear()
        self._peers = self.app._node.list_tcp_peers()
        for p in self._peers:
            status = "Connected" if p["connected"] else "Disconnected"
            failures = str(p["fail_count"]) if p["fail_count"] > 0 else ""
            table.add_row(p["address"], status, failures)
            if p["fail_count"] == 5:
                self.notify(
                    f"Peer {p['address']} has failed 5 consecutive times",
                    severity="warning",
                )
```

**Step 3: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add cli/main.py tui/app.py
git commit -m "feat: show connection failure counts in CLI and TUI"
```

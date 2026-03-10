"""Manage TCP peer addresses stored in peers.txt."""
from __future__ import annotations

import logging
from pathlib import Path

import RNS

log = logging.getLogger(__name__)

_DEFAULT_PORT = 4965
_FILENAME = "peers.txt"
_HEADER = "# TCP peer addresses (one per line: host:port)"


class PeerManager:
    def __init__(self, config_dir: Path):
        self._path = Path(config_dir) / _FILENAME
        self._interfaces: dict[str, object] = {}  # normalized_addr -> TCPClientInterface

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
        """Return list of peer addresses from peers.txt."""
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

    def connect(self, address: str) -> None:
        """Create a TCPClientInterface for the given address."""
        import sys
        _mod = sys.modules[__name__]
        if not hasattr(_mod, "TCPClientInterface"):
            from RNS.Interfaces.TCPInterface import TCPClientInterface as _tcp
            _mod.TCPClientInterface = _tcp  # type: ignore[attr-defined]
        TCPClientInterface = _mod.TCPClientInterface  # type: ignore[attr-defined]

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

"""Entry point for frozen (PyInstaller) and direct execution."""
from __future__ import annotations

import sys

_BUILD_VERSION = "0.2.0"

# ---------------------------------------------------------------------------
# Frozen-build fix: RNS.Interfaces.__init__ uses glob.glob() to discover .py
# files on disk. In a PyInstaller bundle there are no .py files, so the glob
# returns nothing and `from RNS.Interfaces import *` silently imports zero
# names — crashing later with NameError. Monkey-patching glob.glob *before*
# any RNS code is imported makes the discovery work inside frozen builds.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    print(f"[newsnet v{_BUILD_VERSION} frozen build]", flush=True)

    import glob as _glob
    import os as _os

    _original_glob = _glob.glob
    _INTERFACE_MODULES = [
        "Interface", "LocalInterface", "AutoInterface", "BackboneInterface",
        "TCPInterface", "UDPInterface", "I2PInterface", "SerialInterface",
        "PipeInterface", "KISSInterface", "AX25KISSInterface",
        "RNodeInterface", "RNodeMultiInterface", "WeaveInterface",
    ]

    def _patched_glob(pattern, *args, **kwargs):
        if pattern.endswith("*.py") and pattern.replace("\\", "/").endswith("Interfaces/*.py"):
            base = pattern[:-4]
            return [_os.path.join(base, f"{m}.py") for m in _INTERFACE_MODULES]
        if pattern.endswith("*.pyc") and pattern.replace("\\", "/").endswith("Interfaces/*.pyc"):
            return []
        return _original_glob(pattern, *args, **kwargs)

    _glob.glob = _patched_glob


def _load_config():
    from newsnet.config import NewsnetConfig
    cfg = NewsnetConfig()
    cfg.ensure_dirs()
    if cfg.config_file_path.exists():
        cfg = NewsnetConfig.from_file(cfg.config_file_path)
    return cfg


def _run_server(config):
    import uvicorn
    from newsnet.node import Node
    from newsnet.wizard import is_first_run, run_wizard
    from api.app import create_app
    from api.websocket import WebSocketHub

    if is_first_run(config):
        # Node needed only to pass add_tcp_peer to wizard; create minimally
        node = Node(config)
        run_wizard(config, add_peer_fn=node.add_tcp_peer)
        # Re-load config after wizard saved it
        config = _load_config()
        node = Node(config)
    else:
        node = Node(config)

    hub = WebSocketHub()
    app = create_app(config=config, node=node, hub=hub)

    print(f"[newsnet] Web interface: http://{config.api_host}:{config.api_port}")
    uvicorn.run(app, host=config.api_host, port=config.api_port, log_level="warning")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        # Allow CLI invocation: python newsnet_main.py cli <subcommand>
        sys.argv.pop(1)
        from cli.main import main
        main()
    else:
        config = _load_config()
        _run_server(config)

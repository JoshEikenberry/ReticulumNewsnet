from __future__ import annotations

import socket
import uuid
from typing import Callable

from newsnet.config import NewsnetConfig


def is_first_run(config: NewsnetConfig) -> bool:
    """True if the node has never been configured (no api_token set)."""
    return not config.api_token


def run_wizard(config: NewsnetConfig, add_peer_fn: Callable[[str], None] | None = None):
    """Interactive first-run setup. Modifies config in place and saves it."""
    print("\nWelcome to ReticulumNewsnet!")
    print("════════════════════════════")
    print("Let's get you set up. This will only take a minute.\n")

    # Step 1: Display name
    print("Step 1 of 3 — What should we call you?")
    print("Your display name is shown alongside your posts.")
    print("It can be anything you like.\n")
    name = input(f"  Display name [{config.display_name}]: ").strip()
    if name:
        config.display_name = name

    print()

    # Step 2: Data location (default only — no custom path in v1)
    print("Step 2 of 3 — Where should your data be stored?")
    print(f"  Using default location: {config.config_dir}")
    input("  Press Enter to continue... ")

    print()

    # Step 3: Optional TCP peer
    print("Step 3 of 3 — Connect to a friend's node (optional)")
    print("If someone you know is already running Newsnet, ask them")
    print("for their node address (looks like: 192.168.1.x:4965)")
    print("and enter it here to start syncing right away.\n")
    print("On the same WiFi? Skip this — you'll find each other automatically.\n")
    peer_addr = input("  Node address (or press Enter to skip): ").strip()
    if peer_addr and add_peer_fn:
        try:
            add_peer_fn(peer_addr)
            print(f"  Connected to {peer_addr}")
        except Exception as e:
            print(f"  ! Could not connect to {peer_addr}: {e}")

    # Generate token and save
    config.api_token = str(uuid.uuid4())
    config.ensure_dirs()
    config.save()

    # Summary
    print("\n────────────────────────────────────────────────────")
    print("All done! Starting your node...\n")
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "localhost"
    url = f"http://{local_ip}:{config.api_port}/?token={config.api_token}"
    print(f"  Open this link in your browser:")
    print(f"  {url}")
    print("  (Your token is saved — future visits won't need it again)\n")

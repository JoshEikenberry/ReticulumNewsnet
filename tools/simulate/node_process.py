from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx


def _write_config(config_dir: Path, index: int, port: int, token: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f'display_name = "sim-node-{index}"',
        f'api_port = {port}',
        f'api_host = "127.0.0.1"',
        f'api_token = "{token}"',
        'retention_hours = 168',
        'sync_interval_minutes = 1',
        'strict_filtering = false',
    ]
    (config_dir / "config.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class NodeProcess:
    def __init__(self, index: int, port: int):
        self.index = index
        self.port = port
        self.token = str(uuid.uuid4())
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"newsnet-sim-{index}-"))
        self._proc: subprocess.Popen | None = None

        _write_config(self._temp_dir, index, port, self.token)

    def start(self) -> None:
        """Spawn newsnet_main.py subprocess with isolated config dir."""
        env = os.environ.copy()
        env["NEWSNET_CONFIG_DIR"] = str(self._temp_dir)
        env["NEWSNET_NO_BROWSER"] = "1"
        env.setdefault("NEWSNET_DEBUG", "")

        main_py = Path(__file__).parents[2] / "newsnet_main.py"
        self._proc = subprocess.Popen(
            [sys.executable, str(main_py)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def wait_ready(self, timeout: float = 15.0) -> None:
        """Poll /api/local-auth until 200 or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(
                    f"http://127.0.0.1:{self.port}/api/local-auth", timeout=2.0
                )
                if r.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.3)
        raise TimeoutError(f"sim-node-{self.index} (port {self.port}) did not start within {timeout}s")

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def post_article(
        self,
        newsgroup: str,
        subject: str,
        body: str,
        references: list[str] | None = None,
    ) -> str:
        """Post an article and return its message_id."""
        r = httpx.post(
            self._url("/api/articles"),
            json={
                "newsgroup": newsgroup,
                "subject": subject,
                "body": body,
                "references": references or [],
            },
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()["message_id"]

    def list_article_ids(self) -> set[str]:
        """Return set of all message_ids this node currently holds."""
        r = httpx.get(self._url("/api/articles"), headers=self._headers(), timeout=10)
        r.raise_for_status()
        return {a["message_id"] for a in r.json()}

    def add_tcp_peer(self, host: str, port: int) -> None:
        """Tell this node to connect to another node as a TCP peer."""
        r = httpx.post(
            self._url("/api/peers"),
            json={"address": f"{host}:{port}"},
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()

    def close(self) -> None:
        """Terminate subprocess and delete temp dir."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)

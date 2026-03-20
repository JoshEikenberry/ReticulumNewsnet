from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NewsnetConfig:
    display_name: str = "anonymous"
    retention_hours: int = 168
    sync_interval_minutes: int = 15
    strict_filtering: bool = True
    api_token: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    config_dir_override: str | None = None

    def __post_init__(self):
        self.retention_hours = max(1, min(720, self.retention_hours))

    @property
    def config_dir(self) -> Path:
        if self.config_dir_override:
            return Path(self.config_dir_override)
        return Path.home() / ".config" / "reticulum-newsnet"

    @property
    def db_path(self) -> Path:
        return self.config_dir / "newsnet.db"

    @property
    def identity_path(self) -> Path:
        return self.config_dir / "identity"

    @property
    def config_file_path(self) -> Path:
        return self.config_dir / "config.toml"

    @classmethod
    def from_file(cls, path: str | Path) -> NewsnetConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self):
        """Write application fields back to config.toml.
        Does not write config_dir_override (runtime-only).
        Does not touch [[interface]] blocks (user-managed).
        """
        def _toml_val(v) -> str:
            if isinstance(v, bool):
                return "true" if v else "false"
            if isinstance(v, str):
                escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            return str(v)

        fields_to_save = [
            "display_name", "retention_hours", "sync_interval_minutes",
            "strict_filtering", "api_token", "api_host", "api_port",
        ]
        lines = [f"{k} = {_toml_val(getattr(self, k))}" for k in fields_to_save]
        self.config_file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def ensure_dirs(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

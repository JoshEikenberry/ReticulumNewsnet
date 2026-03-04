from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NewsnetConfig:
    display_name: str = "anonymous"
    retention_hours: int = 168
    sync_interval_minutes: int = 15
    strict_filtering: bool = True
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
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def ensure_dirs(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

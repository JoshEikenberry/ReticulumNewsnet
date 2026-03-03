from __future__ import annotations

from pathlib import Path

import RNS


class IdentityManager:
    def __init__(self, identity_path: str | Path):
        self._path = str(identity_path)
        self._identity = None

    def get_or_create(self) -> RNS.Identity:
        if self._identity is not None:
            return self._identity

        if Path(self._path).exists():
            self._identity = RNS.Identity.from_file(self._path)

        if self._identity is None:
            self._identity = RNS.Identity()
            self._identity.to_file(self._path)

        return self._identity

    @property
    def identity(self) -> RNS.Identity:
        if self._identity is None:
            return self.get_or_create()
        return self._identity

    @property
    def hash_hex(self) -> str:
        return self.identity.hash.hex()

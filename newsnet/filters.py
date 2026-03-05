from __future__ import annotations

import fnmatch
from pathlib import Path

# Mapping from filter_type to filename
_TYPE_FILES = {
    "author": "authors.txt",
    "newsgroup": "newsgroups.txt",
    "word": "words.txt",
}

# Mapping from file prefix to filter_mode
_PREFIX_TO_MODE = {"block": "blacklist", "allow": "whitelist"}
_MODE_TO_PREFIX = {"blacklist": "block", "whitelist": "allow"}

_FILE_HEADERS = {
    "authors.txt": "# Blocked/allowed authors (one per line: block:pattern or allow:pattern)",
    "newsgroups.txt": "# Blocked/allowed newsgroups (one per line: block:pattern or allow:pattern)",
    "words.txt": "# Blocked/allowed words (one per line: block:pattern or allow:pattern)",
}


class TextFilterStore:
    """Stores filters as plain text files — one file per filter type."""

    def __init__(self, config_dir: Path):
        self._config_dir = Path(config_dir)

    def ensure_files(self):
        """Create filter files with comment headers if they don't exist."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        for filename, header in _FILE_HEADERS.items():
            path = self._config_dir / filename
            if not path.exists():
                path.write_text(header + "\n")

    def _path_for_type(self, filter_type: str) -> Path:
        filename = _TYPE_FILES.get(filter_type)
        if not filename:
            raise ValueError(f"Unknown filter type: {filter_type}")
        return self._config_dir / filename

    def _parse_file(self, filter_type: str, path: Path) -> list[dict]:
        if not path.exists():
            return []
        results = []
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" in stripped:
                prefix, _, pattern = stripped.partition(":")
                prefix = prefix.lower()
                if prefix in _PREFIX_TO_MODE:
                    mode = _PREFIX_TO_MODE[prefix]
                else:
                    # No recognized prefix — treat entire line as pattern, default block
                    mode = "blacklist"
                    pattern = stripped
            else:
                mode = "blacklist"
                pattern = stripped
            results.append({
                "filter_type": filter_type,
                "filter_mode": mode,
                "pattern": pattern,
            })
        return results

    def list_filters(self) -> list[dict]:
        """Read all three files and return a combined list of filter dicts."""
        all_filters = []
        for filter_type, filename in _TYPE_FILES.items():
            path = self._config_dir / filename
            all_filters.extend(self._parse_file(filter_type, path))
        return all_filters

    def list_filters_by_type(self, filter_type: str) -> list[dict]:
        path = self._path_for_type(filter_type)
        return self._parse_file(filter_type, path)

    def add_filter(self, filter_type: str, filter_mode: str, pattern: str):
        """Append a filter line to the appropriate file."""
        path = self._path_for_type(filter_type)
        self._config_dir.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            header = _FILE_HEADERS.get(path.name, "")
            path.write_text(header + "\n")
        prefix = _MODE_TO_PREFIX.get(filter_mode, "block")
        with open(path, "a") as f:
            f.write(f"{prefix}:{pattern}\n")

    def remove_filter(self, filter_type: str, pattern: str):
        """Remove all lines matching the given pattern from the file."""
        path = self._path_for_type(filter_type)
        if not path.exists():
            return
        lines = path.read_text().splitlines()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue
            # Parse and check if this line matches the pattern to remove
            if ":" in stripped:
                prefix, _, line_pattern = stripped.partition(":")
                if prefix.lower() in _PREFIX_TO_MODE:
                    if line_pattern == pattern:
                        continue
                elif stripped == pattern:
                    continue
            elif stripped == pattern:
                continue
            new_lines.append(line)
        path.write_text("\n".join(new_lines) + "\n" if new_lines else "")


def migrate_from_store(store, text_filter_store: TextFilterStore):
    """Migrate filters from SQLite store to text files.

    Called once on startup if text files don't exist but SQLite filters do.
    """
    try:
        filters = store.list_filters()
    except Exception:
        return
    if not filters:
        return
    for f in filters:
        text_filter_store.add_filter(f["filter_type"], f["filter_mode"], f["pattern"])


class FilterEngine:
    def __init__(self, filters: list[dict]):
        self._filters = filters

    def should_keep(self, article: dict) -> bool:
        if not self._check_type("author", article.get("author_hash", "")):
            return False
        if not self._check_type("newsgroup", article.get("newsgroup", "")):
            return False
        if not self._check_type_word(article):
            return False
        return True

    def _check_type(self, filter_type: str, value: str) -> bool:
        whitelists = [
            f["pattern"] for f in self._filters
            if f["filter_type"] == filter_type and f["filter_mode"] == "whitelist"
        ]
        blacklists = [
            f["pattern"] for f in self._filters
            if f["filter_type"] == filter_type and f["filter_mode"] == "blacklist"
        ]
        if whitelists:
            if any(fnmatch.fnmatch(value, p) for p in whitelists):
                return True
            return False
        if blacklists:
            if any(fnmatch.fnmatch(value, p) for p in blacklists):
                return False
        return True

    def _check_type_word(self, article: dict) -> bool:
        text = (article.get("subject", "") + " " + article.get("body", "")).lower()
        whitelists = [
            f["pattern"].lower() for f in self._filters
            if f["filter_type"] == "word" and f["filter_mode"] == "whitelist"
        ]
        blacklists = [
            f["pattern"].lower() for f in self._filters
            if f["filter_type"] == "word" and f["filter_mode"] == "blacklist"
        ]
        if whitelists:
            if any(w in text for w in whitelists):
                return True
            return False
        if blacklists:
            if any(w in text for w in blacklists):
                return False
        return True

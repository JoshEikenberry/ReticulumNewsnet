from __future__ import annotations

import fnmatch


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

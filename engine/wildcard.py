"""Module 6 - Wildcard processing (permuterm index).

Every term t is stored under all rotations of t + "$". A pattern is rotated
so its last wildcard sits at the end, the literal prefix is found by binary
search, and a regex pass confirms each candidate.

    net*   ->  "$net"   prefix       *ing  ->  "ing$"  prefix
    n*k    ->  "k$n"    prefix       s?ack ->  "ack$s"  prefix
"""
from __future__ import annotations

import re
from bisect import bisect_left
from typing import Iterable

WILDCARD_CHARS = ("*", "?")


def has_wildcard(word: str) -> bool:
    return any(ch in word for ch in WILDCARD_CHARS)


def _clean(pattern: str) -> str:
    pattern = re.sub(r"[^\w*?]|_", "", pattern)
    return re.sub(r"\*+", "*", pattern)


def _to_regex(pattern: str) -> re.Pattern[str]:
    parts = []
    for ch in pattern:
        parts.append(".*" if ch == "*" else "." if ch == "?" else re.escape(ch))
    return re.compile("".join(parts))


class PermutermIndex:
    def __init__(self, vocabulary: Iterable[str]) -> None:
        pairs = []
        for term in vocabulary:
            marked = term + "$"
            for i in range(len(marked)):
                pairs.append((marked[i:] + marked[:i], term))
        pairs.sort()
        self._keys = [k for k, _ in pairs]
        self._terms = [t for _, t in pairs]

    def expand(self, pattern: str) -> list[str]:
        """Return every indexed term matching `pattern`, sorted."""
        pattern = _clean(pattern)
        if not pattern:
            return []
        marked = pattern + "$"
        last = max(marked.rfind("*"), marked.rfind("?"))
        if last == -1:                         # no wildcard: exact term lookup
            rotated = marked
        else:
            rotated = marked[last + 1:] + marked[: last + 1]
        prefix = re.split(r"[*?]", rotated, maxsplit=1)[0]

        regex = _to_regex(pattern)
        found: set[str] = set()
        i = bisect_left(self._keys, prefix)
        while i < len(self._keys) and self._keys[i].startswith(prefix):
            term = self._terms[i]
            if term not in found and regex.fullmatch(term):
                found.add(term)
            i += 1
        return sorted(found)

"""Module 3 - Text normalization / case folding.

Every token passes through the same normalizer at index time and at query
time, so "Café", "CAFE" and "cafe" all become the term "cafe".
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_POSSESSIVE = re.compile(r"['’]s$")
_APOSTROPHES = re.compile(r"['’]")


class Normalizer:
    """Case folding, accent stripping and apostrophe handling."""

    def normalize_token(self, token: str) -> str:
        folded = unicodedata.normalize("NFKD", token.casefold())
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        folded = _POSSESSIVE.sub("", folded)
        return _APOSTROPHES.sub("", folded)

    def normalize(self, tokens: Iterable[str]) -> list[str]:
        return [self.normalize_token(t) for t in tokens]

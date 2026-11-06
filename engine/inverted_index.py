"""Module 4 - Inverted index construction.

term -> {doc_id -> [positions]}. Positions make phrase queries possible;
term frequencies and document frequencies drive TF-IDF ranking.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

from .document_loader import Document


class InvertedIndex:
    def __init__(self) -> None:
        self._postings: dict[str, dict[int, list[int]]] = {}
        self._doc_length: dict[int, int] = {}

    # -- construction -----------------------------------------------------
    def add_document(self, doc_id: int, terms: Sequence[str]) -> None:
        self._doc_length[doc_id] = len(terms)
        for position, term in enumerate(terms):
            self._postings.setdefault(term, {}).setdefault(doc_id, []).append(position)

    # -- lookups ----------------------------------------------------------
    def postings(self, term: str) -> dict[int, list[int]]:
        return self._postings.get(term, {})

    def doc_ids(self, term: str) -> set[int]:
        return set(self._postings.get(term, ()))

    def positions(self, term: str, doc_id: int) -> list[int]:
        return self._postings.get(term, {}).get(doc_id, [])

    def all_doc_ids(self) -> set[int]:
        return set(self._doc_length)

    def vocabulary(self) -> list[str]:
        return sorted(self._postings)

    # -- statistics & ranking ---------------------------------------------
    @property
    def document_count(self) -> int:
        return len(self._doc_length)

    @property
    def term_count(self) -> int:
        return len(self._postings)

    @property
    def posting_count(self) -> int:
        return sum(len(p) for p in self._postings.values())

    def document_frequency(self, term: str) -> int:
        return len(self._postings.get(term, ()))

    def idf(self, term: str) -> float:
        df = self.document_frequency(term)
        return math.log10(1 + self.document_count / df) if df else 0.0

    def score(self, doc_id: int, terms: Iterable[str]) -> float:
        """Length-normalised TF-IDF: sum((1 + log tf) * idf) / sqrt(|doc|)."""
        total = 0.0
        for term in terms:
            tf = len(self.positions(term, doc_id))
            if tf:
                total += (1 + math.log10(tf)) * self.idf(term)
        length = self._doc_length.get(doc_id, 0)
        return total / math.sqrt(length) if length else 0.0


def build_index(
    documents: Iterable[Document],
    tokenize: Callable[[str], list[str]],
    normalize: Callable[[list[str]], list[str]],
) -> InvertedIndex:
    index = InvertedIndex()
    for doc in documents:
        index.add_document(doc.doc_id, normalize(tokenize(doc.text)))
    return index

"""Search engine package: wires the modules together."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .document_loader import Document, load_documents
from .inverted_index import InvertedIndex, build_index
from .normalizer import Normalizer
from .query_processor import QueryProcessor, QuerySyntaxError, SearchResult
from .tokenizer import tokenize
from .wildcard import PermutermIndex


@dataclass
class SearchEngine:
    documents: list[Document]
    index: InvertedIndex
    wildcards: PermutermIndex
    processor: QueryProcessor

    def search(self, query: str, limit: int = 50) -> SearchResult:
        return self.processor.search(query, limit)


def build_engine_from_documents(documents: list[Document]) -> SearchEngine:
    if not documents:
        raise ValueError("No .txt or .md documents were found in that folder.")
    normalizer = Normalizer()
    index = build_index(documents, tokenize, normalizer.normalize)
    wildcards = PermutermIndex(index.vocabulary())
    processor = QueryProcessor(documents, index, wildcards, normalizer)
    return SearchEngine(documents, index, wildcards, processor)


def build_engine(folder: str | Path) -> SearchEngine:
    return build_engine_from_documents(load_documents(folder))


__all__ = ["SearchEngine", "SearchResult", "QuerySyntaxError", "build_engine",
           "build_engine_from_documents"]

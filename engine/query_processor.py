"""Module 5 - Query processing.

Grammar (operators must be UPPERCASE so "and" / "or" stay ordinary words):

    or_expr  := and_expr ( "OR" and_expr )*
    and_expr := not_expr ( ["AND"] not_expr )*        # implicit AND
    not_expr := "NOT" not_expr | primary
    primary  := "(" or_expr ")" | "\"phrase\"" | word   # word may hold * or ?

Matching documents are ranked by TF-IDF over the positive (non-NOT) terms.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .document_loader import Document
from .inverted_index import InvertedIndex
from .normalizer import Normalizer
from .tokenizer import tokenize, tokenize_with_spans
from .wildcard import PermutermIndex, has_wildcard


class QuerySyntaxError(ValueError):
    """Raised with a message that tells the user how to fix the query."""


# --------------------------------------------------------------------------
# Abstract syntax tree
# --------------------------------------------------------------------------
@dataclass
class Term:
    word: str
    def __str__(self) -> str:
        return self.word


@dataclass
class Phrase:
    words: list[str]
    def __str__(self) -> str:
        return '"' + " ".join(self.words) + '"'


@dataclass
class Not:
    child: object
    def __str__(self) -> str:
        return f"NOT {self.child}"


@dataclass
class And:
    left: object
    right: object
    def __str__(self) -> str:
        return f"({self.left} AND {self.right})"


@dataclass
class Or:
    left: object
    right: object
    def __str__(self) -> str:
        return f"({self.left} OR {self.right})"


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------
_LEXER = re.compile(r'"[^"]*"?|\(|\)|[^\s()"]+')


class _Parser:
    def __init__(self, query: str) -> None:
        self.tokens = _LEXER.findall(query)
        self.pos = 0

    def parse(self):
        if not self.tokens:
            raise QuerySyntaxError('Type a word, a "phrase", or a wildcard such as net*.')
        node = self._or()
        if self.pos < len(self.tokens):
            raise QuerySyntaxError(
                f"Unexpected {self.tokens[self.pos]!r}. Check your parentheses and operators.")
        return node

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _or(self):
        node = self._and()
        while self._peek() == "OR":
            self.pos += 1
            node = Or(node, self._and())
        return node

    def _and(self):
        node = self._not()
        while True:
            tok = self._peek()
            if tok == "AND":
                self.pos += 1
                node = And(node, self._not())
            elif tok is not None and tok not in ("OR", ")"):
                node = And(node, self._not())          # implicit AND
            else:
                return node

    def _not(self):
        if self._peek() == "NOT":
            self.pos += 1
            return Not(self._not())
        return self._primary()

    def _primary(self):
        tok = self._peek()
        if tok is None:
            raise QuerySyntaxError("The query ends where a term was expected.")
        self.pos += 1
        if tok == "(":
            node = self._or()
            if self._peek() != ")":
                raise QuerySyntaxError("Missing closing parenthesis.")
            self.pos += 1
            return node
        if tok in (")", "AND", "OR"):
            raise QuerySyntaxError(f"{tok} needs a term on both sides.")
        if tok.startswith('"'):
            if len(tok) < 2 or not tok.endswith('"'):
                raise QuerySyntaxError('Close the phrase with a second " quote.')
            words = tok[1:-1].split()
            if not words:
                raise QuerySyntaxError("The phrase between quotes is empty.")
            if any(has_wildcard(w) for w in words):
                raise QuerySyntaxError("Wildcards can't be used inside a quoted phrase.")
            return Phrase(words)
        return Term(tok)


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
@dataclass
class Snippet:
    text: str
    spans: list[tuple[int, int]]          # highlight ranges inside `text`


@dataclass
class Hit:
    doc_id: int
    title: str
    filename: str
    score: float
    relevance: float                      # score / best score, 0..1
    snippet: Snippet


@dataclass
class SearchResult:
    query: str
    plan: str
    hits: list[Hit]
    total: int
    elapsed_ms: float
    terms: list[str]
    expansions: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class _Context:
    terms: list[str] = field(default_factory=list)
    expansions: dict[str, list[str]] = field(default_factory=dict)


def build_snippet(document: Document, match_terms: set[str],
                  normalizer: Normalizer, width: int = 230) -> Snippet:
    text = document.text
    newline = text.find("\n")
    body_start = newline + 1 if newline >= 0 else 0
    while body_start < len(text) and text[body_start].isspace():
        body_start += 1

    matches = [t for t in tokenize_with_spans(text)
               if normalizer.normalize_token(t.text) in match_terms]
    body_matches = [t for t in matches if t.start >= body_start]
    anchor = (body_matches or matches or [None])[0]
    lower = body_start if (anchor is None or body_matches) else 0

    start = lower if anchor is None else max(lower, anchor.start - 70)
    if start > lower:
        space = text.find(" ", start)
        if 0 <= space < (anchor.start if anchor else len(text)):
            start = space + 1
    end = min(len(text), start + width)
    if end < len(text):
        space = text.rfind(" ", start, end)
        if space > start:
            end = space

    prefix = "… " if start > lower else ""
    suffix = " …" if end < len(text) else ""
    flat = text[start:end].replace("\n", " ")
    spans = [(t.start - start + len(prefix), t.end - start + len(prefix))
             for t in matches if t.start >= start and t.end <= end]
    return Snippet(prefix + flat + suffix, spans)


# --------------------------------------------------------------------------
# Processor
# --------------------------------------------------------------------------
class QueryProcessor:
    def __init__(self, documents: list[Document], index: InvertedIndex,
                 wildcards: PermutermIndex, normalizer: Normalizer) -> None:
        self.documents = {d.doc_id: d for d in documents}
        self.index = index
        self.wildcards = wildcards
        self.normalizer = normalizer

    def search(self, query: str, limit: int = 50) -> SearchResult:
        started = time.perf_counter()
        tree = _Parser(query).parse()
        ctx = _Context()
        matched = self._evaluate(tree, True, ctx)

        terms = list(dict.fromkeys(ctx.terms))
        scored = [(self.index.score(d, terms), d) for d in matched]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        best = scored[0][0] if scored else 0.0

        match_terms = set(terms)
        hits = []
        for score, doc_id in scored[:limit]:
            doc = self.documents[doc_id]
            hits.append(Hit(doc_id, doc.title, doc.filename, score,
                            score / best if best > 0 else 0.0,
                            build_snippet(doc, match_terms, self.normalizer)))

        plan = str(tree)
        if isinstance(tree, (And, Or)):
            plan = plan[1:-1]                       # drop the redundant outer parentheses
        return SearchResult(query, plan, hits, len(matched),
                            (time.perf_counter() - started) * 1000,
                            sorted(match_terms), ctx.expansions)

    # -- evaluation -------------------------------------------------------
    def _evaluate(self, node, positive: bool, ctx: _Context) -> set[int]:
        if isinstance(node, Term):
            return self._term(node.word, positive, ctx)
        if isinstance(node, Phrase):
            return self._phrase(node.words, positive, ctx)
        if isinstance(node, Not):
            return self.index.all_doc_ids() - self._evaluate(node.child, not positive, ctx)
        left = self._evaluate(node.left, positive, ctx)
        right = self._evaluate(node.right, positive, ctx)
        return left & right if isinstance(node, And) else left | right

    def _normalized_terms(self, word: str) -> list[str]:
        return [t for t in self.normalizer.normalize(tokenize(word)) if t]

    def _term(self, word: str, positive: bool, ctx: _Context) -> set[int]:
        if has_wildcard(word):
            pattern = self.normalizer.normalize_token(word)
            expanded = self.wildcards.expand(pattern)
            ctx.expansions[word] = expanded
            if positive:
                ctx.terms.extend(expanded)
            docs: set[int] = set()
            for term in expanded:
                docs |= self.index.doc_ids(term)
            return docs
        return self._phrase([word], positive, ctx)

    def _phrase(self, words: list[str], positive: bool, ctx: _Context) -> set[int]:
        terms = [t for w in words for t in self._normalized_terms(w)]
        if not terms:
            return set()
        if positive:
            ctx.terms.extend(terms)
        candidates = set.intersection(*(self.index.doc_ids(t) for t in terms))
        if len(terms) == 1:
            return candidates
        found = set()
        for doc_id in candidates:
            starts = set(self.index.positions(terms[0], doc_id))
            for offset, term in enumerate(terms[1:], start=1):
                starts &= {p - offset for p in self.index.positions(term, doc_id)}
                if not starts:
                    break
            if starts:
                found.add(doc_id)
        return found

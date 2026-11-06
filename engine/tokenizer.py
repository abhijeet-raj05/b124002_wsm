"""Module 2 - Tokenization.

Splits raw text into word tokens. Letters and digits form tokens; an
apostrophe between letters stays inside the token ("don't"). Character
offsets are kept so the GUI can highlight matches in the original text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


def tokenize_with_spans(text: str) -> list[Token]:
    return [Token(m.group(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def tokenize(text: str) -> list[str]:
    return [m.group() for m in _TOKEN_RE.finditer(text)]

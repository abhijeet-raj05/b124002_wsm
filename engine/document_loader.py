"""Module 1 - Document loading.

Reads every .txt / .md file in a folder and turns it into a `Document`.
The first non-empty line of a file is used as the document title.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = (".txt", ".md")
MAX_TITLE_LENGTH = 90


@dataclass(frozen=True)
class Document:
    doc_id: int
    title: str
    path: Path
    text: str

    @property
    def filename(self) -> str:
        return self.path.name


def _readable_name(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _derive_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line if len(line) <= MAX_TITLE_LENGTH else _readable_name(path)
    return _readable_name(path)


def load_documents(folder: str | Path) -> list[Document]:
    """Load all supported files from `folder`; doc ids start at 1."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    paths = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    documents: list[Document] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue
        documents.append(Document(len(documents) + 1, _derive_title(path, text), path, text))
    return documents

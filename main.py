"""Entry point.

    python main.py                 launch the GUI on ./data
    python main.py --data FOLDER   launch the GUI on another folder
    python main.py --cli "net* AND NOT tcp"   run one query in the terminal
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine import QuerySyntaxError, build_engine

DEFAULT_DATA = Path(__file__).parent / "data"


def run_cli(folder: Path, query: str) -> int:
    engine = build_engine(folder)
    try:
        result = engine.search(query)
    except QuerySyntaxError as err:
        print(f"Query problem: {err}")
        return 2
    print(f"query : {result.query}\nplan  : {result.plan}")
    print(f"found : {result.total} document(s) in {result.elapsed_ms:.2f} ms")
    for word, terms in result.expansions.items():
        print(f"expand: {word} -> {', '.join(terms) or '(no matching terms)'}")
    for rank, hit in enumerate(result.hits, 1):
        print(f"{rank:>2}. [{hit.score:.3f}] {hit.title}  ({hit.filename})")
        print(f"      {hit.snippet.text}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lexicon document search")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="folder of .txt/.md files")
    parser.add_argument("--cli", metavar="QUERY", help="run a single query without the GUI")
    args = parser.parse_args()

    if args.cli is not None:
        return run_cli(args.data, args.cli)

    try:                                    # crisp text on high-DPI Windows screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    from gui.app import SearchApp
    SearchApp(args.data).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

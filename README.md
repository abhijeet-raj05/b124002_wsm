# Lexicon - a small search engine (WSM assignment)

Pure Python 3.10+ and Tkinter. No third-party packages.

```
wsm_search_engine/
├── main.py                    entry point (GUI, or --cli "query")
├── data/                      16 sample documents (.txt)
├── engine/
│   ├── document_loader.py     1. document loading
│   ├── tokenizer.py           2. tokenization
│   ├── normalizer.py          3. text normalization / case folding
│   ├── inverted_index.py      4. inverted index construction (+ TF-IDF scoring)
│   ├── query_processor.py     5. query processing (Boolean, phrase, ranking, snippets)
│   ├── wildcard.py            6. wildcard processing (permuterm index)
│   └── __init__.py            wires the modules into a SearchEngine
├── gui/app.py                 7. frontend GUI
└── tests/test_engine.py       unit tests
```

## Run

```
python main.py                      # GUI on ./data
python main.py --data my_folder     # GUI on your own .txt / .md files
python main.py --cli "rout* AND NOT bgp"
python -m unittest discover -s tests
```
On Linux you may need `sudo apt install python3-tk`.

## Pipeline

1. **Load** - every `.txt`/`.md` file becomes a `Document` (first line = title).
2. **Tokenize** - regex word tokens with character offsets (used for highlighting).
3. **Normalize** - case folding, accent stripping, apostrophe/possessive removal. The same
   normalizer runs on documents and on queries.
4. **Index** - `term -> {doc_id -> [positions]}`; positions enable phrase queries.
5. **Query** - recursive-descent parser, then set operations on postings.
6. **Wildcard** - permuterm index: each term is stored under all rotations of `term$`;
   `net*`, `*ing`, `n*k`, `n?twork` are rotated into prefix searches and verified with a regex.
7. **GUI** - search box, Search button, read-only result area (plus a sidebar showing index
   statistics and how the last query was understood).

## Query syntax

| Query | Meaning |
|---|---|
| `network tcp` / `network AND tcp` | both words (implicit AND) |
| `tcp OR udp` | either word |
| `paging NOT virtual` | paging without virtual |
| `(tcp OR udp) AND network` | parentheses group |
| `"page table"` | exact phrase |
| `net*`, `*ing`, `n*k`, `n?twork` | wildcards (`*` any letters, `?` one letter) |

`AND`, `OR`, `NOT` must be uppercase so that ordinary words like "and" still work.

## Ranking

`score(d, q) = sum over query terms t of (1 + log10 tf(t,d)) * log10(1 + N / df(t)) / sqrt(|d|)`
Terms under `NOT` do not contribute to the score.

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import QuerySyntaxError, build_engine_from_documents
from engine.document_loader import Document
from engine.normalizer import Normalizer
from engine.tokenizer import tokenize


def make_engine():
    texts = [
        "Title one\n\nThe Café network uses TCP and UDP.",
        "Title two\n\nVirtual memory and paging in the network stack.",
        "Title three\n\nRouting, routers and routes: no memory here.",
    ]
    docs = [Document(i, t.split("\n")[0], Path(f"d{i}.txt"), t) for i, t in enumerate(texts, 1)]
    return build_engine_from_documents(docs)


def ids(result):
    return sorted(h.doc_id for h in result.hits)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()

    def test_tokenizer_and_normalizer(self):
        self.assertEqual(tokenize("Don't stop, café!"), ["Don't", "stop", "café"])
        self.assertEqual(Normalizer().normalize(["Café", "NETWORK", "it's"]), ["cafe", "network", "it"])

    def test_case_and_accent_folding(self):
        self.assertEqual(ids(self.engine.search("CAFE")), [1])

    def test_boolean_operators(self):
        self.assertEqual(ids(self.engine.search("network AND memory")), [2])
        self.assertEqual(ids(self.engine.search("tcp OR paging")), [1, 2])
        self.assertEqual(ids(self.engine.search("network NOT memory")), [1])
        self.assertEqual(ids(self.engine.search("network memory")), [2])          # implicit AND
        self.assertEqual(ids(self.engine.search("(tcp OR paging) AND network")), [1, 2])

    def test_phrase(self):
        self.assertEqual(ids(self.engine.search('"virtual memory"')), [2])
        self.assertEqual(ids(self.engine.search('"memory virtual"')), [])

    def test_wildcards(self):
        self.assertEqual(self.engine.search("rout*").expansions["rout*"], ["routers", "routes", "routing"])
        self.assertEqual(self.engine.search("*ing").expansions["*ing"], ["paging", "routing"])
        self.assertEqual(self.engine.search("m?mory").expansions["m?mory"], ["memory"])
        self.assertEqual(self.engine.search("n*k").expansions["n*k"], ["network"])
        self.assertEqual(self.engine.search("zz*").expansions["zz*"], [])

    def test_ranking_prefers_more_relevant_document(self):
        hits = self.engine.search("memory").hits
        self.assertEqual(len(hits), 2)
        self.assertGreaterEqual(hits[0].score, hits[1].score)

    def test_syntax_errors(self):
        for bad in ("", "(tcp", "tcp AND", '"unclosed', "OR tcp", '"mem*"'):
            with self.assertRaises(QuerySyntaxError, msg=bad):
                self.engine.search(bad)

    def test_snippet_highlights_match(self):
        hit = self.engine.search("paging").hits[0]
        s, e = hit.snippet.spans[0]
        self.assertEqual(hit.snippet.text[s:e].lower(), "paging")


if __name__ == "__main__":
    unittest.main()

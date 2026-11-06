"""Module 7 - Frontend GUI (Tkinter, no third-party packages).

Look: a deep-sea sidebar that reports what the index knows, and a mist-blue
workspace holding a pill-shaped search bar and a read-only result sheet.
Matches are marked in saffron and each result carries a relevance meter.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, ttk

from engine import QuerySyntaxError, SearchEngine, SearchResult, build_engine

C = {
    "mist": "#E8EEF0",       # workspace background
    "panel": "#FBFCFC",      # search bar + result sheet
    "ink": "#12263A",        # main text, sidebar
    "slate": "#5C7184",      # secondary text
    "line": "#D5DFE3",       # hairlines, empty meter
    "chip": "#D9E5E8",
    "chip_hover": "#C7D9DD",
    "ring": "#A9BBC6",
    "verdigris": "#1F7A72",  # action + meter
    "verdigris_dark": "#165E58",
    "saffron": "#F6C453",    # match highlight
    "danger": "#A93B2B",
    "side_text": "#CBD8E2",
    "side_dim": "#8AA0B3",
    "side_line": "#264460",
}

EXAMPLES = ['network AND (tcp OR udp)', '"virtual memory"', "rout*", "*ing NOT page"]
PLACEHOLDER = 'Search words, "phrases", or wildcards like net*'
SIDEBAR_WIDTH = 290
METER_CELLS = 10


def _pick(available: set[str], candidates: list[str], fallback: str) -> str:
    return next((name for name in candidates if name in available), fallback)


def rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class SearchPill(tk.Canvas):
    """Rounded search bar: input box on the left, Search button inside on the right."""

    HEIGHT = 64
    BUTTON_W = 132

    def __init__(self, master, on_submit, fonts) -> None:
        super().__init__(master, height=self.HEIGHT, bg=C["mist"], highlightthickness=0, bd=0)
        self.on_submit = on_submit
        self.fonts = fonts
        self._placeholder = True
        self._shell = self._button = self._label = None

        self.entry = tk.Entry(self, bd=0, relief="flat", font=fonts["input"], bg=C["panel"],
                              fg=C["slate"], insertbackground=C["ink"], highlightthickness=0)
        self.entry.insert(0, PLACEHOLDER)
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<Return>", lambda _e: self.on_submit())
        self._window = self.create_window(0, 0, window=self.entry, anchor="w")

        self.tag_bind("hit", "<Button-1>", lambda _e: self.on_submit())
        self.tag_bind("hit", "<Enter>", lambda _e: self._hover(True))
        self.tag_bind("hit", "<Leave>", lambda _e: self._hover(False))
        self.bind("<Configure>", lambda _e: self._draw())

    # -- drawing ----------------------------------------------------------
    def _draw(self) -> None:
        w, h = max(self.winfo_width(), 300), self.HEIGHT
        self.delete("shape")
        self._shell = rounded_rect(self, 2, 2, w - 2, h - 2, 30, fill=C["panel"],
                                   outline=C["ring"], width=2, tags="shape")
        bx1, by1, bx2, by2 = w - self.BUTTON_W - 9, 9, w - 9, h - 9
        self._button = rounded_rect(self, bx1, by1, bx2, by2, 22, fill=C["verdigris"],
                                    outline="", tags=("shape", "hit"))
        self._label = self.create_text((bx1 + bx2) // 2, h // 2, text="Search", fill="white",
                                       font=self.fonts["button"], tags=("shape", "hit"))
        self.coords(self._window, 30, h // 2)
        self.itemconfigure(self._window, width=w - self.BUTTON_W - 60)

    def _hover(self, inside: bool) -> None:
        self.config(cursor="hand2" if inside else "")
        self.itemconfigure(self._button, fill=C["verdigris_dark"] if inside else C["verdigris"])

    # -- placeholder + focus ring ------------------------------------------
    def _focus_in(self, _e=None) -> None:
        if self._placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=C["ink"])
            self._placeholder = False
        self.itemconfigure(self._shell, outline=C["verdigris"])

    def _focus_out(self, _e=None) -> None:
        if not self.entry.get():
            self.entry.insert(0, PLACEHOLDER)
            self.entry.config(fg=C["slate"])
            self._placeholder = True
        self.itemconfigure(self._shell, outline=C["ring"])

    # -- public -----------------------------------------------------------
    def get_query(self) -> str:
        return "" if self._placeholder else self.entry.get()

    def set_query(self, text: str) -> None:
        self._placeholder = False
        self.entry.config(fg=C["ink"])
        self.entry.delete(0, "end")
        self.entry.insert(0, text)


class SearchApp(tk.Tk):
    def __init__(self, data_dir: str | Path) -> None:
        super().__init__()
        self.title("Lexicon - document search")
        self.geometry("1140x740")
        self.minsize(900, 580)
        self.configure(bg=C["mist"])
        self.engine: SearchEngine | None = None
        self.data_dir = Path(data_dir)

        self._init_fonts()
        self._init_style()
        self._build_sidebar()
        self._build_workspace()
        self._load_corpus(self.data_dir)

    # ------------------------------------------------------------------ setup
    def _init_fonts(self) -> None:
        have = set(tkfont.families(self))
        serif = _pick(have, ["Iowan Old Style", "Palatino Linotype", "Palatino", "Georgia",
                             "DejaVu Serif", "Times New Roman"], "Times")
        sans = _pick(have, ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans",
                            "DejaVu Sans", "Arial"], "Helvetica")
        mono = _pick(have, ["Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono",
                            "Courier New"], "Courier")
        self.f = {
            "brand": (serif, 32, "bold"), "h1": (serif, 25, "bold"),
            "result_title": (serif, 16, "bold"), "rank": (serif, 20, "bold"),
            "body": (sans, 11), "small": (sans, 10), "small_bold": (sans, 10, "bold"),
            "side_head": (sans, 10, "bold"), "side_value": (sans, 11),
            "input": (sans, 15), "button": (sans, 13, "bold"),
            "snippet": (serif, 13), "meter": (mono, 10), "tiny": (sans, 1),
        }

    def _init_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Lex.Vertical.TScrollbar", background=C["line"], troughcolor=C["panel"],
                        bordercolor=C["panel"], lightcolor=C["line"], darkcolor=C["line"],
                        arrowcolor=C["slate"], gripcount=0, relief="flat")
        style.map("Lex.Vertical.TScrollbar", background=[("active", C["ring"])])

    # ---------------------------------------------------------------- sidebar
    def _build_sidebar(self) -> None:
        side = tk.Frame(self, bg=C["ink"], width=SIDEBAR_WIDTH)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        pad = {"padx": 28, "anchor": "w"}

        tk.Label(side, text="Lexicon", font=self.f["brand"], fg="white", bg=C["ink"]).pack(pady=(34, 2), **pad)
        tk.Label(side, text="Search your own documents with Boolean, phrase and wildcard queries.",
                 font=self.f["small"], fg=C["side_text"], bg=C["ink"], wraplength=SIDEBAR_WIDTH - 56,
                 justify="left").pack(**pad)
        self._divider(side)

        tk.Label(side, text="Library", font=self.f["side_head"], fg=C["side_dim"], bg=C["ink"]).pack(pady=(0, 8), **pad)
        self.var_docs, self.var_terms, self.var_postings = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self._kv(side, "Documents", self.var_docs)
        self._kv(side, "Distinct terms", self.var_terms)
        self._kv(side, "Postings", self.var_postings)
        self.var_folder = tk.StringVar()
        tk.Label(side, textvariable=self.var_folder, font=self.f["small"], fg=C["side_text"], bg=C["ink"],
                 wraplength=SIDEBAR_WIDTH - 56, justify="left").pack(pady=(8, 0), **pad)
        change = tk.Label(side, text="Choose another folder", font=self.f["small_bold"], fg=C["saffron"],
                          bg=C["ink"], cursor="hand2")
        change.pack(pady=(4, 0), **pad)
        change.bind("<Button-1>", lambda _e: self._choose_folder())
        self._divider(side)

        tk.Label(side, text="Last search", font=self.f["side_head"], fg=C["side_dim"], bg=C["ink"]).pack(pady=(0, 8), **pad)
        self.var_plan, self.var_expand, self.var_found = tk.StringVar(value="-"), tk.StringVar(value="-"), tk.StringVar(value="-")
        for title, var in (("Understood as", self.var_plan), ("Wildcards expanded", self.var_expand),
                           ("Result", self.var_found)):
            tk.Label(side, text=title, font=self.f["small"], fg=C["side_dim"], bg=C["ink"]).pack(pady=(6, 0), **pad)
            tk.Label(side, textvariable=var, font=self.f["side_value"], fg="white", bg=C["ink"],
                     wraplength=SIDEBAR_WIDTH - 56, justify="left").pack(**pad)

        tk.Label(side, text='AND, OR, NOT in capitals   "exact phrase"   * any letters   ? one letter',
                 font=self.f["small"], fg=C["side_dim"], bg=C["ink"], wraplength=SIDEBAR_WIDTH - 56,
                 justify="left").pack(side="bottom", pady=(0, 26), **pad)

    def _divider(self, parent) -> None:
        tk.Frame(parent, bg=C["side_line"], height=1).pack(fill="x", padx=28, pady=22)

    def _kv(self, parent, key: str, var: tk.StringVar) -> None:
        row = tk.Frame(parent, bg=C["ink"])
        row.pack(fill="x", padx=28, pady=1)
        tk.Label(row, text=key, font=self.f["small"], fg=C["side_dim"], bg=C["ink"]).pack(side="left")
        tk.Label(row, textvariable=var, font=self.f["small_bold"], fg="white", bg=C["ink"]).pack(side="right")

    # -------------------------------------------------------------- workspace
    def _build_workspace(self) -> None:
        main = tk.Frame(self, bg=C["mist"])
        main.pack(side="left", fill="both", expand=True, padx=40, pady=(34, 28))

        tk.Label(main, text="What are you looking for?", font=self.f["h1"], fg=C["ink"],
                 bg=C["mist"]).pack(anchor="w")
        tk.Label(main, text="Results are ranked by TF-IDF and every match is highlighted in context.",
                 font=self.f["body"], fg=C["slate"], bg=C["mist"]).pack(anchor="w", pady=(2, 18))

        self.pill = SearchPill(main, self.run_search, self.f)
        self.pill.pack(fill="x")

        chips = tk.Frame(main, bg=C["mist"])
        chips.pack(fill="x", pady=(14, 0))
        tk.Label(chips, text="Try", font=self.f["small"], fg=C["slate"], bg=C["mist"]).pack(side="left", padx=(4, 8))
        for example in EXAMPLES:
            chip = tk.Label(chips, text=example, font=self.f["small"], fg=C["ink"], bg=C["chip"],
                            padx=12, pady=5, cursor="hand2")
            chip.pack(side="left", padx=(0, 8))
            chip.bind("<Enter>", lambda _e, w=chip: w.config(bg=C["chip_hover"]))
            chip.bind("<Leave>", lambda _e, w=chip: w.config(bg=C["chip"]))
            chip.bind("<Button-1>", lambda _e, q=example: self._run_example(q))

        self.var_status = tk.StringVar()
        self.status = tk.Label(main, textvariable=self.var_status, font=self.f["small_bold"],
                               fg=C["slate"], bg=C["mist"], anchor="w")
        self.status.pack(fill="x", pady=(20, 8), padx=4)

        sheet = tk.Frame(main, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
        sheet.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(sheet, orient="vertical", style="Lex.Vertical.TScrollbar")
        scroll.pack(side="right", fill="y")
        self.results = tk.Text(sheet, wrap="word", bd=0, relief="flat", bg=C["panel"], fg=C["ink"],
                               padx=32, pady=10, cursor="arrow", highlightthickness=0,
                               yscrollcommand=scroll.set, tabs=("52",), spacing3=2,
                               selectbackground=C["chip_hover"], selectforeground=C["ink"])
        self.results.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.results.yview)
        self._configure_tags()
        self.results.config(state="disabled")          # read-only result area

    def _configure_tags(self) -> None:
        t, f = self.results, self.f
        t.tag_configure("rank", font=f["rank"], foreground=C["verdigris"], spacing1=20, lmargin1=0, lmargin2=52)
        t.tag_configure("title", font=f["result_title"], foreground=C["ink"], spacing1=20, lmargin1=0, lmargin2=52)
        t.tag_configure("meta_line", lmargin1=52, lmargin2=52, spacing1=4)
        t.tag_configure("meter_on", font=f["meter"], foreground=C["verdigris"])
        t.tag_configure("meter_off", font=f["meter"], foreground=C["line"])
        t.tag_configure("meta", font=f["small"], foreground=C["slate"])
        t.tag_configure("snippet", font=f["snippet"], foreground=C["ink"], lmargin1=52, lmargin2=52,
                        spacing1=6, spacing2=4)
        t.tag_configure("hit", background=C["saffron"], foreground=C["ink"])
        try:   # keep a highlight at the start of a line from bleeding into the margin
            for tag in ("snippet", "meta_line", "title", "rank"):
                t.tag_configure(tag, lmargincolor=C["panel"])
        except tk.TclError:
            pass   # older Tk: cosmetic only
        t.tag_configure("rule", font=f["tiny"], background=C["line"], lmargin1=0, spacing1=0, spacing3=0)
        t.tag_configure("note_title", font=f["result_title"], foreground=C["ink"], spacing1=24)
        t.tag_configure("note", font=f["body"], foreground=C["slate"], spacing1=6, spacing2=3)
        t.tag_configure("error_title", font=f["result_title"], foreground=C["danger"], spacing1=24)
        t.tag_configure("code", font=f["meter"], foreground=C["verdigris_dark"])

    # ------------------------------------------------------------------ corpus
    def _load_corpus(self, folder: Path) -> bool:
        try:
            engine = build_engine(folder)
        except (FileNotFoundError, ValueError) as err:
            self._show_error(str(err))
            return False
        self.engine, self.data_dir = engine, folder
        self.var_docs.set(f"{engine.index.document_count:,}")
        self.var_terms.set(f"{engine.index.term_count:,}")
        self.var_postings.set(f"{engine.index.posting_count:,}")
        self.var_folder.set(f"Reading from {folder.name or folder}")
        self._show_welcome()
        return True

    def _choose_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Choose a folder of .txt or .md files",
                                         initialdir=str(self.data_dir))
        if chosen:
            self._load_corpus(Path(chosen))

    # ------------------------------------------------------------------ search
    def _run_example(self, query: str) -> None:
        self.pill.set_query(query)
        self.run_search()

    def run_search(self) -> None:
        if self.engine is None:
            return
        query = self.pill.get_query().strip()
        if not query:
            self._set_status("Type something to search for.", error=True)
            return
        try:
            result = self.engine.search(query)
        except QuerySyntaxError as err:
            self._show_error(str(err))
            return
        self._render(result)

    # --------------------------------------------------------------- rendering
    def _set_status(self, text: str, error: bool = False) -> None:
        self.var_status.set(text)
        self.status.config(fg=C["danger"] if error else C["slate"])

    def _begin(self) -> None:
        self.results.config(state="normal")
        self.results.delete("1.0", "end")

    def _end(self) -> None:
        self.results.config(state="disabled")
        self.results.yview_moveto(0)

    def _render(self, r: SearchResult) -> None:
        t = self.results
        noun = "document" if r.total == 1 else "documents"
        self._set_status(f"{r.total} {noun} match  -  {r.elapsed_ms:.1f} ms")
        self.var_plan.set(r.plan)
        self.var_found.set(f"{r.total} {noun}, {r.elapsed_ms:.1f} ms")
        self.var_expand.set(self._expansion_summary(r))

        self._begin()
        if not r.hits:
            t.insert("end", "No document matches this query\n", "note_title")
            hint = "Check the spelling, drop a term, or use a wildcard such as net* to widen the search."
            if r.expansions and not any(r.expansions.values()):
                hint = "No indexed term fits your wildcard pattern. Try a shorter prefix or suffix."
            t.insert("end", hint + "\n", "note")
            self._end()
            return

        for rank, hit in enumerate(r.hits, 1):
            if rank > 1:
                t.insert("end", " \n", "rule")
            t.insert("end", f"{rank}\t", "rank")
            t.insert("end", hit.title + "\n", "title")

            t.insert("end", "", "meta_line")
            if hit.score > 0:
                filled = max(1, round(hit.relevance * METER_CELLS))
                t.insert("end", "█" * filled, ("meta_line", "meter_on"))
                t.insert("end", "░" * (METER_CELLS - filled), ("meta_line", "meter_off"))
                t.insert("end", f"  score {hit.score:.2f}   ", ("meta_line", "meta"))
            else:
                t.insert("end", "unranked   ", ("meta_line", "meta"))
            t.insert("end", hit.filename + "\n", ("meta_line", "meta"))

            text, cursor = hit.snippet.text, 0
            for start, end in hit.snippet.spans:
                if start < cursor:
                    continue
                t.insert("end", text[cursor:start], "snippet")
                t.insert("end", text[start:end], ("snippet", "hit"))
                cursor = end
            t.insert("end", text[cursor:] + "\n", "snippet")
        self._end()

    @staticmethod
    def _expansion_summary(r: SearchResult) -> str:
        if not r.expansions:
            return "none in this query"
        lines = []
        for word, terms in r.expansions.items():
            shown = ", ".join(terms[:6]) + (f" and {len(terms) - 6} more" if len(terms) > 6 else "")
            lines.append(f"{word}: {shown or 'no matching terms'}")
        return "\n".join(lines)

    def _show_welcome(self) -> None:
        n = self.engine.index.document_count if self.engine else 0
        self._set_status("")
        self._begin()
        t = self.results
        t.insert("end", f"{n} documents are indexed and ready\n", "note_title")
        t.insert("end", "Type a query above or pick one of the examples. Each result shows a snippet "
                        "with your matches highlighted.\n", "note")
        for syntax, meaning in (('network AND tcp', "documents containing both words"),
                                ('tcp OR udp', "documents containing either word"),
                                ('paging NOT virtual', "paging, but without the word virtual"),
                                ('"page table"', "the exact phrase, words side by side"),
                                ('net*  *ing  n?twork', "wildcards: any letters, or exactly one")):
            t.insert("end", f"{syntax}", "code")
            t.insert("end", f"   {meaning}\n", "note")
        self._end()

    def _show_error(self, message: str) -> None:
        self._set_status("That query could not be run", error=True)
        self._begin()
        self.results.insert("end", "Fix the query and search again\n", "error_title")
        self.results.insert("end", message + "\n", "note")
        self._end()

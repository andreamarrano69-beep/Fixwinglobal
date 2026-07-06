"""Finestra principale dell'applicazione: sidebar di navigazione e gestione delle pagine."""
from __future__ import annotations

import datetime
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional, Set

from core.catalog import default_selected_ids
from core.engine import DiagnosticEngine
from core.models import CheckResult
from gui.pages.dashboard import DashboardPage
from gui.pages.results import ResultsPage
from gui.pages.selection import SelectionPage
from gui.theme import apply_theme

NAV_ITEMS = [
    ("dashboard", "🏠", "Dashboard"),
    ("selection", "🧩", "Seleziona controlli"),
    ("results", "📋", "Risultati"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PC Diagnostic Tool")
        self.geometry("1180x720")
        self.minsize(980, 620)
        apply_theme(self)

        self.engine = DiagnosticEngine()
        self.selected_ids: Set[str] = set(default_selected_ids())
        self.results: Dict[str, CheckResult] = {}
        self.last_score = 0
        self.last_scan_time: Optional[datetime.datetime] = None

        self._scan_queue: "queue.Queue" = queue.Queue()
        self._scan_thread: Optional[threading.Thread] = None
        self._scan_stop_flag = False

        self._build_layout()
        self.show_page("dashboard")

    # ------------------------------------------------------------------ layout
    def _build_layout(self):
        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True)

        sidebar = ttk.Frame(container, style="Sidebar.TFrame", width=230)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(22, 26, 22, 18))
        brand.pack(fill="x")
        ttk.Label(brand, text="🛠  PC Diagnostic", style="SidebarBrand.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Analisi completa del sistema", style="SidebarMuted.TLabel").pack(anchor="w", pady=(2, 0))

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=16, pady=(0, 10))

        self._nav_buttons = {}
        nav_holder = ttk.Frame(sidebar, style="Sidebar.TFrame")
        nav_holder.pack(fill="x", padx=12)
        for key, icon, label in NAV_ITEMS:
            btn = ttk.Button(nav_holder, text=f"  {icon}   {label}", style="Nav.TButton",
                              command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", pady=3)
            self._nav_buttons[key] = btn

        footer = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(22, 12))
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, text="v1.0 · Uso personale", style="SidebarMuted.TLabel").pack(anchor="w")

        self.content = ttk.Frame(container, style="TFrame")
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {
            "dashboard": DashboardPage(self.content, self),
            "selection": SelectionPage(self.content, self),
            "results": ResultsPage(self.content, self),
        }
        for page in self.pages.values():
            page.place(relwidth=1, relheight=1)

    def show_page(self, name: str):
        for key, btn in self._nav_buttons.items():
            btn.configure(style="NavActive.TButton" if key == name else "Nav.TButton")
        page = self.pages[name]
        if hasattr(page, "refresh"):
            page.refresh()
        page.lift()

    # ------------------------------------------------------------------ scan
    def quick_scan(self):
        self.show_page("selection")
        self.after(150, self.pages["selection"]._start_scan)

    def start_scan(self, on_row_done: Callable, on_progress: Callable, on_finished: Callable):
        self._scan_stop_flag = False
        selected = list(self.selected_ids)

        def worker():
            def progress_cb(index, total, label):
                self._scan_queue.put(("progress", index, total, label))

            def stop_check():
                return self._scan_stop_flag

            results = self.engine.run_checks(selected, on_progress=progress_cb, should_stop=stop_check)
            self._scan_queue.put(("done", results))

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()
        self._poll_scan_queue(on_row_done, on_progress, on_finished)

    def _poll_scan_queue(self, on_row_done, on_progress, on_finished):
        try:
            while True:
                item = self._scan_queue.get_nowait()
                if item[0] == "progress":
                    _, index, total, label = item
                    on_progress(index, total, label)
                elif item[0] == "done":
                    _, results = item
                    self.results = results
                    self.last_score = self.engine.compute_health_score(results)
                    self.last_scan_time = datetime.datetime.now()
                    for r in results.values():
                        on_row_done(r)
                    on_finished()
                    self.pages["dashboard"].refresh()
                    self.pages["results"].refresh()
                    return
        except queue.Empty:
            pass
        self.after(80, lambda: self._poll_scan_queue(on_row_done, on_progress, on_finished))


def run():
    app = App()
    app.mainloop()

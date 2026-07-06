"""Pagina di selezione dei controlli da eseguire, suddivisi per categoria."""
from __future__ import annotations

from tkinter import ttk

from core.catalog import CATEGORIES
from gui.widgets import CheckRow, ScrollableFrame, SectionHeader


class SelectionPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame", padding=(28, 24))
        self.app = app
        self.rows = {}

        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Seleziona i controlli", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Scegli quali verifiche eseguire su hardware, software e problemi potenziali.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        toolbar = ttk.Frame(self, style="TFrame")
        toolbar.pack(fill="x", pady=(16, 10))
        ttk.Button(toolbar, text="Seleziona tutto", style="TButton",
                   command=self._select_all).pack(side="left")
        ttk.Button(toolbar, text="Deseleziona tutto", style="TButton",
                   command=self._deselect_all).pack(side="left", padx=(8, 0))
        self.selected_count_label = ttk.Label(toolbar, text="", style="Subtitle.TLabel")
        self.selected_count_label.pack(side="left", padx=(16, 0))

        self.run_button = ttk.Button(toolbar, text="▶  Avvia scansione", style="Accent.TButton",
                                      command=self._start_scan)
        self.run_button.pack(side="right")

        self.progress_frame = ttk.Frame(self, style="TFrame")
        self.progress = ttk.Progressbar(self.progress_frame, mode="determinate")
        self.progress.pack(fill="x")
        self.progress_label = ttk.Label(self.progress_frame, text="", style="Subtitle.TLabel")
        self.progress_label.pack(anchor="w", pady=(4, 0))

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True, pady=(14, 0))
        content = scroll.inner

        for cat in CATEGORIES:
            SectionHeader(content, cat.icon, cat.label,
                          on_toggle_all=lambda v, c=cat: self._toggle_category(c, v)).pack(
                fill="x", pady=(18, 8))
            for meta in cat.checks:
                row = CheckRow(content, meta.id, meta.label, meta.description,
                                initial=meta.id in app.selected_ids, on_toggle=self._on_row_toggle)
                row.pack(fill="x", pady=4)
                self.rows[meta.id] = row

        self._update_count()

    def _on_row_toggle(self, check_id: str, value: bool):
        if value:
            self.app.selected_ids.add(check_id)
        else:
            self.app.selected_ids.discard(check_id)
        self._update_count()

    def _toggle_category(self, category, value: bool):
        for meta in category.checks:
            self.rows[meta.id].set_selected(value)
            if value:
                self.app.selected_ids.add(meta.id)
            else:
                self.app.selected_ids.discard(meta.id)
        self._update_count()

    def _select_all(self):
        for cat in CATEGORIES:
            self._toggle_category(cat, True)

    def _deselect_all(self):
        for cat in CATEGORIES:
            self._toggle_category(cat, False)

    def _update_count(self):
        total = sum(len(cat.checks) for cat in CATEGORIES)
        self.selected_count_label.configure(
            text=f"{len(self.app.selected_ids)} di {total} controlli selezionati")

    def _start_scan(self):
        if not self.app.selected_ids:
            self.selected_count_label.configure(text="Seleziona almeno un controllo per procedere")
            return
        for row in self.rows.values():
            for w in row.status_holder.winfo_children():
                w.destroy()
        self.run_button.configure(state="disabled")
        self.progress_frame.pack(fill="x", pady=(6, 0))
        self.progress.configure(maximum=len(self.app.selected_ids), value=0)
        self.app.start_scan(on_row_done=self._on_row_done, on_progress=self._on_progress,
                             on_finished=self._on_finished)

    def _on_progress(self, index, total, label):
        self.progress.configure(value=index, maximum=total)
        self.progress_label.configure(text=f"Controllo {index}/{total}: {label}")

    def _on_row_done(self, result):
        row = self.rows.get(result.check_id)
        if row:
            row.show_status(result.status.value, result.status.label)

    def _on_finished(self):
        self.run_button.configure(state="normal")
        self.progress_label.configure(text="Scansione completata.")
        self.app.show_page("results")

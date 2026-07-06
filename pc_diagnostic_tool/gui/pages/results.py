"""Pagina dei risultati: albero dei controlli eseguiti, dettagli, consigli, fix ed esportazione report."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.advisor import get_advisory
from core.catalog import CATEGORIES
from core.models import CheckResult, FixAction, FixOutcome, Status
from gui.theme import Palette
from gui.widgets import FixRow, ScrollableFrame, SuggestionCard, Toast


class ResultsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame", padding=(28, 24))
        self.app = app

        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x")
        left_header = ttk.Frame(header, style="TFrame")
        left_header.pack(side="left", fill="x", expand=True)
        ttk.Label(left_header, text="Risultati", style="Title.TLabel").pack(anchor="w")
        self.subtitle = ttk.Label(left_header, text="Nessuna scansione eseguita ancora.", style="Subtitle.TLabel")
        self.subtitle.pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(header, style="TFrame")
        actions.pack(side="right")
        ttk.Button(actions, text="Esporta TXT", style="TButton",
                   command=lambda: self._export("txt")).pack(side="left")
        ttk.Button(actions, text="Esporta HTML", style="Accent.TButton",
                   command=lambda: self._export("html")).pack(side="left", padx=(8, 0))

        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True, pady=(18, 0))

        tree_frame = ttk.Frame(body, style="Panel.TFrame", padding=4)
        tree_frame.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("status",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Controllo")
        self.tree.heading("status", text="Stato")
        self.tree.column("status", width=150, anchor="w")
        self.tree.column("#0", width=340)
        vbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        for status in Status:
            self.tree.tag_configure(status.value, foreground=Palette.status_color(status.value))
        self.tree.tag_configure("category", font=(None, 10, "bold"))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail = ttk.Frame(body, style="Panel.TFrame", padding=18)
        detail.pack(side="left", fill="both", expand=True, padx=(16, 0))

        detail_head = ttk.Frame(detail, style="Panel.TFrame")
        detail_head.pack(fill="x")
        title_col = ttk.Frame(detail_head, style="Panel.TFrame")
        title_col.pack(side="left", fill="x", expand=True)
        self.detail_title = ttk.Label(title_col, text="Seleziona un controllo per vedere i dettagli",
                                       style="CardTitle.TLabel", font=(None, 12, "bold"), wraplength=300)
        self.detail_title.pack(anchor="w", fill="x")
        self.recheck_btn = ttk.Button(detail_head, text="🔄 Ricontrolla", style="TButton",
                                       command=self._recheck_current, state="disabled")
        self.recheck_btn.pack(side="right", anchor="n")

        self.detail_summary = ttk.Label(detail, text="", style="PanelMuted.TLabel", wraplength=380, justify="left")
        self.detail_summary.pack(anchor="w", pady=(8, 10), fill="x")

        self.notebook = ttk.Notebook(detail)
        self.notebook.pack(fill="both", expand=True)

        details_tab = tk.Frame(self.notebook, bg=Palette.panel)
        self.notebook.add(details_tab, text="Dettagli")
        text_frame = tk.Frame(details_tab, bg=Palette.panel)
        text_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.detail_text = tk.Text(text_frame, bg=Palette.bg_soft, fg=Palette.text, relief="flat",
                                    wrap="word", padx=12, pady=10, font=(None, 10), state="disabled",
                                    insertbackground=Palette.text)
        detail_vbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_vbar.set)
        self.detail_text.pack(side="left", fill="both", expand=True)
        detail_vbar.pack(side="right", fill="y")

        advisory_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(advisory_tab, text="Consigli e fix")
        self.advisory_scroll = ScrollableFrame(advisory_tab, bg=Palette.panel)
        self.advisory_scroll.pack(fill="both", expand=True, pady=(10, 0))

        self._result_by_iid = {}
        self._iid_by_check_id = {}
        self._current_check_id = None

    # ------------------------------------------------------------------ popolamento albero
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._result_by_iid.clear()
        self._iid_by_check_id.clear()
        results = self.app.results

        if not results:
            self.subtitle.configure(text="Nessuna scansione eseguita ancora.")
            return

        self.subtitle.configure(
            text=f"Ultima scansione: {self.app.last_scan_time.strftime('%d/%m/%Y %H:%M')} · "
                 f"Punteggio di salute: {self.app.last_score}/100")

        for cat in CATEGORIES:
            cat_results = [(meta, results[meta.id]) for meta in cat.checks if meta.id in results]
            if not cat_results:
                continue
            cat_iid = self.tree.insert("", "end", text=f"{cat.icon}  {cat.label}", values=("",), open=True,
                                        tags=("category",))
            for meta, result in cat_results:
                iid = self.tree.insert(cat_iid, "end", text=result.title,
                                        values=(f"{result.status.icon} {result.status.label}",),
                                        tags=(result.status.value,))
                self._result_by_iid[iid] = result
                self._iid_by_check_id[result.check_id] = iid

    def _update_tree_item(self, result: CheckResult):
        iid = self._iid_by_check_id.get(result.check_id)
        if not iid:
            return
        self.tree.item(iid, values=(f"{result.status.icon} {result.status.label}",), tags=(result.status.value,))
        self._result_by_iid[iid] = result

    # ------------------------------------------------------------------ selezione e dettagli
    def _on_select(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        result = self._result_by_iid.get(selection[0])
        if not result:
            return
        self._show_result(result)

    def _show_result(self, result: CheckResult):
        self._current_check_id = result.check_id
        self.recheck_btn.configure(state="normal")
        self.detail_title.configure(text=result.title)
        self.detail_summary.configure(text=f"{result.status.icon} {result.summary}")
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", "\n".join(result.details) if result.details else "Nessun dettaglio aggiuntivo.")
        self.detail_text.configure(state="disabled")
        self._render_advisory(result)

    def _render_advisory(self, result: CheckResult):
        for widget in self.advisory_scroll.inner.winfo_children():
            widget.destroy()

        suggestions, fixes = get_advisory(result)
        content = self.advisory_scroll.inner

        if not suggestions and not fixes:
            ttk.Label(content, text="Nessun suggerimento per questo controllo: risulta a posto.",
                      style="PanelMuted.TLabel", wraplength=380, justify="left").pack(anchor="w", pady=10, padx=4)
            return

        if suggestions:
            ttk.Label(content, text="💡 Suggerimenti", style="Title.TLabel",
                      font=(None, 11, "bold")).pack(anchor="w", pady=(4, 8))
            for s in suggestions:
                SuggestionCard(content, s.icon, s.title, s.text).pack(fill="x", pady=4)

        if fixes:
            ttk.Label(content, text="🔧 Correzioni disponibili", style="Title.TLabel",
                      font=(None, 11, "bold")).pack(anchor="w", pady=(16, 8))
            for fix in fixes:
                row = FixRow(content, fix.label, fix.risk, fix.description,
                             on_apply=lambda _row, f=fix: self._confirm_and_apply(f, _row))
                row.pack(fill="x", pady=4)

    # ------------------------------------------------------------------ fix
    def _confirm_and_apply(self, fix: FixAction, row: FixRow):
        warning = "\n\n⚠ Questa operazione potrebbe non essere reversibile." if fix.risk == "caution" else ""
        confirmed = messagebox.askyesno(
            "Conferma correzione",
            f"{fix.label}\n\n{fix.description}{warning}\n\nProcedere?",
            icon="warning" if fix.risk == "caution" else "question",
        )
        if not confirmed:
            return
        row.set_busy()

        def on_outcome(outcome: FixOutcome):
            row.set_result(outcome.success, outcome.message)
            Toast(self.app, outcome.message, kind="success" if outcome.success else "error")
            if self._current_check_id:
                self.app.recheck_single(self._current_check_id, self._on_recheck_done)

        self.app.run_fix(fix, on_outcome)

    def _recheck_current(self):
        if not self._current_check_id:
            return
        self.recheck_btn.configure(state="disabled", text="Verifica in corso...")
        self.app.recheck_single(self._current_check_id, self._on_recheck_done)

    def _on_recheck_done(self, result: CheckResult):
        self.recheck_btn.configure(state="normal", text="🔄 Ricontrolla")
        self._update_tree_item(result)
        self.subtitle.configure(
            text=f"Ultima scansione: {self.app.last_scan_time.strftime('%d/%m/%Y %H:%M')} · "
                 f"Punteggio di salute: {self.app.last_score}/100")
        if self._current_check_id == result.check_id:
            self._show_result(result)

    # ------------------------------------------------------------------ esportazione
    def _export(self, fmt: str):
        if not self.app.results:
            Toast(self.app, "Esegui prima una scansione", kind="warning")
            return
        ext = ".txt" if fmt == "txt" else ".html"
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("Testo", "*.txt")] if fmt == "txt" else [("HTML", "*.html")],
            initialfile=f"report_diagnostico{ext}",
        )
        if not path:
            return
        content = (self.app.engine.generate_text_report(self.app.results, self.app.last_score) if fmt == "txt"
                   else self.app.engine.generate_html_report(self.app.results, self.app.last_score))
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        Toast(self.app, f"Report salvato in {path}", kind="success")

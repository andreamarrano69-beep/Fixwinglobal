"""Pagina Dashboard: panoramica rapida dello stato del sistema."""
from __future__ import annotations

import platform
from tkinter import ttk

from core.models import Status
from gui.theme import Palette
from gui.widgets import ScoreGauge, StatCard


class DashboardPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame", padding=28)
        self.app = app

        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Dashboard", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text=f"{platform.system()} {platform.release()} · {platform.node()}",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True, pady=(24, 0))

        left = ttk.Frame(body, style="Panel.TFrame", padding=24)
        left.pack(side="left", fill="y", padx=(0, 20))
        ttk.Label(left, text="Punteggio di salute", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))
        self.gauge = ScoreGauge(left, size=170)
        self.gauge.pack()
        self.last_scan_label = ttk.Label(left, text="Nessuna scansione eseguita", style="PanelMuted.TLabel")
        self.last_scan_label.pack(pady=(14, 0))

        right = ttk.Frame(body, style="TFrame")
        right.pack(side="left", fill="both", expand=True)

        cards_row = ttk.Frame(right, style="TFrame")
        cards_row.pack(fill="x")
        self.card_ok = StatCard(cards_row, "✅", "OK", "–", accent=Palette.success)
        self.card_warn = StatCard(cards_row, "⚠", "Avvisi", "–", accent=Palette.warning)
        self.card_crit = StatCard(cards_row, "✖", "Critici", "–", accent=Palette.critical)
        self.card_total = StatCard(cards_row, "🧾", "Totale", "–", accent=Palette.info)
        for i, card in enumerate((self.card_ok, self.card_warn, self.card_crit, self.card_total)):
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            cards_row.columnconfigure(i, weight=1, minsize=120)

        actions = ttk.Frame(right, style="Panel.TFrame", padding=22)
        actions.pack(fill="both", expand=True, pady=(20, 0))
        ttk.Label(actions, text="Inizia una diagnosi completa", style="CardTitle.TLabel",
                  font=(None, 13, "bold")).pack(anchor="w")
        ttk.Label(actions,
                  text="Scegli quali controlli eseguire tra hardware, software e problemi potenziali,\n"
                       "oppure avvia subito una scansione con le impostazioni predefinite.",
                  style="PanelMuted.TLabel", justify="left").pack(anchor="w", pady=(6, 16))
        btn_row = ttk.Frame(actions, style="Panel.TFrame")
        btn_row.pack(anchor="w")
        ttk.Button(btn_row, text="Seleziona controlli →", style="Accent.TButton",
                   command=lambda: app.show_page("selection")).pack(side="left")
        ttk.Button(btn_row, text="Scansione rapida (predefinita)", style="TButton",
                   command=app.quick_scan).pack(side="left", padx=(12, 0))

        self.recent_issues_title = ttk.Label(right, text="", style="Subtitle.TLabel")
        self.recent_issues_frame = ttk.Frame(right, style="TFrame")

    def refresh(self):
        results = self.app.results
        score = self.app.last_score
        self.gauge.set_score(score if results else 0)

        if self.app.last_scan_time:
            self.last_scan_label.configure(
                text=f"Ultima scansione: {self.app.last_scan_time.strftime('%d/%m/%Y %H:%M')}"
            )
        else:
            self.last_scan_label.configure(text="Nessuna scansione eseguita")

        counts = {s: 0 for s in Status}
        for r in results.values():
            counts[r.status] += 1

        self.card_ok.set_value(str(counts[Status.OK]))
        self.card_warn.set_value(str(counts[Status.WARNING]))
        self.card_crit.set_value(str(counts[Status.CRITICAL] + counts[Status.ERROR]))
        self.card_total.set_value(str(len(results)))

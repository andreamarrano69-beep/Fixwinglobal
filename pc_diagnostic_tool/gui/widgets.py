"""Widget riutilizzabili: card statistiche, gauge circolare, lista scrollabile, righe di controllo."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .theme import Palette


class ScrollableFrame(ttk.Frame):
    """Un frame scrollabile verticalmente basato su Canvas, con supporto rotellina del mouse."""

    def __init__(self, parent, bg=None, **kwargs):
        super().__init__(parent, style="TFrame", **kwargs)
        bg = bg or Palette.bg
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="TFrame")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")

        for widget in (self.canvas, self.inner):
            widget.bind("<Enter>", lambda e: self._bind_mousewheel())
            widget.bind("<Leave>", lambda e: self._unbind_mousewheel())

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self._window, width=event.width)

    def _bind_mousewheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

    def _unbind_mousewheel(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class StatCard(ttk.Frame):
    """Card riepilogativa con icona, valore ed etichetta."""

    def __init__(self, parent, icon: str, title: str, value: str = "–",
                 accent: str = Palette.accent, **kwargs):
        super().__init__(parent, style="Panel.TFrame", padding=(12, 14), **kwargs)
        self._accent_bar = tk.Frame(self, bg=accent, width=4)
        self._accent_bar.pack(side="left", fill="y", padx=(0, 10))

        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(side="left", fill="both", expand=True)

        top = ttk.Frame(body, style="Panel.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=icon, style="Panel.TLabel", font=(None, 13)).pack(side="left")
        ttk.Label(top, text=title, style="PanelMuted.TLabel", font=(None, 10, "bold")).pack(side="left", padx=(6, 0))

        self.value_label = ttk.Label(body, text=value, style="CardValue.TLabel")
        self.value_label.pack(anchor="w", pady=(6, 0))

    def set_value(self, value: str):
        self.value_label.configure(text=value)


class ScoreGauge(tk.Canvas):
    """Gauge circolare (arco) che mostra un punteggio 0-100 con colore adattivo."""

    def __init__(self, parent, size: int = 150, **kwargs):
        super().__init__(parent, width=size, height=size, bg=Palette.panel, highlightthickness=0, **kwargs)
        self.size = size
        self.set_score(0)

    def _color_for(self, score: int) -> str:
        if score >= 80:
            return Palette.success
        if score >= 60:
            return Palette.warning
        return Palette.critical

    def set_score(self, score: int):
        self.delete("all")
        size = self.size
        pad = 10
        color = self._color_for(score)

        self.create_oval(pad, pad, size - pad, size - pad, outline=Palette.panel_alt, width=12)
        extent = -360 * (score / 100.0)
        if score > 0:
            self.create_arc(pad, pad, size - pad, size - pad, start=90, extent=extent,
                             style="arc", outline=color, width=12)
        self.create_text(size / 2, size / 2 - 6, text=str(score), fill=Palette.text,
                          font=(None, int(size * 0.22), "bold"))
        self.create_text(size / 2, size / 2 + size * 0.20, text="SALUTE PC", fill=Palette.text_muted,
                          font=(None, int(size * 0.08)))


class StatusBadge(ttk.Frame):
    """Piccola pillola colorata che mostra uno stato (OK, Attenzione, Critico, ...)."""

    def __init__(self, parent, status_value: str, label: str, **kwargs):
        super().__init__(parent, style="Panel.TFrame", **kwargs)
        color = Palette.status_color(status_value)
        canvas = tk.Canvas(self, width=10, height=10, bg=Palette.panel, highlightthickness=0)
        canvas.create_oval(1, 1, 9, 9, fill=color, outline=color)
        canvas.pack(side="left", padx=(0, 6))
        ttk.Label(self, text=label, style="PanelMuted.TLabel").pack(side="left")


class CheckRow(ttk.Frame):
    """Riga selezionabile per un singolo controllo nella pagina di selezione."""

    def __init__(self, parent, check_id: str, title: str, description: str,
                 initial: bool, on_toggle: Callable[[str, bool], None], **kwargs):
        super().__init__(parent, style="Panel.TFrame", padding=(14, 10), **kwargs)
        self.check_id = check_id
        self.var = tk.BooleanVar(value=initial)
        self._on_toggle = on_toggle

        def _toggled():
            on_toggle(check_id, self.var.get())

        self.check = ttk.Checkbutton(self, variable=self.var, style="TCheckbutton", command=_toggled)
        self.check.pack(side="left", padx=(0, 12))

        text_frame = ttk.Frame(self, style="Panel.TFrame")
        text_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(text_frame, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(text_frame, text=description, style="PanelMuted.TLabel", wraplength=520,
                  justify="left").pack(anchor="w")

        self.status_holder = ttk.Frame(self, style="Panel.TFrame")
        self.status_holder.pack(side="right")

        self.bind("<Button-1>", lambda e: self._toggle_from_row())
        text_frame.bind("<Button-1>", lambda e: self._toggle_from_row())

    def _toggle_from_row(self):
        self.var.set(not self.var.get())
        self._on_toggle(self.check_id, self.var.get())

    def set_selected(self, value: bool):
        self.var.set(value)

    def is_selected(self) -> bool:
        return self.var.get()

    def show_status(self, status_value: str, label: str):
        for w in self.status_holder.winfo_children():
            w.destroy()
        StatusBadge(self.status_holder, status_value, label).pack()


class SectionHeader(ttk.Frame):
    """Intestazione di categoria con checkbox 'seleziona tutto'."""

    def __init__(self, parent, icon: str, title: str, on_toggle_all: Callable[[bool], None], **kwargs):
        super().__init__(parent, style="TFrame", **kwargs)
        self.var = tk.BooleanVar(value=True)
        left = ttk.Frame(self, style="TFrame")
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text=f"{icon}  {title}", style="Title.TLabel", font=(None, 14, "bold")).pack(anchor="w")

        ttk.Checkbutton(self, text="Seleziona tutto", variable=self.var, style="TCheckbutton",
                         command=lambda: on_toggle_all(self.var.get())).pack(side="right")


class Toast(tk.Frame):
    """Notifica temporanea in basso a destra."""

    def __init__(self, parent, message: str, kind: str = "info", duration_ms: int = 3200):
        color = {"info": Palette.info, "success": Palette.success,
                 "warning": Palette.warning, "error": Palette.critical}.get(kind, Palette.info)
        super().__init__(parent, bg=color, padx=16, pady=10)
        tk.Label(self, text=message, bg=color, fg="#0b1220", font=(None, 10, "bold")).pack()
        self.place(relx=0.5, rely=0.96, anchor="s")
        self.after(duration_ms, self.destroy)


class SuggestionCard(ttk.Frame):
    """Card che mostra un singolo consiglio (es. upgrade hardware)."""

    def __init__(self, parent, icon: str, title: str, text: str, **kwargs):
        super().__init__(parent, style="PanelAlt.TFrame", padding=(14, 12), **kwargs)
        head = ttk.Frame(self, style="PanelAlt.TFrame")
        head.pack(fill="x", anchor="w")
        ttk.Label(head, text=icon, background=Palette.panel_alt, foreground=Palette.text,
                  font=(None, 13)).pack(side="left")
        ttk.Label(head, text=title, background=Palette.panel_alt, foreground=Palette.text,
                  font=(None, 10, "bold")).pack(side="left", padx=(8, 0))
        ttk.Label(self, text=text, background=Palette.panel_alt, foreground=Palette.text_muted,
                  wraplength=290, justify="left", font=(None, 9)).pack(anchor="w", pady=(6, 0), fill="x")


class FixRow(ttk.Frame):
    """Riga con un'azione di fix proponibile: etichetta, rischio, pulsante 'Applica' e stato esito."""

    def __init__(self, parent, label: str, risk: str, description: str,
                 on_apply: Callable[["FixRow"], None], **kwargs):
        super().__init__(parent, style="PanelAlt.TFrame", padding=(14, 12), **kwargs)
        self.on_apply = on_apply

        ttk.Label(self, text=label, background=Palette.panel_alt, foreground=Palette.text,
                  font=(None, 10, "bold"), wraplength=290, justify="left").pack(anchor="w", fill="x")
        risk_text = "rischio: sicuro" if risk == "safe" else "rischio: attenzione"
        risk_color = Palette.success if risk == "safe" else Palette.warning
        ttk.Label(self, text=risk_text, background=Palette.panel_alt, foreground=risk_color,
                  font=(None, 8, "bold")).pack(anchor="w", pady=(2, 0))

        ttk.Label(self, text=description, background=Palette.panel_alt, foreground=Palette.text_muted,
                  wraplength=290, justify="left", font=(None, 9)).pack(anchor="w", pady=(6, 8), fill="x")

        bottom = ttk.Frame(self, style="PanelAlt.TFrame")
        bottom.pack(fill="x")
        self.apply_btn = ttk.Button(bottom, text="Applica", style="Safe.TButton" if risk == "safe" else "Caution.TButton",
                                     command=lambda: self.on_apply(self))
        self.apply_btn.pack(side="left")
        self.status_label = ttk.Label(bottom, text="", background=Palette.panel_alt, foreground=Palette.text_muted,
                                       font=(None, 9))
        self.status_label.pack(side="left", padx=(10, 0))

    def set_busy(self, message: str = "Applicazione in corso..."):
        self.apply_btn.configure(state="disabled")
        self.status_label.configure(text=message, foreground=Palette.info)

    def set_result(self, success: bool, message: str):
        self.apply_btn.configure(state="normal")
        self.status_label.configure(text=message, foreground=Palette.success if success else Palette.critical)

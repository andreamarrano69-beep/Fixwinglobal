"""Palette colori e configurazione degli stili ttk per un'interfaccia moderna e scura."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


class Palette:
    bg = "#0b1220"           # sfondo principale finestra
    bg_soft = "#101a2e"      # sfondo aree secondarie
    panel = "#151f36"        # pannelli/card
    panel_alt = "#1a2440"    # card alternata / hover
    border = "#26314f"
    sidebar = "#0e1526"

    text = "#e7ecf7"
    text_muted = "#93a0bd"
    text_faint = "#5b6a8c"

    accent = "#4f7cff"       # blu principale
    accent_hover = "#6b93ff"
    accent_soft = "#1b2748"

    success = "#22c55e"
    warning = "#f5a623"
    critical = "#ef4444"
    info = "#38bdf8"
    unsupported = "#5b6a8c"

    @classmethod
    def status_color(cls, status_value: str) -> str:
        return {
            "ok": cls.success,
            "warning": cls.warning,
            "critical": cls.critical,
            "error": cls.critical,
            "info": cls.info,
            "unsupported": cls.unsupported,
        }.get(status_value, cls.text_muted)


FONT_FAMILY = "Segoe UI"
FONT_FAMILY_FALLBACKS = ("Segoe UI", "Helvetica Neue", "Ubuntu", "DejaVu Sans", "Arial")


def _pick_font_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for fam in FONT_FAMILY_FALLBACKS:
        if fam in available:
            return fam
    return "TkDefaultFont"


def apply_theme(root: tk.Tk) -> str:
    """Configura gli stili ttk globali. Restituisce il nome della famiglia di font scelta."""
    family = _pick_font_family(root)

    root.configure(bg=Palette.bg)
    root.option_add("*Font", (family, 10))

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=Palette.bg, foreground=Palette.text,
                    fieldbackground=Palette.panel, bordercolor=Palette.border,
                    font=(family, 10))

    style.configure("TFrame", background=Palette.bg)
    style.configure("Sidebar.TFrame", background=Palette.sidebar)
    style.configure("Panel.TFrame", background=Palette.panel)
    style.configure("PanelAlt.TFrame", background=Palette.panel_alt)

    style.configure("TLabel", background=Palette.bg, foreground=Palette.text, font=(family, 10))
    style.configure("Panel.TLabel", background=Palette.panel, foreground=Palette.text, font=(family, 10))
    style.configure("Muted.TLabel", background=Palette.bg, foreground=Palette.text_muted, font=(family, 9))
    style.configure("PanelMuted.TLabel", background=Palette.panel, foreground=Palette.text_muted, font=(family, 9))
    style.configure("Title.TLabel", background=Palette.bg, foreground=Palette.text, font=(family, 20, "bold"))
    style.configure("Subtitle.TLabel", background=Palette.bg, foreground=Palette.text_muted, font=(family, 11))
    style.configure("CardTitle.TLabel", background=Palette.panel, foreground=Palette.text, font=(family, 11, "bold"))
    style.configure("CardValue.TLabel", background=Palette.panel, foreground=Palette.text, font=(family, 22, "bold"))
    style.configure("SidebarBrand.TLabel", background=Palette.sidebar, foreground=Palette.text, font=(family, 14, "bold"))
    style.configure("SidebarMuted.TLabel", background=Palette.sidebar, foreground=Palette.text_faint, font=(family, 8))

    style.configure("TButton", background=Palette.panel_alt, foreground=Palette.text,
                     borderwidth=0, focusthickness=0, padding=(14, 8), font=(family, 10))
    style.map("TButton", background=[("active", Palette.border)])

    style.configure("Accent.TButton", background=Palette.accent, foreground="#ffffff",
                     borderwidth=0, padding=(16, 10), font=(family, 10, "bold"))
    style.map("Accent.TButton", background=[("active", Palette.accent_hover), ("disabled", Palette.text_faint)])

    style.configure("Ghost.TButton", background=Palette.bg, foreground=Palette.text_muted,
                     borderwidth=0, padding=(10, 6), font=(family, 9))
    style.map("Ghost.TButton", background=[("active", Palette.panel)], foreground=[("active", Palette.text)])

    style.configure("Nav.TButton", background=Palette.sidebar, foreground=Palette.text_muted,
                     borderwidth=0, padding=(14, 10), font=(family, 10), anchor="w")
    style.map("Nav.TButton", background=[("active", Palette.panel_alt)], foreground=[("active", Palette.text)])

    style.configure("NavActive.TButton", background=Palette.accent_soft, foreground=Palette.accent_hover,
                     borderwidth=0, padding=(14, 10), font=(family, 10, "bold"), anchor="w")
    style.map("NavActive.TButton", background=[("active", Palette.accent_soft)])

    style.configure("TCheckbutton", background=Palette.panel, foreground=Palette.text,
                     font=(family, 10), focuscolor=Palette.panel)

    style.configure("TNotebook", background=Palette.panel, borderwidth=0, tabmargins=(0, 6, 0, 0))
    style.configure("TNotebook.Tab", background=Palette.bg_soft, foreground=Palette.text_muted,
                     padding=(16, 8), font=(family, 10, "bold"), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", Palette.panel)],
              foreground=[("selected", Palette.text)])

    style.configure("Safe.TButton", background=Palette.success, foreground="#062012",
                     borderwidth=0, padding=(12, 8), font=(family, 9, "bold"))
    style.map("Safe.TButton", background=[("active", "#2fd66c"), ("disabled", Palette.text_faint)])

    style.configure("Caution.TButton", background=Palette.warning, foreground="#241300",
                     borderwidth=0, padding=(12, 8), font=(family, 9, "bold"))
    style.map("Caution.TButton", background=[("active", "#ffb84d"), ("disabled", Palette.text_faint)])
    style.map("TCheckbutton", background=[("active", Palette.panel)])

    style.configure("Horizontal.TProgressbar", background=Palette.accent, troughcolor=Palette.panel_alt,
                     bordercolor=Palette.panel_alt, lightcolor=Palette.accent, darkcolor=Palette.accent, thickness=10)

    style.configure("Treeview", background=Palette.panel, fieldbackground=Palette.panel,
                     foreground=Palette.text, borderwidth=0, rowheight=30, font=(family, 10))
    style.configure("Treeview.Heading", background=Palette.bg_soft, foreground=Palette.text_muted,
                     borderwidth=0, font=(family, 9, "bold"))
    style.map("Treeview", background=[("selected", Palette.accent_soft)], foreground=[("selected", Palette.text)])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("Vertical.TScrollbar", background=Palette.panel_alt, troughcolor=Palette.bg,
                     bordercolor=Palette.bg, arrowsize=12)
    style.configure("TSeparator", background=Palette.border)

    return family

"""Punto di ingresso di PC Diagnostic Tool.

Avvio: eseguire questo file dalla cartella 'pc_diagnostic_tool' con:
    python main.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

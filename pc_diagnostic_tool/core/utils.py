"""Funzioni di utilità: rilevamento piattaforma, esecuzione comandi, formattazione."""
from __future__ import annotations

import platform
import subprocess
import time
from typing import Dict, List, Optional

import psutil


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_mac() -> bool:
    return platform.system() == "Darwin"


def run_command(args: List[str], timeout: float = 8.0) -> Optional[str]:
    """Esegue un comando esterno e ne restituisce lo stdout, oppure None in caso di errore."""
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0 and not completed.stdout:
            return None
        return completed.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def run_powershell(script: str, timeout: float = 12.0) -> Optional[str]:
    """Esegue uno script PowerShell (solo Windows) e restituisce lo stdout."""
    return run_command(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )


def format_bytes(num_bytes: float) -> str:
    """Converte un numero di byte in una stringa leggibile (B, KB, MB, GB, TB, PB)."""
    value = float(num_bytes)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if unit == "B":
            if abs(value) < 1024.0:
                return f"{int(value)} B"
        elif round(value, 1) < 1024.0 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"


def format_seconds(seconds: float) -> str:
    """Converte i secondi in una durata leggibile (es. '3 giorni, 4 ore')."""
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days} giorni" if days != 1 else "1 giorno")
    if hours:
        parts.append(f"{hours} ore" if hours != 1 else "1 ora")
    if minutes and not days:
        parts.append(f"{minutes} min")
    if not parts:
        parts.append(f"{seconds} sec")
    return ", ".join(parts)


def sample_processes(interval: float = 0.3) -> List[Dict]:
    """Campiona CPU e memoria per ogni processo con un vero valore, non 0%.

    psutil.Process.cpu_percent() restituisce sempre 0.0 alla prima chiamata
    per ogni processo (deve calcolare la differenza tra due letture). Qui si
    fa una prima chiamata di "riscaldamento" su tutti i processi, si attende
    un breve intervallo, poi si legge il valore reale.
    """
    handles = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)  # avvia la misurazione (il valore restituito qui va ignorato)
            handles.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(interval)

    results = []
    for p in handles:
        try:
            results.append({
                "pid": p.pid,
                "name": p.info.get("name") or p.name(),
                "cpu_percent": p.cpu_percent(None),
                "memory_percent": p.memory_percent(),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def truncate(text: str, length: int = 120) -> str:
    text = text.strip()
    return text if len(text) <= length else text[: length - 1] + "…"

"""Implementazioni concrete delle azioni di correzione (fix) proponibili all'utente.

Ogni funzione restituisce un FixOutcome e non lancia mai eccezioni verso il
chiamante: qualunque errore viene catturato e riportato come esito negativo,
così la GUI può sempre mostrare un messaggio comprensibile.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time

from .models import FixOutcome
from .utils import is_linux, is_mac, is_windows, run_command, run_powershell


def clean_temp_files() -> FixOutcome:
    """Elimina i file temporanei più vecchi di un giorno dalla cartella temp dell'utente."""
    temp_dir = tempfile.gettempdir()
    freed_bytes = 0
    removed = 0
    errors = 0
    cutoff = time.time() - 86400

    try:
        entries = os.listdir(temp_dir)
    except OSError as exc:
        return FixOutcome(False, f"Impossibile accedere alla cartella temporanea: {exc}")

    for name in entries:
        path = os.path.join(temp_dir, name)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                if os.path.getmtime(path) > cutoff:
                    continue
                size = os.path.getsize(path)
                os.remove(path)
                freed_bytes += size
                removed += 1
            elif os.path.isdir(path):
                if os.path.getmtime(path) > cutoff:
                    continue
                size = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, _, files in os.walk(path) for f in files
                    if os.path.exists(os.path.join(dp, f))
                )
                shutil.rmtree(path, ignore_errors=True)
                freed_bytes += size
                removed += 1
        except (OSError, PermissionError):
            errors += 1
            continue

    from .utils import format_bytes as _fb  # import locale per evitare ciclo
    message = f"Rimossi {removed} elementi, liberati circa {_fb(freed_bytes)}."
    if errors:
        message += f" {errors} elementi non eliminabili (in uso da altri programmi)."
    return FixOutcome(True, message)


def flush_dns_cache() -> FixOutcome:
    if is_windows():
        out = run_command(["ipconfig", "/flushdns"])
        if out is not None:
            return FixOutcome(True, "Cache DNS svuotata con successo.")
        return FixOutcome(False, "Impossibile svuotare la cache DNS (permessi insufficienti?).")
    if is_linux():
        for args in (["resolvectl", "flush-caches"], ["systemd-resolve", "--flush-caches"]):
            out = run_command(args)
            if out is not None:
                return FixOutcome(True, "Cache DNS svuotata con successo.")
        return FixOutcome(False, "Nessun servizio di risoluzione DNS compatibile trovato su questo sistema.")
    if is_mac():
        out = run_command(["dscacheutil", "-flushcache"])
        if out is not None:
            return FixOutcome(True, "Cache DNS svuotata con successo.")
    return FixOutcome(False, "Operazione non supportata su questo sistema operativo.")


def empty_recycle_bin() -> FixOutcome:
    if not is_windows():
        return FixOutcome(False, "Operazione disponibile solo su Windows.")
    run_powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    return FixOutcome(True, "Cestino svuotato (l'operazione non è reversibile).")


def optimize_disk(mountpoint: str) -> FixOutcome:
    """Esegue l'ottimizzazione nativa di Windows (TRIM su SSD, deframmentazione su HDD)."""
    if not is_windows():
        return FixOutcome(False, "Operazione disponibile solo su Windows.")
    letter = mountpoint.rstrip("\\").rstrip(":")
    out = run_powershell(f"Optimize-Volume -DriveLetter {letter} -Verbose 4>&1", timeout=120)
    if out is None:
        return FixOutcome(False, "Impossibile avviare l'ottimizzazione (permessi di amministratore richiesti).")
    return FixOutcome(True, f"Ottimizzazione dell'unità {letter}: completata.", [l.strip() for l in out.splitlines() if l.strip()])


_SYSTEM_TOOLS = {
    "disk_cleanup": "cleanmgr.exe",
    "startup_settings": "ms-settings:startupapps",
    "windows_update": "ms-settings:windowsupdate",
    "windows_security": "windowsdefender:",
    "device_manager": "devmgmt.msc",
    "disk_management": "diskmgmt.msc",
    "optimize_drives": "dfrgui.exe",
    "task_manager": "taskmgr.exe",
    "event_viewer": "eventvwr.msc",
}


def open_system_tool(tool: str) -> FixOutcome:
    """Apre uno strumento nativo di Windows (azione 'guidata': non modifica nulla da sola)."""
    target = _SYSTEM_TOOLS.get(tool)
    if not target:
        return FixOutcome(False, f"Strumento '{tool}' non riconosciuto.")
    if not is_windows():
        return FixOutcome(False, "Questo strumento è disponibile solo su Windows.")
    try:
        os.startfile(target)  # type: ignore[attr-defined]
        return FixOutcome(True, "Strumento di sistema aperto: completa l'operazione dalla finestra che si è aperta.")
    except OSError as exc:
        return FixOutcome(False, f"Impossibile aprire lo strumento richiesto: {exc}")


def rescan_hardware() -> FixOutcome:
    """Chiede a Windows di ricercare nuovamente tutte le periferiche collegate (nuovo rilevamento hardware)."""
    if not is_windows():
        return FixOutcome(False, "Operazione disponibile solo su Windows.")
    out = run_command(["pnputil", "/scan-devices"], timeout=30)
    if out is None:
        return FixOutcome(False, "Impossibile eseguire la nuova ricerca hardware (potrebbero servire permessi "
                                  "di amministratore).")
    return FixOutcome(True, "Nuova ricerca hardware completata: Windows ha ridetectato le periferiche collegate.")


def run_audio_troubleshooter() -> FixOutcome:
    """Avvia lo strumento di risoluzione problemi audio integrato in Windows."""
    if not is_windows():
        return FixOutcome(False, "Operazione disponibile solo su Windows.")
    try:
        subprocess.Popen(["msdt.exe", "/id", "AudioPlaybackDiagnostic"])
        return FixOutcome(True, "Risoluzione problemi audio di Windows avviata: segui le indicazioni a schermo.")
    except OSError as exc:
        return FixOutcome(False, f"Impossibile avviare la risoluzione problemi audio: {exc}")

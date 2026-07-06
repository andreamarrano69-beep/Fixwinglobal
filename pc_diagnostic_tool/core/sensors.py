"""Lettura delle temperature hardware reali (CPU/GPU/dischi).

psutil non espone sensori di temperatura su Windows. Per ottenere dati reali su
Windows ci appoggiamo al provider WMI esposto da LibreHardwareMonitor (o dal suo
predecessore OpenHardwareMonitor), entrambi gratuiti e open source. Se nessuno dei
due è in esecuzione, proviamo ad avviare una copia portatile inclusa nella cartella
'tools/LibreHardwareMonitor' accanto al programma (utile per un uso da chiavetta USB).
Se non è disponibile nulla, restituiamo un risultato vuoto con istruzioni chiare.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import List

import psutil

from .utils import is_windows, run_powershell

_LHM_DIR_CANDIDATES = ("LibreHardwareMonitor", "OpenHardwareMonitor")
_WMI_NAMESPACES = ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor")

DOWNLOAD_HINT = (
    "Per leggere le temperature reali su Windows installa LibreHardwareMonitor "
    "(gratuito, open source): https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases . "
    "Per l'uso da chiavetta USB, estrai l'eseguibile in 'tools/LibreHardwareMonitor/' accanto "
    "a main.py: il programma proverà ad avviarlo automaticamente in background."
)

_launched_lhm = False


@dataclass
class TemperatureReading:
    label: str
    current: float
    high: float = 0.0


@dataclass
class TemperatureReport:
    readings: List[TemperatureReading]
    source: str          # descrive da dove arrivano i dati (per trasparenza nei dettagli)
    note: str = ""       # eventuale suggerimento/limite da mostrare all'utente


def _tools_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "tools")


def _find_bundled_lhm() -> str:
    for name in _LHM_DIR_CANDIDATES:
        exe = os.path.join(_tools_dir(), name, f"{name}.exe")
        if os.path.isfile(exe):
            return exe
    return ""


def _query_wmi_namespace(namespace: str) -> List[TemperatureReading]:
    script = (
        f"Get-CimInstance -Namespace {namespace} -ClassName Sensor -ErrorAction SilentlyContinue | "
        "Where-Object { $_.SensorType -eq 'Temperature' } | "
        "Select-Object Name,Value | ForEach-Object { \"$($_.Name)|$($_.Value)\" }"
    )
    out = run_powershell(script, timeout=8)
    readings = []
    if not out:
        return readings
    for line in out.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        name, _, value = line.partition("|")
        try:
            readings.append(TemperatureReading(label=name.strip(), current=float(value.strip())))
        except ValueError:
            continue
    return readings


def _try_launch_bundled_lhm() -> bool:
    global _launched_lhm
    if _launched_lhm:
        return True
    exe = _find_bundled_lhm()
    if not exe:
        return False
    try:
        subprocess.Popen(
            [exe],
            cwd=os.path.dirname(exe),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        _launched_lhm = True
        time.sleep(3.0)  # concede tempo al provider WMI per registrarsi
        return True
    except OSError:
        return False


def read_temperatures() -> TemperatureReport:
    """Prova più strategie, in ordine, per leggere le temperature reali del sistema."""
    try:
        psutil_temps = psutil.sensors_temperatures()
    except AttributeError:
        psutil_temps = {}
    if psutil_temps:
        readings = [
            TemperatureReading(label=e.label or name, current=e.current, high=e.high or 0.0)
            for name, entries in psutil_temps.items()
            for e in entries
        ]
        if readings:
            return TemperatureReport(readings, source="Sensori di sistema (psutil)")

    if not is_windows():
        return TemperatureReport([], source="nessuna", note=DOWNLOAD_HINT)

    for namespace in _WMI_NAMESPACES:
        readings = _query_wmi_namespace(namespace)
        if readings:
            tool = "LibreHardwareMonitor" if "Libre" in namespace else "OpenHardwareMonitor"
            return TemperatureReport(readings, source=f"{tool} (già in esecuzione)")

    if _try_launch_bundled_lhm():
        for namespace in _WMI_NAMESPACES:
            readings = _query_wmi_namespace(namespace)
            if readings:
                return TemperatureReport(readings, source="LibreHardwareMonitor (avviato automaticamente)")

    return TemperatureReport([], source="nessuna", note=DOWNLOAD_HINT)

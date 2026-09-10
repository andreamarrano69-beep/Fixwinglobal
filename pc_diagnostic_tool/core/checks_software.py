"""Controlli software: sistema operativo, aggiornamenti, app installate, avvio, processi, antivirus, driver, servizi."""
from __future__ import annotations

import os
import platform
import time

import psutil

from .models import CheckResult, Status
from .utils import format_seconds, is_linux, is_mac, is_windows, run_command, run_powershell, sample_processes


def check_os_info() -> CheckResult:
    boot_time = psutil.boot_time()
    uptime = time.time() - boot_time
    details = [
        f"Sistema: {platform.system()} {platform.release()}",
        f"Versione: {platform.version()}",
        f"Architettura: {platform.machine()}",
        f"Nome host: {platform.node()}",
        f"Avviato: {time.strftime('%d/%m/%Y %H:%M', time.localtime(boot_time))} "
        f"(da {format_seconds(uptime)})",
    ]
    status = Status.OK
    summary = f"{platform.system()} {platform.release()} — attivo da {format_seconds(uptime)}"
    if uptime > 14 * 86400:
        status = Status.WARNING
        summary += " (si consiglia un riavvio)"
    return CheckResult("os_info", "Sistema operativo", status, summary, details, raw={"uptime": uptime})


def check_windows_update() -> CheckResult:
    if not is_windows():
        return CheckResult("windows_update", "Aggiornamenti di sistema", Status.UNSUPPORTED,
                            "Controllo disponibile solo su Windows", [])
    out = run_powershell(
        "Get-HotFix | Sort-Object -Property InstalledOn -Descending | "
        "Select-Object -First 8 HotFixID,Description,InstalledOn | Format-Table -AutoSize | Out-String -Width 200"
    )
    if not out or not out.strip():
        return CheckResult("windows_update", "Aggiornamenti di sistema", Status.INFO,
                            "Impossibile leggere la cronologia aggiornamenti (permessi insufficienti)", [])
    details = [l.rstrip() for l in out.splitlines() if l.strip()]
    return CheckResult("windows_update", "Aggiornamenti di sistema", Status.OK,
                        "Ultimi aggiornamenti installati elencati sotto", details)


def check_installed_apps() -> CheckResult:
    apps = []
    if is_windows():
        script = (
            "$paths = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
            "'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
            "'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*';"
            "Get-ItemProperty $paths -ErrorAction SilentlyContinue | "
            "Where-Object { $_.DisplayName } | Select-Object -ExpandProperty DisplayName -Unique"
        )
        out = run_powershell(script, timeout=20)
        if out:
            apps = sorted({l.strip() for l in out.splitlines() if l.strip()})
    elif is_linux():
        out = run_command(["dpkg-query", "-W", "-f=${Package}\n"], timeout=15)
        if out is None:
            out = run_command(["rpm", "-qa"], timeout=15)
        if out:
            apps = sorted({l.strip() for l in out.splitlines() if l.strip()})
    elif is_mac():
        out = run_command(["ls", "/Applications"])
        if out:
            apps = sorted({l.strip() for l in out.splitlines() if l.strip()})

    if not apps:
        return CheckResult("installed_apps", "Software installato", Status.INFO,
                            "Impossibile enumerare il software installato su questo sistema", [])

    details = apps[:300]
    if len(apps) > 300:
        details.append(f"… e altri {len(apps) - 300} elementi non mostrati")
    return CheckResult("installed_apps", "Software installato", Status.OK,
                        f"{len(apps)} programmi installati rilevati", details)


def check_startup_programs() -> CheckResult:
    items = []
    if is_windows():
        out = run_powershell(
            "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location | Format-List"
        )
        if out and out.strip():
            items = [b.strip().replace("\n", " | ") for b in out.split("\n\n") if b.strip()]
    elif is_linux():
        autostart_dir = os.path.expanduser("~/.config/autostart")
        if os.path.isdir(autostart_dir):
            items = [f for f in os.listdir(autostart_dir) if f.endswith(".desktop")]
    elif is_mac():
        out = run_command(["osascript", "-e", 'tell application "System Events" to get the name of every login item'])
        if out and out.strip():
            items = [i.strip() for i in out.strip().split(",")]

    if not items:
        return CheckResult("startup_programs", "Programmi all'avvio", Status.INFO,
                            "Nessun programma di avvio rilevato o funzione non supportata su questo sistema", [])

    status = Status.WARNING if len(items) > 15 else Status.OK
    summary = f"{len(items)} programmi si avviano insieme al sistema"
    if status == Status.WARNING:
        summary += " (un numero elevato può rallentare l'avvio)"
    return CheckResult("startup_programs", "Programmi all'avvio", status, summary, items)


def check_running_processes() -> CheckResult:
    procs = sample_processes()

    by_cpu = sorted(procs, key=lambda i: i.get("cpu_percent") or 0, reverse=True)[:8]
    by_mem = sorted(procs, key=lambda i: i.get("memory_percent") or 0, reverse=True)[:8]

    details = [f"Totale processi in esecuzione: {len(procs)}", "", "Top per CPU:"]
    details += [f"  {i['name']} (PID {i['pid']}): {i.get('cpu_percent') or 0:.1f}% CPU" for i in by_cpu]
    details.append("")
    details.append("Top per memoria:")
    details += [f"  {i['name']} (PID {i['pid']}): {i.get('memory_percent') or 0:.1f}% RAM" for i in by_mem]

    return CheckResult("running_processes", "Processi in esecuzione", Status.OK,
                        f"{len(procs)} processi attivi", details, raw={"count": len(procs)})


def check_antivirus() -> CheckResult:
    if is_windows():
        out = run_powershell(
            "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | "
            "Select-Object displayName,productState | Format-List"
        )
        if out and out.strip():
            details = [l.strip() for l in out.splitlines() if l.strip()]
            return CheckResult("antivirus", "Antivirus e firewall", Status.OK,
                                "Prodotto/i antivirus rilevato/i", details)
        return CheckResult("antivirus", "Antivirus e firewall", Status.WARNING,
                            "Nessun antivirus rilevato tramite Security Center",
                            ["Verificare manualmente che Windows Defender o un altro antivirus sia attivo."])
    elif is_mac():
        return CheckResult("antivirus", "Antivirus e firewall", Status.INFO,
                            "macOS include protezioni integrate (Gatekeeper, XProtect); "
                            "controllo dettagliato non disponibile", [])
    return CheckResult("antivirus", "Antivirus e firewall", Status.UNSUPPORTED,
                        "Controllo non applicabile o non supportato su questo sistema operativo", [])


def check_drivers() -> CheckResult:
    if not is_windows():
        return CheckResult("drivers", "Driver di sistema", Status.UNSUPPORTED,
                            "Controllo dettagliato dei driver disponibile solo su Windows", [])
    out = run_command(["driverquery"], timeout=15)
    if not out or not out.strip():
        return CheckResult("drivers", "Driver di sistema", Status.INFO,
                            "Impossibile leggere l'elenco driver", [])
    lines = [l for l in out.splitlines() if l.strip()]
    return CheckResult("drivers", "Driver di sistema", Status.OK,
                        f"{max(len(lines) - 2, 0)} driver rilevati", lines[:60])


def check_services() -> CheckResult:
    if is_windows():
        try:
            services = list(psutil.win_service_iter())
        except AttributeError:
            return CheckResult("services", "Servizi di sistema", Status.ERROR,
                                "Impossibile enumerare i servizi Windows", [])
        running = [s for s in services if s.status() == "running"]
        details = [f"Servizi totali: {len(services)}", f"In esecuzione: {len(running)}"]
        return CheckResult("services", "Servizi di sistema", Status.OK,
                            f"{len(running)} servizi attivi su {len(services)} totali", details)
    elif is_linux():
        out = run_command(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend"])
        if out is None:
            return CheckResult("services", "Servizi di sistema", Status.UNSUPPORTED,
                                "systemd non disponibile su questo sistema", [])
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        return CheckResult("services", "Servizi di sistema", Status.OK,
                            f"{len(lines)} servizi attivi", lines[:60])
    return CheckResult("services", "Servizi di sistema", Status.UNSUPPORTED,
                        "Controllo non supportato su questo sistema operativo", [])

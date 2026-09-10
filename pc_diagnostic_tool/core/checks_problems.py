"""Controlli euristici per l'individuazione di problemi potenziali del sistema."""
from __future__ import annotations

import os
import re
import socket
import tempfile
import time

import psutil

from .models import CheckResult, Status
from .sensors import read_temperatures
from .utils import format_bytes, is_linux, is_windows, run_command, run_powershell, sample_processes


def check_disk_space_alert() -> CheckResult:
    critical, warning, ok = [], [], []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        line = f"{part.mountpoint}: {usage.percent:.0f}% usato ({format_bytes(usage.free)} liberi)"
        if usage.percent >= 95:
            critical.append(line)
        elif usage.percent >= 85:
            warning.append(line)
        else:
            ok.append(line)

    details = critical + warning + ok
    if critical:
        return CheckResult("disk_space_alert", "Spazio disco in esaurimento", Status.CRITICAL,
                            f"{len(critical)} unità quasi piena/e (>95%)", details)
    if warning:
        return CheckResult("disk_space_alert", "Spazio disco in esaurimento", Status.WARNING,
                            f"{len(warning)} unità con poco spazio libero (>85%)", details)
    return CheckResult("disk_space_alert", "Spazio disco in esaurimento", Status.OK,
                        "Nessuna unità con spazio in esaurimento", details)


def check_cpu_load_alert() -> CheckResult:
    percent = psutil.cpu_percent(interval=1.0)
    details = [f"Utilizzo CPU misurato: {percent:.0f}% (campione istantaneo)"]
    top = sorted(sample_processes(), key=lambda i: i.get("cpu_percent") or 0, reverse=True)[:5]
    for p in top:
        details.append(f"  {p['name']}: {p.get('cpu_percent') or 0:.1f}%")

    if percent >= 90:
        return CheckResult("cpu_load_alert", "Sovraccarico CPU", Status.CRITICAL,
                            f"Sovraccarico CPU rilevato: {percent:.0f}%", details)
    if percent >= 70:
        return CheckResult("cpu_load_alert", "Sovraccarico CPU", Status.WARNING,
                            f"Carico CPU elevato: {percent:.0f}%", details)
    return CheckResult("cpu_load_alert", "Sovraccarico CPU", Status.OK,
                        f"Carico CPU nella norma: {percent:.0f}%", details)


def check_ram_pressure() -> CheckResult:
    vm = psutil.virtual_memory()
    details = [f"Memoria in uso: {vm.percent:.0f}%", f"Disponibile: {format_bytes(vm.available)}"]
    if vm.percent >= 90:
        return CheckResult("ram_pressure", "Memoria insufficiente", Status.CRITICAL,
                            f"Pressione critica sulla memoria: {vm.percent:.0f}% in uso", details)
    if vm.percent >= 75:
        return CheckResult("ram_pressure", "Memoria insufficiente", Status.WARNING,
                            f"Memoria sotto pressione: {vm.percent:.0f}% in uso", details)
    return CheckResult("ram_pressure", "Memoria insufficiente", Status.OK,
                        f"Memoria disponibile sufficiente ({100 - vm.percent:.0f}% libera)", details)


def check_temp_alert() -> CheckResult:
    report = read_temperatures()
    if not report.readings:
        return CheckResult("temp_alert", "Surriscaldamento", Status.UNSUPPORTED,
                            "Nessun sensore di temperatura disponibile",
                            [report.note] if report.note else [])
    max_temp = 0.0
    details = [f"Fonte dati: {report.source}"]
    for r in report.readings:
        max_temp = max(max_temp, r.current)
        details.append(f"{r.label}: {r.current:.0f}°C")
    if max_temp >= 90:
        return CheckResult("temp_alert", "Surriscaldamento", Status.CRITICAL,
                            f"Temperatura critica rilevata: {max_temp:.0f}°C", details, raw={"max_temp": max_temp})
    if max_temp >= 80:
        return CheckResult("temp_alert", "Surriscaldamento", Status.WARNING,
                            f"Temperatura elevata rilevata: {max_temp:.0f}°C", details, raw={"max_temp": max_temp})
    return CheckResult("temp_alert", "Surriscaldamento", Status.OK,
                        f"Temperature nella norma (max {max_temp:.0f}°C)", details, raw={"max_temp": max_temp})


def check_battery_health_alert() -> CheckResult:
    if is_windows():
        fd, report_path = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        try:
            run_powershell(f'powercfg /batteryreport /XML /output "{report_path}"', timeout=20)
            with open(report_path, encoding="utf-8", errors="ignore") as f:
                xml = f.read()
            design = re.search(r"<DesignCapacity>(\d+)</DesignCapacity>", xml)
            full = re.search(r"<FullChargeCapacity>(\d+)</FullChargeCapacity>", xml)
            if design and full:
                design_cap, full_cap = int(design.group(1)), int(full.group(1))
                ratio = full_cap / design_cap * 100 if design_cap else 100
                details = [
                    f"Capacità di progetto: {design_cap} mWh",
                    f"Capacità massima attuale: {full_cap} mWh",
                    f"Salute stimata: {ratio:.0f}%",
                ]
                if ratio < 60:
                    return CheckResult("battery_health_alert", "Batteria degradata", Status.CRITICAL,
                                        f"Batteria molto degradata: {ratio:.0f}% della capacità originale", details)
                if ratio < 80:
                    return CheckResult("battery_health_alert", "Batteria degradata", Status.WARNING,
                                        f"Batteria parzialmente degradata: {ratio:.0f}% della capacità originale", details)
                return CheckResult("battery_health_alert", "Batteria degradata", Status.OK,
                                    f"Salute batteria buona: {ratio:.0f}% della capacità originale", details)
        except OSError:
            pass
        finally:
            try:
                os.remove(report_path)
            except OSError:
                pass
    battery = psutil.sensors_battery()
    if battery is None:
        return CheckResult("battery_health_alert", "Batteria degradata", Status.UNSUPPORTED,
                            "Nessuna batteria rilevata o dati di salute non disponibili su questo sistema", [])
    return CheckResult("battery_health_alert", "Batteria degradata", Status.INFO,
                        "Dati dettagliati sulla salute della batteria non disponibili su questo sistema",
                        [f"Carica attuale: {battery.percent:.0f}%"])


def check_event_log_errors() -> CheckResult:
    if is_windows():
        out = run_powershell(
            "Get-WinEvent -FilterHashtable @{LogName='System';Level=2;StartTime=(Get-Date).AddDays(-1)} "
            "-MaxEvents 20 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,ProviderName | Format-Table -AutoSize | Out-String -Width 200"
        )
        if out is None or not out.strip():
            return CheckResult("event_log_errors", "Errori di sistema recenti", Status.OK,
                                "Nessun errore critico trovato nel registro eventi (ultime 24 ore)", [])
        lines = [l.rstrip() for l in out.splitlines() if l.strip()]
        count = max(len(lines) - 2, 0)
        status = Status.WARNING if count > 0 else Status.OK
        summary = f"{count} errori registrati nel Log di Sistema nelle ultime 24 ore" if count else "Nessun errore recente"
        return CheckResult("event_log_errors", "Errori di sistema recenti", status, summary, lines)
    elif is_linux():
        out = run_command(["journalctl", "-p", "3", "-b", "--no-pager", "-n", "20"])
        if out is None:
            return CheckResult("event_log_errors", "Errori di sistema recenti", Status.UNSUPPORTED,
                                "journalctl non disponibile su questo sistema", [])
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        status = Status.WARNING if lines else Status.OK
        summary = f"{len(lines)} errori trovati nel journal di sistema" if lines else "Nessun errore recente nel journal"
        return CheckResult("event_log_errors", "Errori di sistema recenti", status, summary, lines)
    return CheckResult("event_log_errors", "Errori di sistema recenti", Status.UNSUPPORTED,
                        "Controllo non supportato su questo sistema operativo", [])


def check_suspicious_processes() -> CheckResult:
    tmp_markers = ("temp", "tmp", "appdata\\local\\temp")
    suspicious = []
    for p in psutil.process_iter(["pid", "name", "exe", "cpu_percent"]):
        try:
            exe = (p.info.get("exe") or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if exe and any(marker in exe for marker in tmp_markers):
            suspicious.append(f"{p.info['name']} (PID {p.info['pid']}) eseguito da: {p.info['exe']}")

    details = suspicious[:30]
    details.append("Nota: euristica basilare (percorso in cartella temporanea). Non sostituisce un antivirus.")
    if suspicious:
        return CheckResult("suspicious_processes", "Processi sospetti", Status.WARNING,
                            f"{len(suspicious)} processi in esecuzione da cartelle temporanee", details)
    return CheckResult("suspicious_processes", "Processi sospetti", Status.OK,
                        "Nessun processo sospetto rilevato con l'euristica applicata", details)


def check_pending_reboot() -> CheckResult:
    if not is_windows():
        return CheckResult("pending_reboot", "Riavvio in sospeso", Status.UNSUPPORTED,
                            "Controllo disponibile solo su Windows", [])
    script = (
        "$a = Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending';"
        "$b = Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired';"
        "$c = Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager' "
        "-Name PendingFileRenameOperations -ErrorAction SilentlyContinue;"
        "Write-Output \"$a|$b|$($c -ne $null)\""
    )
    out = run_powershell(script)
    if not out:
        return CheckResult("pending_reboot", "Riavvio in sospeso", Status.INFO,
                            "Impossibile verificare lo stato di riavvio in sospeso", [])
    parts = out.strip().split("|")
    pending = any(p.strip().lower() == "true" for p in parts)
    if pending:
        return CheckResult("pending_reboot", "Riavvio in sospeso", Status.WARNING,
                            "Il sistema richiede un riavvio per completare aggiornamenti/modifiche in sospeso",
                            ["Si consiglia di riavviare il PC appena possibile."])
    return CheckResult("pending_reboot", "Riavvio in sospeso", Status.OK,
                        "Nessun riavvio in sospeso", [])


def check_disk_fragmentation() -> CheckResult:
    if not is_windows():
        return CheckResult("disk_fragmentation", "Frammentazione disco", Status.UNSUPPORTED,
                            "Controllo significativo solo su unità HDD Windows con file system NTFS", [])
    out = run_powershell(
        "Get-Volume | Where-Object {$_.DriveType -eq 'Fixed'} | Select-Object DriveLetter,FileSystemType | Format-Table -AutoSize | Out-String"
    )
    media_out = run_powershell("(Get-PhysicalDisk | Select-Object -ExpandProperty MediaType) -join ','")
    has_hdd = bool(media_out and "hdd" in media_out.lower())
    details = [l.rstrip() for l in (out or "").splitlines() if l.strip()]
    if has_hdd:
        status = Status.WARNING
        summary = "Rilevato almeno un disco meccanico (HDD): la frammentazione ne riduce le prestazioni nel tempo"
    else:
        status = Status.OK
        summary = "Nessun disco meccanico rilevato (SSD/NVMe): la frammentazione non è un problema rilevante"
    return CheckResult("disk_fragmentation", "Frammentazione disco", status, summary, details,
                        raw={"has_hdd": has_hdd})


def check_network_connectivity() -> CheckResult:
    targets = [("1.1.1.1", 53), ("8.8.8.8", 53)]
    details = []
    reachable = False
    best_latency = None
    for host, port in targets:
        start = time.time()
        try:
            with socket.create_connection((host, port), timeout=2.5):
                latency = (time.time() - start) * 1000
                details.append(f"Connessione a {host}:{port} riuscita ({latency:.0f} ms)")
                reachable = True
                best_latency = latency if best_latency is None else min(best_latency, latency)
        except OSError:
            details.append(f"Connessione a {host}:{port} fallita")

    dns_ok = False
    try:
        socket.gethostbyname("www.google.com")
        dns_ok = True
        details.append("Risoluzione DNS: funzionante")
    except OSError:
        details.append("Risoluzione DNS: non riuscita")

    if not reachable:
        return CheckResult("network_connectivity", "Connettività di rete", Status.CRITICAL,
                            "Nessuna connessione a Internet rilevata", details)
    if not dns_ok:
        return CheckResult("network_connectivity", "Connettività di rete", Status.WARNING,
                            "Connessione a Internet attiva ma la risoluzione DNS non funziona", details)
    if best_latency and best_latency > 150:
        return CheckResult("network_connectivity", "Connettività di rete", Status.WARNING,
                            f"Connessione funzionante ma con latenza elevata ({best_latency:.0f} ms)", details)
    return CheckResult("network_connectivity", "Connettività di rete", Status.OK,
                        f"Connessione a Internet funzionante ({best_latency:.0f} ms)", details)

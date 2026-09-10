"""Controlli hardware: CPU, RAM, dischi, GPU, scheda madre, rete, batteria, temperature, USB."""
from __future__ import annotations

import re
import socket

import psutil

from .models import CheckResult, Status
from .sensors import read_temperatures
from .utils import format_bytes, format_seconds, is_linux, is_mac, is_windows, run_command, run_powershell


def check_cpu() -> CheckResult:
    percent_total = psutil.cpu_percent(interval=0.6)
    percent_per_core = psutil.cpu_percent(interval=0.0, percpu=True)
    logical = psutil.cpu_count(logical=True)
    physical = psutil.cpu_count(logical=False)
    freq = psutil.cpu_freq()
    name = platform_cpu_name()

    details = [
        f"Modello: {name}" if name else "Modello: non rilevabile",
        f"Core fisici: {physical or 'n/d'} — Core logici (thread): {logical or 'n/d'}",
    ]
    if freq:
        details.append(f"Frequenza attuale: {freq.current:.0f} MHz (min {freq.min:.0f} / max {freq.max:.0f} MHz)")
    details.append("Utilizzo per core: " + ", ".join(f"C{i}: {p:.0f}%" for i, p in enumerate(percent_per_core)))

    try:
        load_avg = psutil.getloadavg()
        details.append(f"Load average (1/5/15 min): {load_avg[0]:.2f} / {load_avg[1]:.2f} / {load_avg[2]:.2f}")
    except (AttributeError, OSError):
        pass

    if percent_total >= 90:
        status, summary = Status.CRITICAL, f"Utilizzo CPU molto elevato: {percent_total:.0f}%"
    elif percent_total >= 70:
        status, summary = Status.WARNING, f"Utilizzo CPU elevato: {percent_total:.0f}%"
    else:
        status, summary = Status.OK, f"Utilizzo CPU nella norma: {percent_total:.0f}%"

    return CheckResult("cpu", "Processore (CPU)", status, summary, details,
                        raw={"percent_total": percent_total, "logical": logical, "physical": physical})


def platform_cpu_name() -> str:
    import platform as _platform
    try:
        if is_windows():
            out = run_powershell("(Get-CimInstance Win32_Processor).Name")
            if out and out.strip():
                return out.strip()
        elif is_linux():
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.lower().startswith("model name"):
                            return line.split(":", 1)[1].strip()
            except OSError:
                pass
        elif is_mac():
            out = run_command(["sysctl", "-n", "machdep.cpu.brand_string"])
            if out and out.strip():
                return out.strip()
    except Exception:
        pass
    return _platform.processor() or _platform.machine()


def _ram_slot_info() -> list:
    """Interroga WMI per capire quanti banchi RAM sono occupati/liberi (utile per consigli di upgrade)."""
    if not is_windows():
        return []
    script = (
        "$sticks = Get-CimInstance Win32_PhysicalMemory | "
        "Select-Object Capacity,Speed,Manufacturer,MemoryType; "
        "$slots = (Get-CimInstance Win32_PhysicalMemoryArray).MemoryDevices; "
        "Write-Output \"SLOTS_TOTALI:$slots\"; "
        "$sticks | ForEach-Object { Write-Output \"BANCO:$($_.Capacity)|$($_.Speed)|$($_.Manufacturer)\" }"
    )
    out = run_powershell(script, timeout=10)
    if not out:
        return []
    details = []
    occupied = 0
    total_slots = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("SLOTS_TOTALI:"):
            try:
                total_slots = int(line.split(":", 1)[1])
            except ValueError:
                pass
        elif line.startswith("BANCO:"):
            occupied += 1
            parts = line.split(":", 1)[1].split("|")
            if len(parts) == 3:
                capacity, speed, manufacturer = parts
                try:
                    cap_str = format_bytes(int(capacity))
                except ValueError:
                    cap_str = "?"
                details.append(f"  Banco: {cap_str} a {speed} MHz ({manufacturer.strip() or 'produttore sconosciuto'})")
    if total_slots is not None:
        free = max(total_slots - occupied, 0)
        details.insert(0, f"Slot RAM: {occupied} occupati su {total_slots} totali ({free} liberi)")
    return details


def check_ram() -> CheckResult:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    details = [
        f"Totale: {format_bytes(vm.total)}",
        f"Usata: {format_bytes(vm.used)} ({vm.percent:.0f}%)",
        f"Disponibile: {format_bytes(vm.available)}",
        f"Swap: {format_bytes(swap.used)} / {format_bytes(swap.total)} usata"
        if swap.total else "Swap: non configurata",
    ]
    details.extend(_ram_slot_info())
    if vm.percent >= 90:
        status, summary = Status.CRITICAL, f"Memoria quasi esaurita: {vm.percent:.0f}% in uso"
    elif vm.percent >= 75:
        status, summary = Status.WARNING, f"Utilizzo memoria elevato: {vm.percent:.0f}%"
    else:
        status, summary = Status.OK, f"Memoria nella norma: {vm.percent:.0f}% in uso"

    return CheckResult("ram", "Memoria RAM", status, summary, details, raw={"percent": vm.percent})


def check_disk() -> CheckResult:
    details = []
    worst = Status.OK
    worst_percent = 0.0
    partitions_data = []
    for part in psutil.disk_partitions(all=False):
        if is_windows() and ("cdrom" in part.opts or part.fstype == ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        partitions_data.append((part, usage))
        details.append(
            f"{part.device} ({part.mountpoint}) [{part.fstype}]: "
            f"{format_bytes(usage.used)} / {format_bytes(usage.total)} usati ({usage.percent:.0f}%), "
            f"liberi {format_bytes(usage.free)}"
        )
        if usage.percent > worst_percent:
            worst_percent = usage.percent

    if not partitions_data:
        return CheckResult("disk", "Dischi e archiviazione", Status.ERROR,
                            "Impossibile leggere le informazioni sui dischi", details)

    if worst_percent >= 95:
        worst = Status.CRITICAL
        summary = f"Almeno un'unità è quasi piena ({worst_percent:.0f}% usato)"
    elif worst_percent >= 85:
        worst = Status.WARNING
        summary = f"Spazio in esaurimento su un'unità ({worst_percent:.0f}% usato)"
    else:
        summary = f"Spazio su disco nella norma (massimo {worst_percent:.0f}% usato)"

    return CheckResult("disk", "Dischi e archiviazione", worst, summary, details)


def check_disk_health() -> CheckResult:
    details = []
    if is_windows():
        out = run_powershell(
            "Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,OperationalStatus,MediaType,BusType,Size | Format-List"
        )
        if out and out.strip():
            entries = [e.strip() for e in out.split("\n\n") if e.strip()]
            bad = False
            has_hdd = False
            for entry in entries:
                details.append(entry.replace("\n", " | "))
                if "healthy" not in entry.lower() and "sano" not in entry.lower():
                    bad = True
                if "hdd" in entry.lower():
                    has_hdd = True
            status = Status.CRITICAL if bad else Status.OK
            summary = "Problema rilevato sullo stato di uno o più dischi" if bad else "Tutti i dischi risultano in stato integro"
            return CheckResult("disk_health", "Salute dischi (SMART)", status, summary, details,
                                raw={"has_hdd": has_hdd})
        return CheckResult("disk_health", "Salute dischi (SMART)", Status.INFO,
                            "Impossibile leggere lo stato SMART (permessi insufficienti o comando non disponibile)",
                            ["Suggerimento: eseguire il programma come amministratore."])

    smartctl_out = run_command(["smartctl", "--scan"])
    if smartctl_out is None:
        return CheckResult("disk_health", "Salute dischi (SMART)", Status.UNSUPPORTED,
                            "smartmontools non installato: impossibile leggere lo stato SMART",
                            ["Installa il pacchetto 'smartmontools' per abilitare questo controllo "
                             "(es. 'sudo apt install smartmontools')."])
    devices = re.findall(r"^(\S+)", smartctl_out, flags=re.MULTILINE)
    if not devices:
        return CheckResult("disk_health", "Salute dischi (SMART)", Status.INFO,
                            "Nessun dispositivo SMART rilevato", [])
    bad = False
    for dev in devices:
        health = run_command(["smartctl", "-H", dev])
        if health is None:
            details.append(f"{dev}: impossibile leggere lo stato (richiede permessi elevati)")
            continue
        passed = "PASSED" in health or "OK" in health
        details.append(f"{dev}: {'OK' if passed else 'ATTENZIONE - possibile guasto imminente'}")
        if not passed:
            bad = True
    status = Status.CRITICAL if bad else Status.OK
    summary = "Rilevato possibile guasto su un disco" if bad else "Stato SMART dei dischi: OK"
    return CheckResult("disk_health", "Salute dischi (SMART)", status, summary, details)


def check_gpu() -> CheckResult:
    details = []
    if is_windows():
        out = run_powershell(
            "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM | Format-List"
        )
        if out and out.strip():
            for block in [b.strip() for b in out.split("\n\n") if b.strip()]:
                details.append(block.replace("\n", " | "))
            return CheckResult("gpu", "Scheda video (GPU)", Status.OK,
                                f"Rilevate {len(details)} scheda/e video", details)
    elif is_linux():
        out = run_command(["lspci"])
        if out:
            gpu_lines = [l for l in out.splitlines() if re.search(r"VGA|3D controller|Display", l)]
            if gpu_lines:
                details.extend(gpu_lines)
                return CheckResult("gpu", "Scheda video (GPU)", Status.OK,
                                    f"Rilevate {len(gpu_lines)} scheda/e video", details)
    elif is_mac():
        out = run_command(["system_profiler", "SPDisplaysDataType"])
        if out and out.strip():
            details.append(out.strip())
            return CheckResult("gpu", "Scheda video (GPU)", Status.OK, "Informazioni GPU rilevate", details)

    return CheckResult("gpu", "Scheda video (GPU)", Status.INFO,
                        "Impossibile rilevare automaticamente la scheda video su questo sistema", [])


def check_motherboard() -> CheckResult:
    if is_windows():
        out = run_powershell(
            "Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product | Format-List; "
            "Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | Format-List"
        )
        if out and out.strip():
            details = [l.strip() for l in out.splitlines() if l.strip()]
            return CheckResult("motherboard", "Scheda madre / BIOS", Status.OK,
                                "Informazioni scheda madre e BIOS rilevate", details)
    elif is_linux():
        details = []
        for label, path in (
            ("Produttore", "/sys/class/dmi/id/board_vendor"),
            ("Modello", "/sys/class/dmi/id/board_name"),
            ("Versione BIOS", "/sys/class/dmi/id/bios_version"),
        ):
            try:
                with open(path) as f:
                    details.append(f"{label}: {f.read().strip()}")
            except (OSError, PermissionError):
                details.append(f"{label}: non disponibile (permessi insufficienti)")
        if details:
            return CheckResult("motherboard", "Scheda madre / BIOS", Status.OK,
                                "Informazioni scheda madre lette da /sys/class/dmi", details)
    elif is_mac():
        out = run_command(["system_profiler", "SPHardwareDataType"])
        if out and out.strip():
            return CheckResult("motherboard", "Scheda madre / BIOS", Status.OK,
                                "Informazioni hardware Mac rilevate", [out.strip()])

    return CheckResult("motherboard", "Scheda madre / BIOS", Status.INFO,
                        "Impossibile leggere le informazioni della scheda madre (permessi o piattaforma non supportata)", [])


def check_network_hw() -> CheckResult:
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    details = []
    active = 0
    for name, st in stats.items():
        state = "attiva" if st.isup else "disattiva"
        if st.isup:
            active += 1
        line = f"{name}: {state}"
        if st.isup and st.speed:
            line += f", {st.speed} Mbps"
        ip_list = [a.address for a in addrs.get(name, []) if a.family == socket.AF_INET]
        if ip_list:
            line += f", IP: {', '.join(ip_list)}"
        details.append(line)

    if active == 0:
        return CheckResult("network_hw", "Interfacce di rete", Status.WARNING,
                            "Nessuna interfaccia di rete risulta attiva", details)
    return CheckResult("network_hw", "Interfacce di rete", Status.OK,
                        f"{active} interfaccia/e di rete attiva/e su {len(stats)} rilevate", details)


def check_battery() -> CheckResult:
    battery = psutil.sensors_battery()
    if battery is None:
        return CheckResult("battery", "Batteria", Status.UNSUPPORTED,
                            "Nessuna batteria rilevata (probabilmente un desktop, oppure info non disponibili)", [])
    plugged = "collegato alla corrente" if battery.power_plugged else "in uso a batteria"
    details = [f"Carica: {battery.percent:.0f}%", f"Stato alimentazione: {plugged}"]
    if battery.secsleft and battery.secsleft > 0:
        details.append(f"Autonomia residua stimata: {format_seconds(battery.secsleft)}")

    if battery.percent <= 15 and not battery.power_plugged:
        status, summary = Status.WARNING, f"Batteria scarica ({battery.percent:.0f}%) e non in carica"
    else:
        status, summary = Status.OK, f"Batteria al {battery.percent:.0f}%, {plugged}"
    return CheckResult("battery", "Batteria", status, summary, details, raw={"percent": battery.percent, "plugged": battery.power_plugged})


def check_temperature() -> CheckResult:
    report = read_temperatures()
    if not report.readings:
        return CheckResult("temperature", "Sensori di temperatura", Status.UNSUPPORTED,
                            "Nessun sensore di temperatura rilevato su questo sistema",
                            [report.note] if report.note else [])

    details = [f"Fonte dati: {report.source}"]
    max_temp = 0.0
    for r in report.readings:
        details.append(f"{r.label}: {r.current:.0f}°C" + (f" (max {r.high:.0f}°C)" if r.high else ""))
        max_temp = max(max_temp, r.current)

    if max_temp >= 90:
        status, summary = Status.CRITICAL, f"Temperatura molto elevata rilevata: {max_temp:.0f}°C"
    elif max_temp >= 80:
        status, summary = Status.WARNING, f"Temperatura elevata rilevata: {max_temp:.0f}°C"
    else:
        status, summary = Status.OK, f"Temperature nella norma (massima {max_temp:.0f}°C)"
    return CheckResult("temperature", "Sensori di temperatura", status, summary, details, raw={"max_temp": max_temp})


def check_usb() -> CheckResult:
    if is_windows():
        out = run_powershell(
            "Get-PnpDevice -Class USB -Status OK | Select-Object -ExpandProperty FriendlyName"
        )
        if out is not None:
            items = [l.strip() for l in out.splitlines() if l.strip()]
            return CheckResult("usb", "Dispositivi USB collegati", Status.OK,
                                f"{len(items)} dispositivo/i USB rilevato/i", items)
    elif is_linux():
        out = run_command(["lsusb"])
        if out is not None:
            items = [l.strip() for l in out.splitlines() if l.strip()]
            return CheckResult("usb", "Dispositivi USB collegati", Status.OK,
                                f"{len(items)} dispositivo/i USB rilevato/i", items)
    elif is_mac():
        out = run_command(["system_profiler", "SPUSBDataType"])
        if out and out.strip():
            return CheckResult("usb", "Dispositivi USB collegati", Status.OK,
                                "Dispositivi USB rilevati", [out.strip()])

    return CheckResult("usb", "Dispositivi USB collegati", Status.INFO,
                        "Impossibile enumerare i dispositivi USB su questo sistema", [])

"""Controlli hardware: CPU, RAM, dischi, GPU, scheda madre, rete, batteria, temperature, USB."""
from __future__ import annotations

import os
import re
import socket
import tempfile
import time

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


def check_performance_monitor() -> CheckResult:
    """Campiona CPU/RAM/I-O disco per alcuni secondi, invece di un solo istante, per scovare picchi intermittenti."""
    duration_s = 8
    cpu_samples = []
    ram_samples = []
    io_before = None
    try:
        io_before = psutil.disk_io_counters()
    except (OSError, RuntimeError):
        pass

    t_start = time.time()
    while time.time() - t_start < duration_s:
        cpu_samples.append(psutil.cpu_percent(interval=1.0))
        ram_samples.append(psutil.virtual_memory().percent)
    elapsed = time.time() - t_start

    io_after = None
    try:
        io_after = psutil.disk_io_counters()
    except (OSError, RuntimeError):
        pass

    cpu_avg = sum(cpu_samples) / len(cpu_samples)
    cpu_max = max(cpu_samples)
    ram_avg = sum(ram_samples) / len(ram_samples)
    ram_max = max(ram_samples)

    details = [
        f"Durata campionamento: {elapsed:.0f} secondi ({len(cpu_samples)} letture)",
        f"CPU: media {cpu_avg:.0f}%, picco massimo {cpu_max:.0f}%",
        f"RAM: media {ram_avg:.0f}%, picco massimo {ram_max:.0f}%",
    ]
    if io_before and io_after:
        read_mb = (io_after.read_bytes - io_before.read_bytes) / (1024 * 1024)
        write_mb = (io_after.write_bytes - io_before.write_bytes) / (1024 * 1024)
        details.append(f"Disco: {read_mb:.1f} MB letti, {write_mb:.1f} MB scritti durante il campionamento")

    if cpu_max >= 95 and cpu_avg < 50:
        status = Status.WARNING
        summary = f"Rilevato un picco intermittente di CPU al {cpu_max:.0f}% (media {cpu_avg:.0f}%)"
    elif cpu_avg >= 80:
        status = Status.WARNING
        summary = f"CPU costantemente sotto carico elevato durante il campionamento (media {cpu_avg:.0f}%)"
    else:
        status = Status.OK
        summary = f"Nessun picco anomalo rilevato (CPU media {cpu_avg:.0f}%, picco {cpu_max:.0f}%)"

    return CheckResult("performance_monitor", "Monitoraggio prestazioni", status, summary, details,
                        raw={"cpu_avg": cpu_avg, "cpu_max": cpu_max})


def check_disk_speed_test() -> CheckResult:
    """Test pratico: scrive e rilegge un file da 100 MB per misurare la velocità reale del disco."""
    test_size_mb = 100
    chunk = os.urandom(1024 * 1024)  # 1 MB casuale (non comprimibile), riscritto 100 volte
    tmp_dir = tempfile.gettempdir()

    try:
        fd, path = tempfile.mkstemp(suffix=".diskbench", dir=tmp_dir)
        os.close(fd)
    except OSError as exc:
        return CheckResult("disk_speed_test", "Test velocità disco", Status.ERROR,
                            f"Impossibile creare il file di test: {exc}", [])

    try:
        start = time.time()
        with open(path, "wb") as f:
            for _ in range(test_size_mb):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        write_time = time.time() - start
        write_speed = test_size_mb / write_time if write_time > 0 else 0.0

        start = time.time()
        with open(path, "rb") as f:
            while f.read(4 * 1024 * 1024):
                pass
        read_time = time.time() - start
        read_speed = test_size_mb / read_time if read_time > 0 else 0.0
    except OSError as exc:
        return CheckResult("disk_speed_test", "Test velocità disco", Status.ERROR,
                            f"Impossibile completare il test: {exc}", [])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    details = [
        f"Cartella di test: {tmp_dir}",
        f"Dimensione file di test: {test_size_mb} MB",
        f"Velocità di scrittura: {write_speed:.0f} MB/s",
        f"Velocità di lettura: {read_speed:.0f} MB/s (può risultare più alta del reale per via della "
        "cache del sistema operativo)",
    ]

    if write_speed < 60:
        status = Status.CRITICAL
        summary = f"Disco molto lento in scrittura: {write_speed:.0f} MB/s (tipico di un HDD datato o quasi pieno)"
    elif write_speed < 150:
        status = Status.WARNING
        summary = f"Velocità in scrittura da disco meccanico (HDD): {write_speed:.0f} MB/s"
    else:
        status = Status.OK
        summary = f"Velocità in scrittura buona: {write_speed:.0f} MB/s (compatibile con un SSD)"

    return CheckResult("disk_speed_test", "Test velocità disco", status, summary, details,
                        raw={"write_speed": write_speed, "read_speed": read_speed})


def check_input_devices() -> CheckResult:
    """Verifica tastiera e mouse: rilevamento e codici di errore driver riportati da Windows."""
    if is_linux():
        try:
            with open("/proc/bus/input/devices", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            names = re.findall(r'N: Name="([^"]+)"', content)
            relevant = [n for n in names if re.search(r"keyboard|mouse|touchpad", n, re.IGNORECASE)] or names
            if names:
                return CheckResult("input_devices", "Tastiera e mouse", Status.OK,
                                    f"{len(names)} dispositivo/i di input rilevato/i", relevant)
        except OSError:
            pass
        return CheckResult("input_devices", "Tastiera e mouse", Status.INFO,
                            "Impossibile enumerare tastiera/mouse su questo sistema", [])

    if not is_windows():
        return CheckResult("input_devices", "Tastiera e mouse", Status.INFO,
                            "Controllo dettagliato disponibile solo su Windows e Linux", [])

    script = (
        "$devs = @(); "
        "$devs += Get-CimInstance Win32_Keyboard -ErrorAction SilentlyContinue; "
        "$devs += Get-CimInstance Win32_PointingDevice -ErrorAction SilentlyContinue; "
        "foreach ($d in $devs) { Write-Output \"DEV:$($d.Name)|$($d.Status)|$($d.ConfigManagerErrorCode)\" }"
    )
    out = run_powershell(script, timeout=10)
    if not out or not out.strip():
        return CheckResult("input_devices", "Tastiera e mouse", Status.INFO,
                            "Impossibile enumerare tastiera/mouse (permessi insufficienti)", [])

    details = []
    problem_devices = []
    count = 0
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("DEV:"):
            continue
        count += 1
        parts = line[4:].split("|")
        name = parts[0].strip() if parts and parts[0].strip() else "Dispositivo sconosciuto"
        dev_status = parts[1].strip() if len(parts) > 1 else ""
        error_code = parts[2].strip() if len(parts) > 2 else "0"
        line_out = f"{name}: stato {dev_status or 'sconosciuto'}"
        if error_code and error_code != "0":
            line_out += f" — codice errore Windows: {error_code} (dispositivo con problemi)"
            problem_devices.append(name)
        details.append(line_out)

    if problem_devices:
        status = Status.WARNING
        summary = f"{len(problem_devices)} dispositivo/i di input con errori segnalati da Windows"
    elif count == 0:
        status = Status.WARNING
        summary = "Nessuna tastiera o mouse rilevato tramite Windows (possibile problema di driver/connessione)"
    else:
        status = Status.OK
        summary = f"{count} dispositivo/i di input rilevato/i, nessun errore segnalato"
    return CheckResult("input_devices", "Tastiera e mouse", status, summary, details,
                        raw={"problem_count": len(problem_devices)})


def check_output_devices() -> CheckResult:
    """Verifica monitor e dispositivi audio (uscita): rilevamento e codici di errore driver."""
    if not is_windows():
        return CheckResult("output_devices", "Monitor e audio (output)", Status.INFO,
                            "Controllo dettagliato disponibile solo su Windows", [])

    script = (
        "$mons = Get-CimInstance Win32_DesktopMonitor -ErrorAction SilentlyContinue; "
        "$auds = Get-CimInstance Win32_SoundDevice -ErrorAction SilentlyContinue; "
        "foreach ($m in $mons) { Write-Output \"MON:$($m.Name)|$($m.Status)|$($m.ScreenWidth)x$($m.ScreenHeight)\" }; "
        "foreach ($a in $auds) { Write-Output \"AUD:$($a.Name)|$($a.Status)|$($a.ConfigManagerErrorCode)\" }"
    )
    out = run_powershell(script, timeout=10)
    if not out or not out.strip():
        return CheckResult("output_devices", "Monitor e audio (output)", Status.INFO,
                            "Impossibile enumerare monitor/dispositivi audio (permessi insufficienti)", [])

    details = []
    problems = []
    mon_count = aud_count = 0
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("MON:"):
            mon_count += 1
            parts = line[4:].split("|")
            name = parts[0].strip() or "Monitor"
            mon_status = parts[1].strip() if len(parts) > 1 else ""
            resolution = parts[2].strip() if len(parts) > 2 else ""
            line_out = f"Monitor: {name} — stato {mon_status or 'sconosciuto'}"
            if resolution and resolution not in ("0x0", "x"):
                line_out += f", risoluzione {resolution}"
            details.append(line_out)
            if mon_status and mon_status.lower() not in ("ok", ""):
                problems.append(name)
        elif line.startswith("AUD:"):
            aud_count += 1
            parts = line[4:].split("|")
            name = parts[0].strip() or "Dispositivo audio"
            aud_status = parts[1].strip() if len(parts) > 1 else ""
            error_code = parts[2].strip() if len(parts) > 2 else "0"
            line_out = f"Audio: {name} — stato {aud_status or 'sconosciuto'}"
            if error_code and error_code != "0":
                line_out += f" — codice errore Windows: {error_code}"
                problems.append(name)
            details.append(line_out)

    if problems:
        status = Status.WARNING
        summary = f"{len(problems)} dispositivo/i di output con problemi rilevati"
    elif mon_count == 0 and aud_count == 0:
        status = Status.INFO
        summary = "Nessun monitor/dispositivo audio rilevato tramite Windows"
    else:
        status = Status.OK
        summary = f"{mon_count} monitor e {aud_count} dispositivo/i audio rilevati, nessun problema segnalato"
    return CheckResult("output_devices", "Monitor e audio (output)", status, summary, details,
                        raw={"problem_count": len(problems)})


def check_stuck_keys() -> CheckResult:
    """Test fisico (non solo driver): rileva se un tasto risulta premuto in modo anomalo per tutta la
    durata del test — il sintomo tipico di un tasto meccanicamente incastrato (es. Canc bloccato che
    continua a inviare comandi di eliminazione)."""
    if not is_windows():
        return CheckResult("stuck_keys_test", "Test tasti bloccati", Status.UNSUPPORTED,
                            "Disponibile solo su Windows", [])
    try:
        import ctypes
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return CheckResult("stuck_keys_test", "Test tasti bloccati", Status.ERROR,
                            "Impossibile accedere alle API di Windows per questo test", [])

    keys = {
        0x08: "Backspace", 0x09: "Tab", 0x0D: "Invio", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt",
        0x1B: "Esc", 0x20: "Spazio", 0x2E: "Canc (Delete)", 0x2D: "Ins", 0x24: "Home", 0x23: "Fine",
        0x21: "Pag Su", 0x22: "Pag Giù",
        0x25: "Freccia sinistra", 0x26: "Freccia su", 0x27: "Freccia destra", 0x28: "Freccia giù",
        0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
        0x76: "F7", 0x77: "F8", 0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    }
    for code in range(0x30, 0x3A):
        keys[code] = chr(code)
    for code in range(0x41, 0x5B):
        keys[code] = chr(code)

    samples = 6
    interval = 0.5
    pressed_counts = {code: 0 for code in keys}
    for _ in range(samples):
        for code in keys:
            state = user32.GetAsyncKeyState(code)
            if state & 0x8000:
                pressed_counts[code] += 1
        time.sleep(interval)

    stuck = [keys[code] for code, count in pressed_counts.items() if count == samples]

    details = [f"Durata test: {samples * interval:.1f} secondi ({len(keys)} tasti monitorati; "
               "non toccare la tastiera durante il test per un risultato affidabile)"]
    if stuck:
        details.append("Tasti risultati premuti per l'intera durata del test:")
        details.extend(f"  {k}" for k in stuck)
        return CheckResult("stuck_keys_test", "Test tasti bloccati", Status.CRITICAL,
                            f"Rilevato/i {len(stuck)} tasto/i probabilmente bloccato/i: {', '.join(stuck)}",
                            details, raw={"stuck_keys": stuck})
    details.append("Nessun tasto risultato bloccato durante il test")
    return CheckResult("stuck_keys_test", "Test tasti bloccati", Status.OK,
                        "Nessun tasto bloccato rilevato", details)

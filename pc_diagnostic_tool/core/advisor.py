"""Genera suggerimenti (anche di upgrade hardware) e azioni di fix per ogni controllo.

Il modulo è disaccoppiato dai controlli veri e propri: prende in input il
CheckResult già calcolato e restituisce (List[Suggestion], List[FixAction]).
Le funzioni di fix effettive vivono in fix_actions.py; qui costruiamo solo i
FixAction con etichette/descrizioni pertinenti al contesto rilevato.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import psutil

from . import fix_actions as fx
from .models import CheckResult, FixAction, Status, Suggestion
from .utils import is_windows

AdvisorFunc = Callable[[CheckResult], Tuple[List[Suggestion], List[FixAction]]]

PROBLEM_STATUSES = (Status.WARNING, Status.CRITICAL, Status.ERROR)


def _fix_clean_temp() -> FixAction:
    return FixAction(
        id="clean_temp_files",
        label="🧹 Pulisci file temporanei",
        risk="safe",
        description="Elimina i file più vecchi di un giorno dalla cartella temporanea di sistema. "
                    "Operazione reversibile a basso rischio: non tocca documenti o programmi installati.",
        run=fx.clean_temp_files,
    )


def _fix_flush_dns() -> FixAction:
    return FixAction(
        id="flush_dns",
        label="🌐 Svuota cache DNS",
        risk="safe",
        description="Cancella la cache di risoluzione dei nomi di dominio. Utile se alcuni siti non "
                    "si aprono correttamente pur essendoci connessione. Nessun rischio.",
        run=fx.flush_dns_cache,
    )


def _fix_empty_recycle_bin() -> FixAction:
    return FixAction(
        id="empty_recycle_bin",
        label="🗑 Svuota Cestino",
        risk="caution",
        description="Elimina definitivamente tutti i file presenti nel Cestino per liberare spazio. "
                    "Attenzione: l'operazione NON è reversibile.",
        run=fx.empty_recycle_bin,
    )


def _fix_optimize_disk(mountpoint: str) -> FixAction:
    return FixAction(
        id=f"optimize_disk_{mountpoint}",
        label=f"⚙ Ottimizza unità {mountpoint}",
        risk="safe",
        description=f"Esegue l'ottimizzazione nativa di Windows sull'unità {mountpoint} "
                    "(TRIM se è un SSD, deframmentazione se è un HDD). Operazione standard e sicura, "
                    "potrebbe richiedere qualche minuto.",
        run=lambda: fx.optimize_disk(mountpoint),
    )


def _fix_open_tool(tool_id: str, label: str, description: str) -> FixAction:
    return FixAction(
        id=f"open_{tool_id}", label=label, risk="safe", description=description,
        run=lambda: fx.open_system_tool(tool_id),
    )


def advise_ram(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    percent = result.raw.get("percent", 0)
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🧠", "Chiudi le applicazioni non necessarie",
            f"La memoria RAM è al {percent:.0f}%. Chiudere i programmi aperti che non stai usando "
            "libera immediatamente risorse per il sistema."))
        if percent >= 85:
            suggestions.append(Suggestion(
                "🛒", "Valuta un aumento della RAM installata",
                f"Il sistema mostra un utilizzo di memoria molto elevato ({percent:.0f}%). Se questa "
                "situazione si ripete spesso e non solo durante un picco isolato, un aumento della RAM "
                "installata è l'intervento hardware più efficace per migliorare le prestazioni generali "
                "e la reattività del PC."))
        fixes.append(_fix_open_tool("task_manager", "📋 Apri Gestione attività",
                                     "Apre il Task Manager di Windows per individuare quali programmi "
                                     "stanno consumando più memoria e chiuderli manualmente."))
    return suggestions, fixes


def advise_ram_pressure(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    return advise_ram(result)


def advise_cpu(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "⚙", "Individua il processo responsabile",
            "Un utilizzo elevato della CPU è spesso causato da un singolo programma bloccato o da troppi "
            "processi in background. Apri Gestione attività e ordina per CPU per identificarlo."))
        suggestions.append(Suggestion(
            "🛒", "Valuta un upgrade del processore",
            "Se il carico elevato è costante nel tempo (non un picco isolato) e non dipende da un "
            "processo specifico, il processore potrebbe non essere più adeguato ai software in uso: "
            "valuta un upgrade della CPU o, se non possibile sulla scheda madre attuale, un cambio di sistema."))
        fixes.append(_fix_open_tool("task_manager", "📋 Apri Gestione attività",
                                     "Apre il Task Manager per individuare e chiudere il processo che "
                                     "sta occupando la CPU."))
    return suggestions, fixes


def advise_cpu_load(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    return advise_cpu(result)


def advise_disk(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🛒", "Valuta più spazio di archiviazione",
            "Se lo spazio si esaurisce ripetutamente nonostante la pulizia, valuta l'aggiunta di un "
            "secondo disco o la sostituzione con uno di capacità maggiore (e magari un SSD, se è "
            "ancora presente un HDD meccanico)."))
        fixes.append(_fix_clean_temp())
        fixes.append(_fix_empty_recycle_bin())
        if is_windows():
            fixes.append(_fix_open_tool("disk_cleanup", "🧽 Apri Utilità di pulizia disco",
                                         "Apre lo strumento nativo di Windows per la pulizia guidata del disco."))
    return suggestions, fixes


def advise_disk_space_alert(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    return advise_disk(result)


def advise_disk_health(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🚨", "Esegui subito un backup",
            "Il disco mostra segnali di possibile guasto imminente. Esegui immediatamente una copia di "
            "sicurezza dei dati importanti e valuta la sostituzione del disco (HDD/SSD) il prima possibile."))
        if is_windows():
            fixes.append(_fix_open_tool("disk_management", "💽 Apri Gestione disco",
                                         "Apre la Gestione disco di Windows per verificare lo stato dei volumi."))
    return suggestions, fixes


def advise_disk_fragmentation(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if is_windows():
        if result.raw.get("has_hdd"):
            suggestions.append(Suggestion(
                "🛒", "Sostituisci l'HDD con un SSD",
                "È stato rilevato un disco meccanico (HDD): sostituirlo con un SSD è l'aggiornamento "
                "hardware con il maggior impatto percepito sulla velocità generale del PC (avvio, apertura "
                "programmi, copia file)."))
        for part in psutil.disk_partitions(all=False):
            letter = part.mountpoint.rstrip("\\").rstrip(":")
            if letter and len(letter) <= 2:
                fixes.append(_fix_optimize_disk(letter))
        fixes.append(_fix_open_tool("optimize_drives", "⚙ Apri Ottimizzazione unità",
                                     "Apre lo strumento nativo di Windows per ottimizzare/deframmentare i dischi."))
    return suggestions, fixes


def advise_temperature(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        max_temp = result.raw.get("max_temp", 0)
        suggestions.append(Suggestion(
            "🌡", "Pulizia e manutenzione del raffreddamento",
            f"È stata rilevata una temperatura di {max_temp:.0f}°C. Le cause più comuni sono accumulo "
            "di polvere in ventole e dissipatore, pasta termica da rinnovare o un sistema di "
            "raffreddamento non adeguato all'uso attuale. Si consiglia una pulizia interna del PC e, "
            "se il problema persiste, la sostituzione della pasta termica o l'aggiunta/sostituzione "
            "di una ventola."))
    return suggestions, fixes


def advise_temp_alert(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    return advise_temperature(result)


def advise_battery(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions = []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🔋", "Valuta la sostituzione della batteria",
            "La batteria mostra una capacità ridotta rispetto all'originale o una carica residua bassa. "
            "Se l'autonomia non è più sufficiente per l'uso quotidiano, la sostituzione della batteria "
            "(da un centro assistenza) è l'intervento consigliato."))
    return suggestions, []


def advise_battery_health_alert(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    return advise_battery(result)


def advise_startup_programs(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🚀", "Disattiva i programmi non essenziali all'avvio",
            "Un numero elevato di programmi che partono con Windows rallenta l'accensione del PC. "
            "Disattiva quelli che non ti servono immediatamente dopo l'accensione."))
        if is_windows():
            fixes.append(_fix_open_tool("startup_settings", "🚀 Apri impostazioni di avvio",
                                         "Apre la pagina di Windows dove puoi attivare/disattivare i "
                                         "singoli programmi di avvio."))
    return suggestions, fixes


def advise_windows_update(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    fixes = []
    if is_windows():
        fixes.append(_fix_open_tool("windows_update", "🔄 Apri Windows Update",
                                     "Apre le impostazioni di Windows Update per verificare e installare "
                                     "gli aggiornamenti disponibili."))
    return [], fixes


def advise_antivirus(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🛡", "Attiva una protezione antivirus",
            "Nessun antivirus attivo è stato rilevato. Attiva Windows Defender oppure installa una "
            "soluzione antivirus di terze parti per proteggere il sistema."))
        if is_windows():
            fixes.append(_fix_open_tool("windows_security", "🛡 Apri Sicurezza di Windows",
                                         "Apre il centro sicurezza di Windows per verificare lo stato "
                                         "della protezione antivirus e del firewall."))
    return suggestions, fixes


def advise_event_log_errors(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    fixes = []
    if result.status in PROBLEM_STATUSES and is_windows():
        fixes.append(_fix_open_tool("event_viewer", "📜 Apri Visualizzatore eventi",
                                     "Apre il Visualizzatore eventi di Windows per analizzare in dettaglio "
                                     "gli errori registrati."))
    return [], fixes


def advise_suspicious_processes(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🕵", "Esegui una scansione antivirus completa",
            "Sono stati rilevati processi in esecuzione da cartelle temporanee: non è detto che siano "
            "dannosi, ma è buona norma verificarli con un antivirus aggiornato prima di considerarli innocui."))
        fixes.append(_fix_open_tool("task_manager", "📋 Apri Gestione attività",
                                     "Apre il Task Manager per esaminare i processi segnalati ed "
                                     "eventualmente terminarli manualmente dopo averli verificati."))
    return suggestions, fixes


def advise_pending_reboot(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions = []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "🔁", "Riavvia il PC quando possibile",
            "Il sistema ha aggiornamenti o modifiche in sospeso che richiedono un riavvio per essere "
            "completati. Salva il lavoro in corso e riavvia il PC appena possibile."))
    return suggestions, []


def advise_network_connectivity(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    suggestions, fixes = [], []
    if result.status in PROBLEM_STATUSES:
        suggestions.append(Suggestion(
            "📶", "Verifica router e cavi",
            "Se il problema persiste dopo lo svuotamento della cache DNS, prova a riavviare router/modem "
            "e controlla i cavi di rete o la connessione Wi-Fi."))
        fixes.append(_fix_flush_dns())
    return suggestions, fixes


def advise_drivers(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    fixes = []
    if is_windows():
        fixes.append(_fix_open_tool("device_manager", "🖧 Apri Gestione dispositivi",
                                     "Apre Gestione dispositivi per verificare la presenza di driver "
                                     "mancanti o con problemi (icona di avviso gialla)."))
    return [], fixes


ADVISORS: Dict[str, AdvisorFunc] = {
    "ram": advise_ram,
    "ram_pressure": advise_ram_pressure,
    "cpu": advise_cpu,
    "cpu_load_alert": advise_cpu_load,
    "disk": advise_disk,
    "disk_space_alert": advise_disk_space_alert,
    "disk_health": advise_disk_health,
    "disk_fragmentation": advise_disk_fragmentation,
    "temperature": advise_temperature,
    "temp_alert": advise_temp_alert,
    "battery": advise_battery,
    "battery_health_alert": advise_battery_health_alert,
    "startup_programs": advise_startup_programs,
    "windows_update": advise_windows_update,
    "antivirus": advise_antivirus,
    "event_log_errors": advise_event_log_errors,
    "suspicious_processes": advise_suspicious_processes,
    "pending_reboot": advise_pending_reboot,
    "network_connectivity": advise_network_connectivity,
    "drivers": advise_drivers,
}


def get_advisory(result: CheckResult) -> Tuple[List[Suggestion], List[FixAction]]:
    func = ADVISORS.get(result.check_id)
    if not func:
        return [], []
    try:
        return func(result)
    except Exception:
        return [], []

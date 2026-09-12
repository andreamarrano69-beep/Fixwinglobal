"""Catalogo delle categorie e dei singoli controlli selezionabili dall'utente."""
from __future__ import annotations

from typing import List

from .models import Category, CheckMeta

CATEGORIES: List[Category] = [
    Category(
        id="hardware",
        label="Hardware",
        icon="🖥",
        checks=[
            CheckMeta("cpu", "Processore (CPU)", "Utilizzo, frequenza, numero di core e carico per core"),
            CheckMeta("ram", "Memoria RAM", "Memoria totale, utilizzata, disponibile e memoria di swap"),
            CheckMeta("disk", "Dischi e archiviazione", "Spazio libero/occupato su ogni unità e partizione"),
            CheckMeta("disk_health", "Salute dischi (SMART)", "Stato SMART dei dischi, se disponibile sul sistema"),
            CheckMeta("gpu", "Scheda video (GPU)", "Modello e informazioni sulla scheda grafica"),
            CheckMeta("motherboard", "Scheda madre / BIOS", "Produttore, modello e versione del firmware/BIOS"),
            CheckMeta("network_hw", "Interfacce di rete", "Schede di rete, indirizzi IP/MAC e stato del collegamento"),
            CheckMeta("battery", "Batteria", "Percentuale di carica e stato di alimentazione (portatili)"),
            CheckMeta("temperature", "Sensori di temperatura", "Temperature rilevate su CPU e altri sensori"),
            CheckMeta("usb", "Dispositivi USB collegati", "Elenco delle periferiche USB attualmente connesse"),
            CheckMeta("performance_monitor", "Monitoraggio prestazioni (~8 sec)",
                      "Campiona CPU, RAM e attività disco per alcuni secondi per rilevare picchi intermittenti "
                      "che un singolo controllo istantaneo non vedrebbe"),
            CheckMeta("disk_speed_test", "Test velocità disco (scrive/legge un file da 100 MB)",
                      "Misura la velocità reale di scrittura/lettura del disco per capire se è il collo di "
                      "bottiglia delle prestazioni (non solo quanto spazio è occupato)", default_selected=False),
        ],
    ),
    Category(
        id="software",
        label="Software",
        icon="💽",
        checks=[
            CheckMeta("os_info", "Sistema operativo",
                      "Produttore, modello, numero di serie, edizione/build di Windows e tempo di attività"),
            CheckMeta("windows_update", "Aggiornamenti di sistema", "Stato degli aggiornamenti installati/in sospeso"),
            CheckMeta("installed_apps", "Software installato", "Elenco dei programmi installati sul sistema"),
            CheckMeta("startup_programs", "Programmi all'avvio", "Applicazioni che si avviano insieme al PC"),
            CheckMeta("running_processes", "Processi in esecuzione", "Processi attivi e consumo di risorse"),
            CheckMeta("antivirus", "Antivirus e firewall", "Stato della protezione antivirus e del firewall"),
            CheckMeta("drivers", "Driver di sistema", "Elenco dei driver installati e relativo stato"),
            CheckMeta("services", "Servizi di sistema", "Servizi critici e loro stato di esecuzione"),
        ],
    ),
    Category(
        id="problems",
        label="Problemi potenziali",
        icon="⚠",
        checks=[
            CheckMeta("disk_space_alert", "Spazio disco in esaurimento", "Verifica se un'unità sta per riempirsi"),
            CheckMeta("cpu_load_alert", "Sovraccarico CPU", "Rileva un utilizzo anomalo/elevato del processore"),
            CheckMeta("ram_pressure", "Memoria insufficiente", "Rileva una pressione elevata sulla RAM disponibile"),
            CheckMeta("temp_alert", "Surriscaldamento", "Segnala temperature elevate sui sensori disponibili"),
            CheckMeta("battery_health_alert", "Batteria degradata", "Confronta capacità attuale e di progetto della batteria"),
            CheckMeta("event_log_errors", "Errori di sistema recenti", "Cerca errori recenti nel registro eventi/log"),
            CheckMeta("suspicious_processes", "Processi sospetti", "Euristica su processi da percorsi anomali (Temp, ecc.)"),
            CheckMeta("pending_reboot", "Riavvio in sospeso", "Verifica se il sistema richiede un riavvio"),
            CheckMeta("disk_fragmentation", "Frammentazione disco", "Stima la frammentazione sui dischi meccanici (HDD)"),
            CheckMeta("network_connectivity", "Connettività di rete", "Verifica la raggiungibilità di Internet e la latenza"),
            CheckMeta("reliability_history", "Cronologia affidabilità Windows",
                      "Legge gli eventi critici (crash, blocchi, arresti anomali) registrati da Windows stesso"),
        ],
    ),
]


def all_check_ids() -> List[str]:
    return [c.id for cat in CATEGORIES for c in cat.checks]


def default_selected_ids() -> List[str]:
    return [c.id for cat in CATEGORIES for c in cat.checks if c.default_selected]


def find_check_meta(check_id: str) -> CheckMeta:
    for cat in CATEGORIES:
        for c in cat.checks:
            if c.id == check_id:
                return c
    raise KeyError(check_id)


def category_of(check_id: str) -> Category:
    for cat in CATEGORIES:
        for c in cat.checks:
            if c.id == check_id:
                return cat
    raise KeyError(check_id)

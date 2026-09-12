# PC Diagnostic Tool

Programma desktop in Python (Tkinter) per l'analisi completa di un PC: hardware,
software e problemi potenziali, con interfaccia grafica moderna e controlli
selezionabili singolarmente.

## Funzionalità

- **Dashboard** con punteggio di salute (0-100), card riepilogative e avvio rapido.
- **Selezione controlli**: 31 verifiche suddivise in 3 categorie, ognuna attivabile/disattivabile:
  - **Hardware**: CPU, RAM (con conteggio slot occupati/liberi), dischi, salute SMART (tipo SSD/HDD), GPU, scheda madre/BIOS, rete, batteria, temperature, USB, **monitoraggio prestazioni** (campiona CPU/RAM/disco per ~8 secondi per scovare picchi intermittenti), **test velocità disco reale** (scrive/legge un file da 100 MB).
  - **Software**: sistema operativo (produttore, modello, numero di serie, edizione Windows esatta), aggiornamenti, software installato, programmi all'avvio, processi, antivirus, driver, servizi.
  - **Problemi potenziali**: spazio disco, sovraccarico CPU, memoria insufficiente, surriscaldamento, batteria degradata, errori di sistema, processi sospetti, riavvio in sospeso, frammentazione, connettività, **cronologia affidabilità di Windows** (crash/blocchi registrati dal sistema).
- **Risultati** in un elenco ad albero colorato per gravità (OK / Attenzione / Critico / Non disponibile), con pannello dettagli a due schede:
  - **Dettagli**: dati tecnici grezzi del controllo.
  - **Consigli e fix**: suggerimenti testuali (anche di upgrade hardware, es. "aumenta la RAM", "sostituisci l'HDD con un SSD", "pulisci il dissipatore") e, dove possibile, **azioni di correzione applicabili con un click** ("Applica"), sempre con conferma esplicita prima dell'esecuzione.
  - Pulsante **"🔄 Ricontrolla"** per rieseguire subito il singolo controllo dopo aver applicato una correzione, senza dover rilanciare l'intera scansione.
- **Monitoraggio temperature reale**: oltre ai sensori esposti da `psutil` (Linux/alcuni laptop), su Windows il programma interroga il provider WMI di **LibreHardwareMonitor/OpenHardwareMonitor** se già in esecuzione, oppure prova ad avviare automaticamente una copia portatile inclusa in `tools/LibreHardwareMonitor/` (utile per l'uso da chiavetta USB). Se nessuno dei due è disponibile, il programma lo segnala con istruzioni chiare.
- **Esportazione report** in formato TXT e HTML.
- Scansione eseguita in background (l'interfaccia resta sempre reattiva).

## Requisiti

- Python 3.9 o superiore (Tkinter incluso di serie nelle installazioni standard da python.org).
- Pacchetto `psutil` (vedi `requirements.txt`).
- Alcune verifiche sono più complete su **Windows** (aggiornamenti, driver, servizi,
  batteria dettagliata, riavvio in sospeso, temperature reali) perché usano PowerShell/WMI.
  Su Linux/macOS quei controlli mostrano "Non disponibile" invece di fallire.
- Per i controlli e le correzioni più complete è consigliato eseguire il programma
  come **amministratore** su Windows.

## Monitoraggio temperature: come attivarlo su Windows

1. Scarica **LibreHardwareMonitor** (gratuito, open source):
   https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases
2. Estrai l'eseguibile nella cartella `pc_diagnostic_tool/tools/LibreHardwareMonitor/`
   (crea la cartella se non esiste), in modo che il file si trovi in
   `tools/LibreHardwareMonitor/LibreHardwareMonitor.exe`.
3. Avvia il programma normalmente: se LibreHardwareMonitor non è già in esecuzione,
   verrà avviato automaticamente in background prima di leggere le temperature.
   In alternativa puoi avviarlo manualmente tu stesso (anche come icona nella system tray)
   prima di lanciare la scansione.

## Le correzioni ("fix") disponibili

Ogni azione di correzione richiede sempre una conferma esplicita e indica il livello
di rischio:
- 🟢 **sicuro**: operazione reversibile o a basso rischio (es. pulizia file temporanei,
  svuotamento cache DNS, ottimizzazione nativa del disco).
- 🟠 **attenzione**: operazione irreversibile o delicata (es. svuotamento Cestino):
  viene sempre chiesta una conferma aggiuntiva.

Per le operazioni più delicate (chiudere un processo, disattivare un programma di
avvio, disinstallare software) il programma apre lo strumento nativo di Windows
pertinente (Task Manager, Impostazioni avvio, Gestione dispositivi, Windows Update,
Sicurezza di Windows...) così l'operatore mantiene sempre il controllo diretto
sull'azione finale, invece di un'automazione "invisibile".

## Installazione e avvio

```bash
cd pc_diagnostic_tool
pip install -r requirements.txt
python main.py
```

**Su Windows** puoi anche fare doppio clic su `avvia.bat`: installa da solo le
dipendenze (solo la prima volta) e apre il programma, senza dover usare il
terminale. Richiede comunque Python installato (da python.org, spuntando
"Add python.exe to PATH" durante l'installazione).

Su Windows, per i controlli più completi (salute dischi, driver, aggiornamenti,
antivirus) è consigliato eseguire il programma come **amministratore**.

## Struttura del progetto

```
pc_diagnostic_tool/
  main.py                  punto di ingresso
  requirements.txt
  tools/                   (opzionale) LibreHardwareMonitor/LibreHardwareMonitor.exe
  core/
    models.py               modelli dati (Status, CheckResult, Suggestion, FixAction...)
    catalog.py               elenco categorie/controlli selezionabili
    utils.py                 helper (piattaforma, comandi, formattazione)
    sensors.py               lettura temperature reali (WMI/LibreHardwareMonitor)
    checks_hardware.py       controlli hardware
    checks_software.py       controlli software
    checks_problems.py       controlli euristici sui problemi potenziali
    advisor.py               genera suggerimenti e propone i fix per ogni controllo
    fix_actions.py           implementazione delle azioni di correzione
    engine.py                orchestrazione scansione, punteggio, report
  gui/
    theme.py                 palette colori e stili ttk
    widgets.py                componenti riutilizzabili (card, gauge, righe, fix...)
    app.py                    finestra principale, navigazione, esecuzione async
    pages/
      dashboard.py
      selection.py
      results.py              risultati + consigli/fix + esportazione
```

## Suggerimenti per migliorare ulteriormente il programma

1. **Packaging eseguibile**: creare un `.exe` standalone con PyInstaller
   (`pyinstaller --onefile --windowed main.py`) così l'utente finale non deve
   installare Python — fondamentale per l'uso da chiavetta USB in azienda.
2. **Storico scansioni per PC**: salvare i risultati in un piccolo database SQLite
   (magari indicizzato per nome macchina/cliente) per confrontare l'andamento nel
   tempo e generare un report "prima/dopo l'intervento" da lasciare al cliente.
3. **Fix aggiuntivi automatizzabili in sicurezza**: disattivazione diretta di un
   singolo programma di avvio scelto dal tecnico (oggi si apre solo la finestra di
   Windows), terminazione guidata di un processo specifico con conferma del nome,
   pulizia cache aggiornamenti Windows (`SoftwareDistribution`).
4. **Localizzazione**: estrarre le stringhe in un file di traduzione per
   supportare più lingue oltre l'italiano.
5. **Firma/verifica processi sospetti**: sostituire l'euristica sui percorsi
   Temp con una verifica reale della firma digitale dell'eseguibile (Windows:
   `WinVerifyTrust` / certutil) per ridurre i falsi positivi.
6. **Test automatici**: aggiungere una suite di test (pytest) che verifichi
   che ogni funzione di controllo e ogni fix restituiscano sempre un esito
   valido anche in assenza dei permessi/programmi richiesti.
7. **Modalità scura/chiara**: aggiungere un interruttore tema chiaro/scuro
   nelle impostazioni, riusando la struttura già centralizzata in `theme.py`.
8. **Report "prima/dopo" per il cliente**: generare un PDF/HTML riepilogativo
   con lo stato iniziale, le correzioni applicate durante l'intervento e lo
   stato finale, da poter stampare o inviare via email al cliente.
9. **Profilo tecnico/cliente**: aggiungere un campo per nome cliente/PC prima
   della scansione, incluso automaticamente nei report esportati.
10. **Modalità inventario multi-PC**: se usato in azienda su più postazioni, un
    piccolo indice locale (CSV/SQLite) di tutte le scansioni fatte quel giorno.

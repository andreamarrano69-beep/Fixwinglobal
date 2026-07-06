# PC Diagnostic Tool

Programma desktop in Python (Tkinter) per l'analisi completa di un PC: hardware,
software e problemi potenziali, con interfaccia grafica moderna e controlli
selezionabili singolarmente.

## Funzionalità

- **Dashboard** con punteggio di salute (0-100), card riepilogative e avvio rapido.
- **Selezione controlli**: 28 verifiche suddivise in 3 categorie, ognuna attivabile/disattivabile:
  - **Hardware**: CPU, RAM, dischi, salute SMART, GPU, scheda madre/BIOS, rete, batteria, temperature, USB.
  - **Software**: sistema operativo, aggiornamenti, software installato, programmi all'avvio, processi, antivirus, driver, servizi.
  - **Problemi potenziali**: spazio disco, sovraccarico CPU, memoria insufficiente, surriscaldamento, batteria degradata, errori di sistema, processi sospetti, riavvio in sospeso, frammentazione, connettività.
- **Risultati** in un elenco ad albero colorato per gravità (OK / Attenzione / Critico / Non disponibile), con pannello dettagli.
- **Esportazione report** in formato TXT e HTML.
- Scansione eseguita in background (l'interfaccia resta sempre reattiva).

## Requisiti

- Python 3.9 o superiore (Tkinter incluso di serie nelle installazioni standard da python.org).
- Pacchetto `psutil` (vedi `requirements.txt`).
- Alcune verifiche sono più complete su **Windows** (aggiornamenti, driver, servizi,
  batteria dettagliata, riavvio in sospeso) perché usano PowerShell/WMI. Su Linux/macOS
  quei controlli mostrano "Non disponibile" invece di fallire.

## Installazione e avvio

```bash
cd pc_diagnostic_tool
pip install -r requirements.txt
python main.py
```

Su Windows, per i controlli più completi (salute dischi, driver, aggiornamenti,
antivirus) è consigliato eseguire il programma come **amministratore**.

## Struttura del progetto

```
pc_diagnostic_tool/
  main.py                  punto di ingresso
  requirements.txt
  core/
    models.py               modelli dati (Status, CheckResult, Category...)
    catalog.py               elenco categorie/controlli selezionabili
    utils.py                 helper (piattaforma, comandi, formattazione)
    checks_hardware.py       controlli hardware
    checks_software.py       controlli software
    checks_problems.py       controlli euristici sui problemi potenziali
    engine.py                orchestrazione scansione, punteggio, report
  gui/
    theme.py                 palette colori e stili ttk
    widgets.py                componenti riutilizzabili (card, gauge, righe...)
    app.py                    finestra principale e navigazione
    pages/
      dashboard.py
      selection.py
      results.py
```

## Suggerimenti per migliorare ulteriormente il programma

1. **Packaging eseguibile**: creare un `.exe` standalone con PyInstaller
   (`pyinstaller --onefile --windowed main.py`) così l'utente finale non deve
   installare Python.
2. **Sensori di temperatura su Windows**: integrare `OpenHardwareMonitorLib`
   (via `pythonnet`) o `LibreHardwareMonitor` per leggere temperature CPU/GPU,
   dato che `psutil` non le espone su Windows.
3. **Storico scansioni**: salvare i risultati in un piccolo database SQLite
   per confrontare l'andamento nel tempo (grafico punteggio salute nei giorni).
4. **Pianificazione automatica**: aggiungere una scansione periodica in
   background (es. ogni avvio del PC) con notifiche di sistema in caso di problemi critici.
5. **Azioni correttive guidate**: per ogni problema rilevato, offrire un
   pulsante "Risolvi" (es. libera spazio disco, disattiva un programma di avvio,
   apre Gestione dispositivi) invece del solo referto.
6. **Localizzazione**: estrarre le stringhe in un file di traduzione per
   supportare più lingue oltre l'italiano.
7. **Firma/verifica processi sospetti**: sostituire l'euristica sui percorsi
   Temp con una verifica reale della firma digitale dell'eseguibile (Windows:
   `WinVerifyTrust` / certutil) per ridurre i falsi positivi.
8. **Test automatici**: aggiungere una suite di test (pytest) che verifichi
   che ogni funzione di controllo restituisca sempre un `CheckResult` valido
   anche in assenza dei permessi/programmi richiesti.
9. **Modalità scura/chiara**: aggiungere un interruttore tema chiaro/scuro
   nelle impostazioni, riusando la struttura già centralizzata in `theme.py`.
10. **Aggiornamento automatico dell'app**: controllo versione all'avvio con
    link alla nuova release, utile se distribuito a più utenti.

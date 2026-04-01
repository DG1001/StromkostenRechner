# Stromkosten-Rechner - Spezifikation

## Projektübersicht
- **Name**: Stromkosten-Rechner
- **Typ**: Webanwendung (Python/FastAPI + HTML/JS)
- **Funktion**: Berechnung und Visualisierung von Stromverbrauch und -kosten für ein Mehrfamilienhaus
- **Zielnutzer**: Eigenheimbesitzer mit Mietwohnung

## Datenmodelle

### Stromtarif
- `id`: Integer (PK)
- `gueltig_ab`: Date (gültig ab Datum)
- `grundkosten_jahr`: Decimal (Grundkosten pro Jahr in €)
- `arbeitspreis_kwh`: Decimal (Arbeitspreis pro kWh in €)

### Zählerstand
- `id`: Integer (PK)
- `standort`: Enum (HAUS, DACHGESCHOSS, MIETWOHNUNG)
- `zaehlerstand`: Integer (kWh, ohne Kommastellen)
- `ablesedatum`: Date
- `bemerkung`: Optional String
- Pro Ablesedatum werden alle drei Standorte erfasst

## Berechnungen

### Erdgeschoss
- `EG = Haus - Dachgeschoss - Mietwohnung`

### Verbrauch im Zeitraum
- Differenz zwischen zwei Zählerständen

### Kosten im Zeitraum
1. Grundkosten anteilig: `(grundkosten_jahr / 365) * tage`
2. Arbeitskosten: `verbrauch_kwh * arbeitspreis_kwh`
3. Summe: Grundkosten + Arbeitskosten

### Durchschnittswerte
- Alle erfassten Zeiträume aggregiert
- Verbrauch pro Tag = Gesamtverbrauch / Gesamttage
- Kosten pro Tag = Gesamtkosten / Gesamttage

### Mietwohnung-Abrechnung (Jahr)
- Zeitraum: Erster Ablesezeitpunkt im gewählten Jahr bis erster Ablesezeitpunkt im Folgejahr
- Grundkosten: 18% des Jahresgrundpreises (nicht tagesgenau)
- Arbeitskosten: Verbrauch * Arbeitspreis pro kWh

## UI-Funktionen

### Tarife verwalten
- Liste aller Tarife mit Gültigkeitsdatum
- Formular zum Hinzufügen neuer Tarife
- **Bearbeiten** bestehender Tarife (Edit-Button)
- **Löschen** bestehender Tarife (Delete-Button)

### Zählerstände verwalten
- Liste aller Zählerstände nach Datum gruppiert
- Formular zum Erfassen neuer Zählerstände
- **Bearbeiten** bestehender Zählerstände (Edit-Button)
- **Löschen** bestehender Zählerstände (Delete-Button)
- **Filter** nach Standort/Stockwerk (Haus, Dachgeschoss, Mietwohnung)
- **Sortierung** nach Ablesedatum, Standort oder Zählerstand (auf-/absteigend)

### Auswertungen
- Dashboard mit:
  - Tage seit letzter Ablesung
  - Verbrauch pro Tag im Ablesezeitraum (Gesamt + je Stockwerk: Dachgeschoss, Erdgeschoss, Mietwohnung)
  - Angefallene Kosten gesamt im Ablesezeitraum (Gesamt + je Stockwerk)
  - Durchschnittliche Verbrauch/Kosten pro Tag über alle erfassten Zeiträume
  - Tagesgenaue Verbrauchswerte werden mit 2 Nachkommastellen dargestellt

### Grafiken
1. **Liniendiagramm Verbrauch**: Verbrauch pro Tag über Zeit für alle Stockwerke (Haus, Dachgeschoss, Erdgeschoss, Mietwohnung) als separate Linien mit realer Zeitachse
2. **Liniendiagramm Kosten**: Kosten pro Tag über Zeit für alle Stockwerke als separate Linien mit realer Zeitachse
3. **Balkendiagramm**: Verbrauchsanteile der Stockwerke (Dachgeschoss, Erdgeschoss, Mietwohnung) für jeden Zeitraum

### Mietwohnung-Abrechnung
- Jahr auswählen
- Abrechnungsanzeige mit Zählerständen, Verbrauch, Kosten (Grundkosten 18%, Arbeitskosten)

### Daten-Backup und Wiederherstellung
- Backup der SQLite-Datenbank über die UI herunterladen
- Backup-Datei (`.db`) über die UI wieder einspielen
- Beim Restore wird die Backup-Datei auf gültige Tabellenstruktur geprüft

## Darstellungsformat
- Datumsanzeige im Frontend einheitlich als `tt.mm.jjjj`
- Zählerstände werden ohne Kommastellen erfasst und dargestellt
- Tageswerte (z. B. kWh/Tag, EUR/Tag) werden mit 2 Nachkommastellen dargestellt

## Technische Umsetzung
- Backend: FastAPI (Python)
- Frontend: HTML + vanilla JS + Chart.js
- Datenhaltung: SQLite (Dateipfad über `STROM_DB_PATH` konfigurierbar)
- Port: 8000, Host: 0.0.0.0

## Deployment
- Containerisierung über Docker (`Dockerfile`)
- Persistente Daten in Container-Umgebungen über Volume-Mount auf den DB-Pfad (z. B. `/data/strom.db`)
- CI/CD via GitHub Actions: Bei Push auf `main` wird ein Multi-Arch-Image (`linux/amd64`, `linux/arm64`) gebaut und nach GHCR veröffentlicht
- Ziel-Registry: `ghcr.io/dg1001/<repo-name>`

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
- `zaehlerstand`: Decimal (kWh)
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
- Zeitraum: Erster Ablesezeitpunkt im Januar des Jahres bis erster Ablesezeitpunkt im Januar des Folgejahres
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

### Auswertungen
- Dashboard mit:
  - Tage seit letzter Ablesung
  - Verbrauch pro Tag im Ablesezeitraum (Gesamt + je Stockwerk: Haus, Dachgeschoss, Erdgeschoss, Mietwohnung)
  - Angefallene Kosten gesamt im Ablesezeitraum (Gesamt + je Stockwerk)
  - Durchschnittliche Verbrauch/Kosten pro Tag über alle erfassten Zeiträume

### Grafiken
1. **Liniendiagramm Verbrauch**: Verbrauch über Zeit für alle Stockwerke (Haus, Dachgeschoss, Erdgeschoss, Mietwohnung) als separate Linien
2. **Liniendiagramm Kosten**: Kosten über Zeit für alle Stockwerke als separate Linien
3. **Balkendiagramm**: Verbrauchsanteile der Stockwerke (Dachgeschoss, Erdgeschoss, Mietwohnung) zum Stichtag

### Mietwohnung-Abrechnung
- Jahr auswählen
- Abrechnungsanzeige mit Zählerständen, Verbrauch, Kosten (Grundkosten 18%, Arbeitskosten)

## Technische Umsetzung
- Backend: FastAPI (Python)
- Frontend: HTML + vanilla JS + Chart.js
- Datenhaltung: SQLite (einfache Datei)
- Port: 8000, Host: 0.0.0.0

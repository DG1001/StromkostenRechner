# Stromkosten-Rechner

Webanwendung zur Erfassung von Stromzaehlerstaenden und zur Auswertung von Verbrauch und Kosten fuer ein Mehrfamilienhaus (Haus, Dachgeschoss, Mietwohnung, Erdgeschoss berechnet).

Die Anwendung besteht aus:
- FastAPI-Backend (Python)
- HTML/JavaScript-Frontend mit Chart.js
- SQLite als Datenbank

## Funktionen

- Verwaltung von Stromtarifen mit `gueltig_ab`, Grundkosten/Jahr und Arbeitspreis/kWh
- Erfassung, Bearbeitung und Loeschen von Zaehlerstaenden
- Filter und Sortierung in der Zaehlerstandsliste
- Auswertungen pro Zeitraum inklusive Tageswerten (`kWh/Tag`, `EUR/Tag`)
- Diagramme mit realer Zeitachse (ungleiche Zeitabstaende werden korrekt beruecksichtigt)
- Mietwohnungsabrechnung je Jahr (erstes Ablesedatum im Jahr bis erstes im Folgejahr)
- Daten-Backup und Restore direkt ueber die UI

## Darstellungsregeln

- Datumsanzeige im Format `tt.mm.jjjj`
- Zaehlerstaende werden ohne Kommastellen erfasst/dargestellt
- Tagesgenaue Werte werden mit 2 Nachkommastellen angezeigt

## Projektstruktur

- `app/main.py` - FastAPI-App und Berechnungslogik
- `static/index.html` - Frontend inkl. UI-Logik
- `SPEC.md` - Fachliche Spezifikation
- `Dockerfile` - Container-Build
- `.github/workflows/docker-publish.yml` - Build/Push nach GHCR

## Lokal starten

Voraussetzungen: Python 3.11+

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Dann im Browser: `http://localhost:8000`

## Konfiguration

- `STROM_DB_PATH` (optional): Pfad zur SQLite-Datei
  - Default lokal: `strom.db` im Projektverzeichnis
  - Empfohlen im Container: `/data/strom.db`

Beispiel:

```bash
STROM_DB_PATH=/data/strom.db uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker

### Lokal bauen und starten

```bash
docker build -t stromkosten-rechner:latest .
docker run -d \
  --name stromkosten-rechner \
  -p 8000:8000 \
  -e STROM_DB_PATH=/data/strom.db \
  -v $(pwd)/data:/data \
  stromkosten-rechner:latest
```

## GitHub Actions + GHCR

Bei Push auf `main` wird automatisch ein Multi-Arch-Image gebaut und nach GHCR gepusht:

- Workflow: `.github/workflows/docker-publish.yml`
- Registry: `ghcr.io`
- Image: `ghcr.io/dg1001/<repo-name>`
- Plattformen: `linux/amd64`, `linux/arm64`
- Tags: `latest`, `sha-<commit>`

Hinweis: Fuer Pull auf einem privaten Package ist ein GHCR-Login (PAT mit `read:packages`) erforderlich.

## Deployment auf QNAP Container Station (TS-233)

1. Image in Container Station ziehen: `ghcr.io/dg1001/<repo-name>:latest`
2. Port-Mapping setzen: `8000 -> 8000`
3. Persistentes Volume mounten, z. B.:
   - Host: `/share/Container/stromkosten`
   - Container: `/data`
4. Umgebungsvariable setzen: `STROM_DB_PATH=/data/strom.db`
5. Container starten

## Backup und Restore

In der UI gibt es den Bereich **"Daten sichern und wiederherstellen"**:

- **Backup herunterladen**: exportiert die aktuelle SQLite-Datei
- **Backup einspielen**: importiert eine `.db`-Datei (Schema wird geprueft)

### Wichtige Hinweise

- Nur `.db`-Dateien werden akzeptiert
- Bei Upload-Limits vom Proxy/Server kann ein Fehler wie `413` auftreten
- Fuer stabile Persistenz immer Volume-Mount + `STROM_DB_PATH` nutzen

## API-Ueberblick

- Tarife: `GET/POST/PUT/DELETE /api/tarife`
- Zaehlerstaende: `GET/POST/PUT/DELETE /api/zaehlerstaende`
- Auswertung: `GET /api/auswertung`
- Mietwohnung-Abrechnung: `GET /api/mietwohnung/{jahr}`
- DB-Backup: `GET /api/db/backup`
- DB-Restore: `POST /api/db/restore`

## Troubleshooting

- Diagramme aktualisieren sich nicht:
  - pruefen, ob fuer ein Datum alle drei Standorte vorhanden sind (`HAUS`, `DACHGESCHOSS`, `MIETWOHNUNG`)
- Restore-Fehler:
  - Dateiformat pruefen (`.db`)
  - Proxy-Upload-Limit pruefen (`413`)
  - Volume-Mount und `STROM_DB_PATH` pruefen

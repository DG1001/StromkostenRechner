from datetime import date
import os
from pathlib import Path
import tempfile
from typing import Optional
import sqlite3

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Stromkosten-Rechner")

BASE_DIR = Path(__file__).parent.parent
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)


def resolve_db_path() -> Path:
    configured = os.getenv("STROM_DB_PATH")
    if not configured:
        return BASE_DIR / "strom.db"
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate


DB_PATH = resolve_db_path()

app.mount("/static", StaticFiles(directory=str(static_dir)), "static")


class Stromtarif(BaseModel):
    id: Optional[int] = None
    gueltig_ab: date
    grundkosten_jahr: float
    arbeitspreis_kwh: float


class Zaehlerstand(BaseModel):
    id: Optional[int] = None
    standort: str
    zaehlerstand: float
    ablesedatum: date
    bemerkung: Optional[str] = None


STANDORTE = ("HAUS", "DACHGESCHOSS", "MIETWOHNUNG")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS tarife (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gueltig_ab DATE NOT NULL,
        grundkosten_jahr REAL NOT NULL,
        arbeitspreis_kwh REAL NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS zaehlerstaende (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        standort TEXT NOT NULL,
        zaehlerstand REAL NOT NULL,
        ablesedatum DATE NOT NULL,
        bemerkung TEXT
    )""")
    conn.commit()
    conn.close()


def validate_backup_schema(db_file: Path):
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    required_tables = {"tarife", "zaehlerstaende"}
    missing = required_tables - tables
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "Backup-Datei ungültig: fehlende Tabellen " + ", ".join(sorted(missing))
            ),
        )


def cleanup_file(path: str):
    p = Path(path)
    if p.exists():
        p.unlink()


def get_reading(
    conn: sqlite3.Connection, standort: str, ablesedatum: str
) -> Optional[float]:
    cur = conn.execute(
        "SELECT zaehlerstand FROM zaehlerstaende WHERE standort = ? AND ablesedatum = ? ORDER BY id DESC LIMIT 1",
        (standort, ablesedatum),
    )
    row = cur.fetchone()
    return float(row[0]) if row else None


def get_complete_dates(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        """
        SELECT ablesedatum
        FROM zaehlerstaende
        GROUP BY ablesedatum
        HAVING SUM(CASE WHEN standort = 'HAUS' THEN 1 ELSE 0 END) > 0
           AND SUM(CASE WHEN standort = 'DACHGESCHOSS' THEN 1 ELSE 0 END) > 0
           AND SUM(CASE WHEN standort = 'MIETWOHNUNG' THEN 1 ELSE 0 END) > 0
        ORDER BY ablesedatum
        """
    )
    return [row[0] for row in cur.fetchall()]


def get_tarif_gueltig(zu_datum: date) -> Optional[dict]:
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM tarife WHERE gueltig_ab <= ? ORDER BY gueltig_ab DESC LIMIT 1",
        (zu_datum.isoformat(),),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def berechne_kosten(verbrauch_kwh: float, tage: int, zu_datum: date) -> Optional[dict]:
    tarif = get_tarif_gueltig(zu_datum)
    if not tarif:
        return None

    grundkosten = (tarif["grundkosten_jahr"] / 365) * tage
    arbeitskosten = verbrauch_kwh * tarif["arbeitspreis_kwh"]

    return {
        "grundkosten": round(grundkosten, 2),
        "arbeitskosten": round(arbeitskosten, 2),
        "gesamtkosten": round(grundkosten + arbeitskosten, 2),
    }


def berechne_eg(haus: float, dach: float, miet: float) -> float:
    return max(0.0, haus - dach - miet)


def calculate_period(
    conn: sqlite3.Connection, prev_date: str, curr_date: str
) -> Optional[dict]:
    tage = (date.fromisoformat(curr_date) - date.fromisoformat(prev_date)).days
    if tage <= 0:
        return None

    verbrauche = {}
    kosten = {}

    for standort, key in (
        ("HAUS", "haus"),
        ("DACHGESCHOSS", "dach"),
        ("MIETWOHNUNG", "miet"),
    ):
        curr = get_reading(conn, standort, curr_date)
        prev = get_reading(conn, standort, prev_date)
        if curr is None or prev is None:
            return None
        verbrauch = round(curr - prev, 2)
        verbrauche[key] = verbrauch
        k = berechne_kosten(verbrauch, tage, date.fromisoformat(curr_date))
        kosten[key] = k["gesamtkosten"] if k else 0.0

    verbrauche["eg"] = round(
        berechne_eg(verbrauche["haus"], verbrauche["dach"], verbrauche["miet"]), 2
    )
    eg_kosten = berechne_kosten(verbrauche["eg"], tage, date.fromisoformat(curr_date))
    kosten["eg"] = eg_kosten["gesamtkosten"] if eg_kosten else 0.0

    verbrauche["gesamt"] = verbrauche["haus"]
    kosten["gesamt"] = kosten["haus"]

    return {
        "von": prev_date,
        "bis": curr_date,
        "datum": curr_date,
        "tage": tage,
        "verbrauche": verbrauche,
        "kosten": kosten,
    }


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index():
    return (static_dir / "index.html").read_text()


# === TARIFE ===


@app.get("/api/tarife")
def get_tarife():
    conn = get_db()
    cur = conn.execute("SELECT * FROM tarife ORDER BY gueltig_ab DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/tarife")
def add_tarif(tarif: Stromtarif):
    conn = get_db()
    conn.execute(
        "INSERT INTO tarife (gueltig_ab, grundkosten_jahr, arbeitspreis_kwh) VALUES (?, ?, ?)",
        (tarif.gueltig_ab.isoformat(), tarif.grundkosten_jahr, tarif.arbeitspreis_kwh),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.put("/api/tarife/{tarif_id}")
def update_tarif(tarif_id: int, tarif: Stromtarif):
    conn = get_db()
    cur = conn.execute("SELECT id FROM tarife WHERE id = ?", (tarif_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Tarif nicht gefunden")
    conn.execute(
        "UPDATE tarife SET gueltig_ab = ?, grundkosten_jahr = ?, arbeitspreis_kwh = ? WHERE id = ?",
        (
            tarif.gueltig_ab.isoformat(),
            tarif.grundkosten_jahr,
            tarif.arbeitspreis_kwh,
            tarif_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/tarife/{tarif_id}")
def delete_tarif(tarif_id: int):
    conn = get_db()
    cur = conn.execute("SELECT id FROM tarife WHERE id = ?", (tarif_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Tarif nicht gefunden")
    conn.execute("DELETE FROM tarife WHERE id = ?", (tarif_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


# === ZAEHLERSTAENDE ===


@app.get("/api/zaehlerstaende")
def get_zaehlerstaende():
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM zaehlerstaende ORDER BY ablesedatum DESC, standort"
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/zaehlerstaende")
def add_zaehlerstand(zaehlerstand: Zaehlerstand):
    if zaehlerstand.standort not in STANDORTE:
        raise HTTPException(status_code=400, detail="Ungültiger Standort")
    meter_value = float(zaehlerstand.zaehlerstand)
    if not meter_value.is_integer():
        raise HTTPException(
            status_code=400,
            detail="Der Zählerstand muss ohne Kommastellen erfasst werden",
        )
    conn = get_db()
    conn.execute(
        "INSERT INTO zaehlerstaende (standort, zaehlerstand, ablesedatum, bemerkung) VALUES (?, ?, ?, ?)",
        (
            zaehlerstand.standort,
            int(meter_value),
            zaehlerstand.ablesedatum.isoformat(),
            zaehlerstand.bemerkung,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.put("/api/zaehlerstaende/{zaehlerstand_id}")
def update_zaehlerstand(zaehlerstand_id: int, zaehlerstand: Zaehlerstand):
    if zaehlerstand.standort not in STANDORTE:
        raise HTTPException(status_code=400, detail="Ungültiger Standort")
    meter_value = float(zaehlerstand.zaehlerstand)
    if not meter_value.is_integer():
        raise HTTPException(
            status_code=400,
            detail="Der Zählerstand muss ohne Kommastellen erfasst werden",
        )
    conn = get_db()
    cur = conn.execute("SELECT id FROM zaehlerstaende WHERE id = ?", (zaehlerstand_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Zählerstand nicht gefunden")
    conn.execute(
        "UPDATE zaehlerstaende SET standort = ?, zaehlerstand = ?, ablesedatum = ?, bemerkung = ? WHERE id = ?",
        (
            zaehlerstand.standort,
            int(meter_value),
            zaehlerstand.ablesedatum.isoformat(),
            zaehlerstand.bemerkung,
            zaehlerstand_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/zaehlerstaende/{zaehlerstand_id}")
def delete_zaehlerstand(zaehlerstand_id: int):
    conn = get_db()
    cur = conn.execute("SELECT id FROM zaehlerstaende WHERE id = ?", (zaehlerstand_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Zählerstand nicht gefunden")
    conn.execute("DELETE FROM zaehlerstaende WHERE id = ?", (zaehlerstand_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/db/backup")
def backup_database(background_tasks: BackgroundTasks):
    if not DB_PATH.exists():
        init_db()

    fd, temp_file = tempfile.mkstemp(prefix="strom_backup_", suffix=".db")
    os.close(fd)
    temp_path = Path(temp_file)

    source_conn = get_db()
    backup_conn = sqlite3.connect(temp_path)
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()

    filename = f"strom_backup_{date.today().isoformat()}.db"
    background_tasks.add_task(cleanup_file, str(temp_path))

    return FileResponse(
        path=str(temp_path),
        media_type="application/octet-stream",
        filename=filename,
    )


@app.post("/api/db/restore")
async def restore_database(backup_file: UploadFile = File(...)):
    if not backup_file.filename or not backup_file.filename.lower().endswith(".db"):
        raise HTTPException(status_code=400, detail="Bitte eine .db-Datei hochladen")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_file = tempfile.mkstemp(
        prefix="strom_restore_",
        suffix=".db",
        dir=str(DB_PATH.parent),
    )
    os.close(fd)
    temp_path = Path(temp_file)

    try:
        has_content = False
        with temp_path.open("wb") as out_file:
            while True:
                chunk = await backup_file.read(1024 * 1024)
                if not chunk:
                    break
                has_content = True
                out_file.write(chunk)

        if not has_content:
            raise HTTPException(
                status_code=400, detail="Leere Datei kann nicht importiert werden"
            )

        validate_backup_schema(temp_path)

        os.replace(temp_path, DB_PATH)
        return {"status": "ok"}
    finally:
        await backup_file.close()
        if temp_path.exists():
            temp_path.unlink()


# === AUSWERTUNG ===


@app.get("/api/auswertung")
def auswertung():
    conn = get_db()

    dates = get_complete_dates(conn)
    if len(dates) < 2:
        conn.close()
        return {"fehler": "Mindestens zwei Ablesezeitpunkte erforderlich"}

    periods = []
    for i in range(1, len(dates)):
        period = calculate_period(conn, dates[i - 1], dates[i])
        if period:
            periods.append(period)

    if not periods:
        conn.close()
        return {"fehler": "Keine auswertbaren Zeiträume gefunden"}

    latest_period = periods[-1]

    total_days = sum(period["tage"] for period in periods)
    keys = ("gesamt", "haus", "dach", "eg", "miet")

    sum_verbrauch = {key: 0.0 for key in keys}
    sum_kosten = {key: 0.0 for key in keys}
    for period in periods:
        for key in keys:
            sum_verbrauch[key] += period["verbrauche"][key]
            sum_kosten[key] += period["kosten"][key]

    avg_verbrauch = {
        key: round(sum_verbrauch[key] / total_days, 4) if total_days else 0.0
        for key in keys
    }
    avg_kosten = {
        key: round(sum_kosten[key] / total_days, 4) if total_days else 0.0
        for key in keys
    }

    verbrauchs_reihen = []
    kosten_reihen = []
    for period in periods:
        verbrauchs_reihen.append(
            {
                "von": period["von"],
                "bis": period["bis"],
                "datum": period["datum"],
                "tage": period["tage"],
                **period["verbrauche"],
            }
        )
        kosten_reihen.append(
            {
                "von": period["von"],
                "bis": period["bis"],
                "datum": period["datum"],
                "tage": period["tage"],
                **period["kosten"],
            }
        )

    conn.close()

    return {
        "tage_seit_letzt": latest_period["tage"],
        "latest_date": latest_period["datum"],
        "verbrauche": latest_period["verbrauche"],
        "kosten": latest_period["kosten"],
        "durchschnitt": {
            "verbrauch_pro_tag": avg_verbrauch["gesamt"],
            "kosten_pro_tag": avg_kosten["gesamt"],
            "verbrauch_pro_tag_je_bereich": avg_verbrauch,
            "kosten_pro_tag_je_bereich": avg_kosten,
        },
        "ablesezeitpunkte": dates,
        "verbrauchs_reihen": verbrauchs_reihen,
        "kosten_reihen": kosten_reihen,
    }


# === MIETWOHNUNG ABRECHNUNG ===


@app.get("/api/mietwohnung/{jahr}")
def mietwohnung_abrechnung(jahr: int):
    conn = get_db()

    cur = conn.execute(
        """
        SELECT *
        FROM zaehlerstaende
        WHERE standort = 'MIETWOHNUNG'
          AND strftime('%Y', ablesedatum) = ?
        ORDER BY ablesedatum ASC
        LIMIT 1
        """,
        (str(jahr),),
    )
    start = cur.fetchone()
    if not start:
        conn.close()
        return {"fehler": f"Kein Ablesezeitpunkt im Jahr {jahr} gefunden"}

    next_year = str(jahr + 1)
    cur = conn.execute(
        """
        SELECT *
        FROM zaehlerstaende
        WHERE standort = 'MIETWOHNUNG'
          AND strftime('%Y', ablesedatum) = ?
        ORDER BY ablesedatum ASC
        LIMIT 1
        """,
        (next_year,),
    )
    end = cur.fetchone()
    if not end:
        conn.close()
        return {"fehler": f"Kein Ablesezeitpunkt im Jahr {jahr + 1} gefunden"}

    start = dict(start)
    end = dict(end)

    verbrauch = round(float(end["zaehlerstand"]) - float(start["zaehlerstand"]), 2)
    tage = (
        date.fromisoformat(end["ablesedatum"])
        - date.fromisoformat(start["ablesedatum"])
    ).days

    tarif = get_tarif_gueltig(date.fromisoformat(end["ablesedatum"]))
    if not tarif:
        conn.close()
        return {"fehler": "Kein gültiger Tarif gefunden"}

    grundkosten_anteil = round(tarif["grundkosten_jahr"] * 0.18, 2)
    arbeitskosten = round(verbrauch * tarif["arbeitspreis_kwh"], 2)
    gesamtkosten = round(grundkosten_anteil + arbeitskosten, 2)

    conn.close()

    return {
        "jahr": jahr,
        "zeitraum_von": start["ablesedatum"],
        "zeitraum_bis": end["ablesedatum"],
        "tage": tage,
        "zaehlerstand_von": start["zaehlerstand"],
        "zaehlerstand_bis": end["zaehlerstand"],
        "verbrauch_kwh": verbrauch,
        "grundkosten_anteil": grundkosten_anteil,
        "arbeitskosten": arbeitskosten,
        "gesamtkosten": gesamtkosten,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

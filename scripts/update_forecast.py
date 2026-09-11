#!/usr/bin/env python3
"""
Scarica dati reali OSMER FVG (stazione di Trieste + bollettino bora zona costa Z4)
e li scrive in data.json, così la pagina (che nel browser non può leggerli per il
blocco CORS) li mostra come dati "misurati ora" invece di sola previsione.

Eseguito da GitHub Actions due volte al giorno (vedi .github/workflows/update-forecast.yml).
Non tocca le previsioni giorno per giorno: quelle restano calcolate dal browser
al volo con Open-Meteo, quando l'utente apre la pagina o preme "Aggiorna ora".
"""
import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

OSMER_MARE_URL = "https://www.osmer.fvg.it/mare.php?m=0"
OSMER_BOLLETTINO_URL = "https://www.osmer.fvg.it/previsioni.php?dettaglio=Z4"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; bora-o-libri-bot/1.0; +personal use)"}
TIMEOUT = 20


def fetch_realtime_wind():
    """Legge il vento reale misurato ora alla stazione di Trieste da OSMER."""
    try:
        r = requests.get(OSMER_MARE_URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Formato tipico: "Trieste - 11-09-2026 11:00 CEST temperatura 17.9 °C
        # umidità 81 % vento medio E 20 kt vento max E 32 kt" — usiamo "vento medio"
        # come ancora (più affidabile della sola ora, che è precedeuta dalla data
        # con altre cifre).
        m = re.search(
            r"Trieste\b.{0,120}?(\d{1,2}[:.]\d{2}).{0,120}?"
            r"vento medio\s+([NSEW]{1,3})\s+(\d{1,3})\s*kt",
            text,
            re.IGNORECASE,
        )
        if not m:
            return None
        time_str, direction, speed_kt = m.group(1), m.group(2).upper(), int(m.group(3))
        return {
            "station": "Trieste (OSMER)",
            "observedAtLabel": time_str,
            "windKt": speed_kt,
            "windKmh": round(speed_kt * 1.852),
            "direction": direction,
        }
    except Exception as e:
        print(f"[warn] impossibile leggere il vento reale da OSMER: {e}", file=sys.stderr)
        return None


# Zone con cui OSMER divide il Friuli Venezia Giulia nei suoi bollettini: usate
# come "paletti" per capire dove finisce il testo della zona Costa (quella che
# comprende Trieste) ed evitare di prendere previsioni di montagna/pianura.
OTHER_ZONE_MARKERS = [
    "montagna", "alta pianura", "bassa pianura", "pianura", "carnia",
    "prealpi", "alpi giulie", "collina",
]


def fetch_bulletin_excerpt():
    """Legge il testo del bollettino ufficiale bora specifico per la zona Costa
    (quella che comprende Trieste). La pagina ha una "situazione generale"
    valida per tutta la regione (di solito la pioggia è descritta lì) e poi
    una riga breve per zona (es. "Sulla costa ... Bora moderata..."):
    prendiamo entrambe invece di un paragrafo scelto a caso."""
    try:
        r = requests.get(OSMER_BOLLETTINO_URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)

        parts = []

        g = re.search(r"situazione generale\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
        if g:
            general = g.group(1)
            stop = re.search(
                r"\b(?:sulla costa|in montagna|in pianura|in carnia)\b",
                general,
                re.IGNORECASE,
            )
            general = general[: stop.start()] if stop else general[:450]
            general = general.strip(" .:-–—")
            if general:
                parts.append(general + ".")

        c = re.search(r"sulla costa\b\s*(.+?\.)(?:\s*.+?\.)?", text, re.IGNORECASE)
        if c:
            parts.append(c.group(0).strip())

        if not parts:
            return _fallback_excerpt(text)

        excerpt = " ".join(parts).strip()
        if len(excerpt) > 700:
            excerpt = excerpt[:700].rstrip() + "…"
        return excerpt
    except Exception as e:
        print(f"[warn] impossibile leggere il bollettino OSMER: {e}", file=sys.stderr)
        return None


def _fallback_excerpt(text):
    """Se non troviamo l'intestazione 'Costa', ripieghiamo sul paragrafo più
    lungo che parla di meteo, meglio di niente ma meno preciso."""
    m = re.search(
        r"(?:[^.]{0,40}(?:bora|pioggia|temporal|nuvol)[^.]{0,400}\.)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(0).strip()
    return None


def main():
    now = datetime.now(timezone.utc)
    data = {
        "generatedAtUtc": now.isoformat(timespec="seconds"),
        "realtime": fetch_realtime_wind(),
        "bulletinExcerpt": fetch_bulletin_excerpt(),
        "bulletinUrl": OSMER_BOLLETTINO_URL,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

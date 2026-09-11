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

        m = re.search(
            r"Trieste[^0-9]{0,80}?(\d{1,2}[:.]\d{2})[^0-9A-Z]{0,40}?"
            r"([NSEW]{1,3})\s*[- ]?\s*(\d{1,3})\s*kt",
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


def fetch_bulletin_excerpt():
    """Legge un breve estratto testuale del bollettino ufficiale bora (zona Z4)."""
    try:
        r = requests.get(OSMER_BOLLETTINO_URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        candidates = soup.find_all(["p", "div"], limit=400)
        best = ""
        for el in candidates:
            t = el.get_text(" ", strip=True)
            if len(t) > len(best) and any(
                kw in t.lower() for kw in ["bora", "vento", "pioggia", "previs"]
            ):
                best = t
        if not best:
            return None
        excerpt = best[:600].rstrip()
        if len(best) > 600:
            excerpt += "…"
        return excerpt
    except Exception as e:
        print(f"[warn] impossibile leggere il bollettino OSMER: {e}", file=sys.stderr)
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

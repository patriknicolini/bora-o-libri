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

#!/usr/bin/env python3
"""Aktualisiert die Daten für das Teconomic-News-Dashboard.

Läuft in einer GitHub Action (siehe .github/workflows/update.yml).
Nur Python-Standardbibliothek, keine Installation nötig.

  python scripts/update.py              Kurse immer, Nachrichten + Podcast
                                        einmal täglich ab 7:00 Uhr (Berlin)
  python scripts/update.py --force-news Nachrichten sofort neu holen

Optionale Umgebungsvariablen:
  ANTHROPIC_API_KEY  Schlüssel für die KI-Kernaussagen (ohne Schlüssel
                     werden die Anreißer der Quellen verwendet)
  CLAUDE_MODEL       Modell-ID, Standard: claude-haiku-4-5-20251001
"""
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BERLIN = ZoneInfo("Europe/Berlin")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
NEWS_HOUR = 7  # ab dieser Uhrzeit (Berlin) werden die Tagesnachrichten erstellt

# ---------------------------------------------------------------- Hilfen

def fetch(url, headers=None, data=None, timeout=25, tries=3):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def load_json(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


def save_json(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def now_berlin():
    return dt.datetime.now(BERLIN)


def label_de(d):
    return d.strftime("%d.%m.%Y, %H:%M Uhr")


def clean(text, limit=400):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]

# ---------------------------------------------------------------- Kurse

TICKERS = {
    # Indizes
    "dax": "^GDAXI", "mdax": "^MDAXI", "sdax": "^SDAXI", "dow": "^DJI",
    "nasdaq": "^NDX", "sp500": "^GSPC", "stoxx": "^STOXX50E", "ftse": "^FTSE",
    "nikkei": "^N225",
    # DAX-Werte
    "adidas": "ADS.DE", "airbus": "AIR.DE", "allianz": "ALV.DE", "basf": "BAS.DE",
    "bayer": "BAYN.DE", "beiersdorf": "BEI.DE", "bmw": "BMW.DE", "brenntag": "BNR.DE",
    "commerzbank": "CBK.DE", "continental": "CON.DE", "covestro": "1COV.DE",
    "daimlertruck": "DTG.DE", "db": "DBK.DE", "deutscheboerse": "DB1.DE",
    "dhlgroup": "DHL.DE", "telekom": "DTE.DE", "eon": "EOAN.DE", "fresenius": "FRE.DE",
    "fmc": "FME.DE", "hannoverrueck": "HNR1.DE", "heidelbergmat": "HEI.DE",
    "henkel": "HEN3.DE", "infineon": "IFX.DE", "mbg": "MBG.DE", "merck": "MRK.DE",
    "mtu": "MTX.DE", "munichre": "MUV2.DE", "porscheag": "P911.DE", "porschese": "PAH3.DE",
    "qiagen": "QIA.DE", "rheinmetall": "RHM.DE", "rwe": "RWE.DE", "sap": "SAP.DE",
    "sartorius": "SRT3.DE", "siemens": "SIE.DE", "siemensenergy": "ENR.DE",
    "siemenshealth": "SHL.DE", "symrise": "SY1.DE", "vw": "VOW3.DE", "vonovia": "VNA.DE",
    "zalando": "ZAL.DE",
    # International
    "apple": "AAPL", "msft": "MSFT", "nvda": "NVDA", "amzn": "AMZN", "googl": "GOOGL",
    "meta": "META", "tsla": "TSLA", "brka": "BRK-B", "lly": "LLY", "v": "V", "ma": "MA",
    "jpm": "JPM", "jnj": "JNJ", "avgo": "AVGO", "nflx": "NFLX", "wmt": "WMT", "xom": "XOM",
    "pg": "PG", "ko": "KO", "asml": "ASML.AS", "lvmh": "MC.PA", "novo": "NVO",
    "toyota": "TM", "samsung": "005930.KS", "tsm": "TSM", "shell": "SHEL",
    "nestle": "NESN.SW", "novartis": "NOVN.SW",
    # Krypto
    "btc": "BTC-EUR", "eth": "ETH-EUR", "sol": "SOL-EUR", "xrp": "XRP-EUR", "bnb": "BNB-EUR",
    # Devisen
    "eurusd": "EURUSD=X", "eurgbp": "EURGBP=X", "eurchf": "EURCHF=X", "usdjpy": "JPY=X",
}
CURRENCY_SIGN = {"EUR": "€", "USD": "$", "GBP": "£", "GBp": "p", "JPY": "¥", "KRW": "₩", "CHF": "CHF"}


def fmt_num(x, decimals):
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_price(ticker, price, currency):
    if ticker.startswith("^"):
        return fmt_num(price, 0) + " Pkt."
    if ticker.endswith("=X"):
        return fmt_num(price, 2 if price >= 50 else 4)
    decimals = 0 if price >= 10000 else (4 if price < 1 else 2)
    return fmt_num(price, decimals) + " " + CURRENCY_SIGN.get(currency, currency or "")


def pct(now, then):
    if not then:
        return None
    return round((now / then - 1) * 100, 2)


def quote(ticker):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(ticker) + "?range=1y&interval=1d")
    res = json.loads(fetch(url))["chart"]["result"][0]
    meta = res["meta"]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    price = meta.get("regularMarketPrice") or closes[-1]
    return {
        "price": fmt_price(ticker, price, meta.get("currency")),
        "change": {
            "week": pct(price, closes[-6] if len(closes) >= 6 else closes[0]),
            "month": pct(price, closes[-22] if len(closes) >= 22 else closes[0]),
            "year": pct(price, closes[0]),
        },
    }


def update_markets():
    old = load_json("markets.json", {}).get("quotes", {})
    quotes, failed = {}, []
    for sid, ticker in TICKERS.items():
        try:
            quotes[sid] = quote(ticker)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{ticker} ({e.__class__.__name__})")
            if sid in old:
                quotes[sid] = old[sid]  # letzten bekannten Wert behalten
        time.sleep(0.25)
    if not quotes:
        print("Kurse: keine Daten erhalten, Datei bleibt unverändert")
        return
    n = now_berlin()
    save_json("markets.json", {
        "updatedAt": n.isoformat(),
        "updatedAtLabel": label_de(n),
        "source": "Yahoo Finance",
        "quotes": quotes,
    })
    print(f"Kurse: {len(TICKERS) - len(failed)} aktualisiert, {len(failed)} fehlgeschlagen")
    for f in failed:
        print("  -", f)

# ---------------------------------------------------------------- Nachrichten

FEEDS = [
    ("tagesschau", "wirtschaft", "https://www.tagesschau.de/wirtschaft/index~rss2.xml"),
    ("spiegel", "wirtschaft", "https://www.spiegel.de/wirtschaft/index.rss"),
    ("zeit", "wirtschaft", "https://newsfeed.zeit.de/wirtschaft/index"),
    ("faz", "wirtschaft", "https://www.faz.net/rss/aktuell/wirtschaft/"),
    ("ntv", "wirtschaft", "https://www.n-tv.de/wirtschaft/rss"),
    ("cnbc", "wirtschaft", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("heise", "technologie", "https://www.heise.de/rss/heise-top-atom.xml"),
    ("t3n", "technologie", "https://t3n.de/rss.xml"),
    ("golem", "technologie", "https://rss.golem.de/rss.php?feed=RSS2.0"),
    ("techcrunch", "technologie", "https://techcrunch.com/feed/"),
    ("theverge", "technologie", "https://www.theverge.com/rss/index.xml"),
    ("arstechnica", "technologie", "https://feeds.arstechnica.com/arstechnica/index"),
    ("wired", "technologie", "https://www.wired.com/feed/rss"),
    ("techreview", "ki", "https://www.technologyreview.com/feed/"),
]
PODCAST_FEED = "https://handelsblatt-morningbriefing.podigee.io/feed/mp3"
NS = {"atom": "http://www.w3.org/2005/Atom",
      "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
      "content": "http://purl.org/rss/1.0/modules/content/"}


def parse_date(s):
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s)
    except Exception:  # noqa: BLE001
        pass
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def parse_feed(raw):
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        items.append({
            "title": clean(it.findtext("title"), 200),
            "url": (it.findtext("link") or "").strip(),
            "summary": clean(it.findtext("description"), 400),
            "date": parse_date(it.findtext("pubDate")),
        })
    for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
        link = e.find("atom:link[@rel='alternate']", NS)
        if link is None:
            link = e.find("atom:link", NS)
        items.append({
            "title": clean(e.findtext("atom:title", namespaces=NS), 200),
            "url": link.get("href") if link is not None else "",
            "summary": clean(e.findtext("atom:summary", namespaces=NS)
                             or e.findtext("atom:content", namespaces=NS), 400),
            "date": parse_date(e.findtext("atom:updated", namespaces=NS)
                               or e.findtext("atom:published", namespaces=NS)),
        })
    return [i for i in items if i["title"] and i["url"]]


def collect_candidates():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=30)
    out = []
    for src, cat, url in FEEDS:
        try:
            items = parse_feed(fetch(url))
        except Exception as e:  # noqa: BLE001
            print(f"  Feed fehlgeschlagen: {src} ({e.__class__.__name__})")
            continue
        recent = [i for i in items if not i["date"] or i["date"] > cutoff][:10]
        for i in recent:
            out.append({"src": src, "cat": cat, **{k: i[k] for k in ("title", "url", "summary")}})
    print(f"Nachrichten: {len(out)} Kandidaten aus den Feeds")
    return out


def latest_podcast():
    root = ET.fromstring(fetch(PODCAST_FEED))
    it = root.find("channel/item")
    desc = (it.findtext("content:encoded", namespaces=NS)
            or it.findtext("itunes:summary", namespaces=NS)
            or it.findtext("description"))
    dur = it.findtext("itunes:duration", namespaces=NS) or ""
    minutes = None
    if dur:
        parts = [int(p) for p in dur.split(":") if p.isdigit()]
        secs = parts[0] if len(parts) == 1 else sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
        minutes = max(1, round(secs / 60))
    pub = parse_date(it.findtext("pubDate"))
    return {
        "title": clean(it.findtext("title"), 200),
        "description": clean(desc, 3000),
        "url": (it.findtext("link") or "").strip(),
        "dateLabel": ("Folge vom " + pub.astimezone(BERLIN).strftime("%d.%m.") if pub else "Neueste Folge")
                     + (f" · {minutes} Min." if minutes else ""),
    }


def ask_claude(candidates, podcast):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.environ.get("CLAUDE_MODEL") or "claude-haiku-4-5-20251001"
    listing = "\n".join(
        f"[{n}] ({c['src']}, {c['cat']}) {c['title']} :: {c['summary']}"
        for n, c in enumerate(candidates))
    prompt = f"""Du kuratierst das Morgen-Dashboard "Teconomic News" für einen deutschen BWL-Studenten (International Business).

Aufgabe 1: Wähle aus den Meldungen unten die 5 wichtigsten des Tages aus den Bereichen Wirtschaft, Technologie und KI. Mische die Bereiche, vermeide Dubletten zum selben Ereignis, bevorzuge deutsche Quellen bei gleicher Relevanz.
Für jede Meldung: eine deutsche Überschrift (max. 110 Zeichen, sachlich) und eine Kernaussage in einem deutschen Satz (max. 170 Zeichen), die erklärt, worum es geht oder warum es relevant ist. Kategorie: "wirtschaft", "technologie" oder "ki".

Aufgabe 2: Fasse die Podcast-Folge in genau 3 kurzen deutschen Kernaussagen zusammen (je max. 130 Zeichen). Nutze nur die Folgenbeschreibung, erfinde nichts.

Antworte NUR mit JSON in dieser Form:
{{"topStories":[{{"id":<Nummer der Meldung>,"cat":"...","headline":"...","takeaway":"..."}}],"podcastTakeaways":["...","...","..."]}}

MELDUNGEN:
{listing}

PODCAST: {podcast['title'] if podcast else '(nicht verfügbar)'}
{podcast['description'] if podcast else ''}
"""
    body = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    raw = fetch("https://api.anthropic.com/v1/messages", data=body, timeout=90, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    text = "".join(b.get("text", "") for b in json.loads(raw)["content"])
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def fallback_selection(candidates):
    """Ohne KI: je Quelle die neueste Meldung, Bereiche abwechselnd."""
    by_cat = {}
    used = set()
    for c in candidates:
        if c["src"] not in used:
            used.add(c["src"])
            by_cat.setdefault(c["cat"], []).append(c)
    picked = []
    while len(picked) < 5 and any(by_cat.values()):
        for cat in ("wirtschaft", "technologie", "ki"):
            if by_cat.get(cat) and len(picked) < 5:
                c = by_cat[cat].pop(0)
                picked.append({**c, "headline": c["title"], "takeaway": c["summary"][:170]})
    return picked


def first_sentences(text, n=3):
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return [p[:200] for p in parts if len(p) > 25][:n]


def update_news():
    candidates = collect_candidates()
    podcast = None
    try:
        podcast = latest_podcast()
    except Exception as e:  # noqa: BLE001
        print(f"  Podcast-Feed fehlgeschlagen ({e.__class__.__name__})")

    stories, pod_points = [], []
    try:
        ai = ask_claude(candidates, podcast) if candidates or podcast else None
    except Exception as e:  # noqa: BLE001
        print(f"  KI-Aufruf fehlgeschlagen ({e}); nutze Anreißer der Quellen")
        ai = None
    if ai:
        for s in ai.get("topStories", [])[:5]:
            try:
                c = candidates[int(s["id"])]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            cat = s.get("cat") if s.get("cat") in ("wirtschaft", "technologie", "ki") else c["cat"]
            stories.append({"cat": cat, "src": c["src"], "url": c["url"],
                            "headline": clean(s.get("headline"), 160) or c["title"],
                            "takeaway": clean(s.get("takeaway"), 240)})
        pod_points = [clean(t, 200) for t in ai.get("podcastTakeaways", [])][:3]
        print(f"Nachrichten: {len(stories)} Meldungen mit KI-Kernaussage")
    if len(stories) < 5:
        have = {s["url"] for s in stories}
        extra = [{k: c[k] for k in ("cat", "src", "url", "headline", "takeaway")}
                 for c in fallback_selection(candidates) if c["url"] not in have]
        stories += extra[:5 - len(stories)]
        print(f"Nachrichten: {len(extra[:5])} Meldungen ohne KI ergänzt")

    old = load_json("news.json", {})
    n = now_berlin()
    out = {
        "date": n.date().isoformat(),
        "updatedAt": n.isoformat(),
        "updatedAtLabel": n.strftime("%d.%m.%Y, %H:%M Uhr"),
        "topStories": stories or old.get("topStories", []),
        "podcastEpisode": old.get("podcastEpisode"),
    }
    if podcast:
        out["podcastEpisode"] = {
            "title": podcast["title"],
            "dateLabel": podcast["dateLabel"],
            "url": podcast["url"],
            "takeaways": pod_points or first_sentences(podcast["description"]),
        }
    save_json("news.json", out)

# ---------------------------------------------------------------- Start

def main():
    force = "--force-news" in sys.argv or os.environ.get("FORCE_NEWS") == "true"
    update_markets()
    n = now_berlin()
    done_today = load_json("news.json", {}).get("date") == n.date().isoformat()
    if force or (n.hour >= NEWS_HOUR and not done_today):
        update_news()
    else:
        print("Nachrichten: heute schon aktuell oder noch vor 7 Uhr, übersprungen")


if __name__ == "__main__":
    main()

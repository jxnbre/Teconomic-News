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
    path = os.path.join(DATA, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
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


def guess_currency(ticker):
    """Währung aus dem Kürzel ableiten, falls die Quelle keine mitliefert."""
    if ticker.startswith("^") or ticker.endswith("=X"):
        return None
    suffix = {".DE": "EUR", ".AS": "EUR", ".PA": "EUR", ".SW": "CHF", ".KS": "KRW", ".L": "GBp"}
    for suf, cur in suffix.items():
        if ticker.endswith(suf):
            return cur
    if ticker.endswith("-EUR"):
        return "EUR"
    return "USD"


def ts_date(ts):
    try:
        return dt.datetime.fromtimestamp(int(ts), BERLIN).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


class Yahoo:
    """Yahoo Finance. Holt die Kurse gebündelt (bis zu 20 Werte pro Anfrage),
    damit aus GitHub Actions heraus möglichst wenige Anfragen nötig sind."""

    def __init__(self):
        import http.cookiejar
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.crumb = None
        self.blocked = False
        self.fails = 0
        try:
            try:
                self._get("https://fc.yahoo.com", timeout=10)
            except Exception:  # noqa: BLE001  (liefert 404, setzt aber das Cookie)
                pass
            self.crumb = self._get("https://query1.finance.yahoo.com/v1/test/getcrumb").decode().strip() or None
        except Exception as e:  # noqa: BLE001
            print(f"  Yahoo: kein Crumb ({e.__class__.__name__}: {str(e)[:60]}), versuche es ohne")

    def _get(self, url, timeout=15):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
        with self.opener.open(req, timeout=timeout) as r:
            return r.read()

    def _crumb(self):
        return f"&crumb={urllib.parse.quote(self.crumb)}" if self.crumb else ""

    @staticmethod
    def _series(timestamps, closes):
        pairs = [(t, c) for t, c in zip(timestamps or [], closes or []) if c is not None]
        return [c for _, c in pairs], (ts_date(pairs[-1][0]) if pairs else None)

    def spark(self, tickers):
        """Mehrere Werte in einer Anfrage. Gibt {ticker: (preis, schlusskurse, währung, datum)} zurück."""
        if self.blocked or not tickers:
            return {}
        syms = ",".join(urllib.parse.quote(t) for t in tickers)
        last = None
        for host in ("query1", "query2"):
            for path in ("/v7/finance/spark", "/v8/finance/spark"):
                url = f"https://{host}.finance.yahoo.com{path}?symbols={syms}&range=1y&interval=1d{self._crumb()}"
                try:
                    data = json.loads(self._get(url))
                except Exception as e:  # noqa: BLE001
                    last = e
                    if "429" in str(e):
                        time.sleep(3)
                    continue
                out = {}
                # Format v7: {"spark": {"result": [{"symbol":..., "response":[{meta, timestamp, indicators}]}]}}
                for res in ((data.get("spark") or {}).get("result") or []):
                    try:
                        r = res["response"][0]
                        closes, day = self._series(r.get("timestamp"), r["indicators"]["quote"][0]["close"])
                        if len(closes) >= 2:
                            meta = r.get("meta") or {}
                            out[res["symbol"]] = (meta.get("regularMarketPrice") or closes[-1], closes,
                                                  meta.get("currency"), day)
                    except Exception:  # noqa: BLE001
                        pass
                # Format v8: {"SAP.DE": {"timestamp": [...], "close": [...]}}
                if not out and "spark" not in data:
                    for sym, r in data.items():
                        try:
                            closes, day = self._series(r.get("timestamp"), r.get("close"))
                            if len(closes) >= 2:
                                out[sym] = (closes[-1], closes, None, day)
                        except Exception:  # noqa: BLE001
                            pass
                if out:
                    return out
                last = RuntimeError("leere Antwort")
        self.fails += 1
        if self.fails >= 2:
            self.blocked = True
        raise last or RuntimeError("Yahoo-Spark fehlgeschlagen")

    def history(self, ticker):
        if self.blocked:
            raise RuntimeError("Yahoo blockiert")
        q = "?range=1y&interval=1d" + self._crumb()
        path = "/v8/finance/chart/" + urllib.parse.quote(ticker) + q
        last = None
        for host in ("query1", "query2"):
            try:
                res = json.loads(self._get(f"https://{host}.finance.yahoo.com{path}"))["chart"]["result"][0]
                closes, day = self._series(res.get("timestamp"), res["indicators"]["quote"][0]["close"])
                price = res["meta"].get("regularMarketPrice") or closes[-1]
                return price, closes, res["meta"].get("currency"), day
            except Exception as e:  # noqa: BLE001
                last = e
        self.fails += 1
        if self.fails >= 6:
            self.blocked = True  # Yahoo sperrt gerade: nur noch die Ausweichquelle
        raise last


STOOQ_INDEX = {"^GDAXI": "^dax", "^DJI": "^dji", "^NDX": "^ndx", "^GSPC": "^spx",
               "^N225": "^nkx", "^FTSE": "^ukx", "^STOXX50E": "^stx", "^MDAXI": "^mdax",
               "^SDAXI": "^sdax"}
STOOQ_CURRENCY = {".de": "EUR", ".us": "USD", ".uk": "GBP", ".jp": "JPY"}
STOOQ_APIKEY = os.environ.get("STOOQ_APIKEY", "").strip()


def stooq_symbol(ticker):
    if ticker in STOOQ_INDEX:
        return STOOQ_INDEX[ticker]
    if ticker.endswith("=X") or ticker.endswith("-EUR"):
        return None  # Devisen und Krypto kommen aus eigenen Quellen
    if ticker.endswith(".DE"):
        return ticker[:-3].lower() + ".de"
    if "." not in ticker:
        return ticker.lower().replace("-", ".") + ".us"
    return None


class StooqBlocked(RuntimeError):
    pass


def stooq_history(ticker):
    sym = stooq_symbol(ticker)
    if not sym:
        raise RuntimeError("kein Stooq-Symbol")
    start = (dt.date.today() - dt.timedelta(days=380)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&i=d&d1={start}"
    if STOOQ_APIKEY:
        url += "&apikey=" + urllib.parse.quote(STOOQ_APIKEY)
    raw = fetch(url, timeout=12, tries=1).decode("utf-8", "replace")
    low = raw.lower()
    if low.lstrip().startswith("<"):
        raise StooqBlocked("Stooq liefert eine Webseite statt Kursdaten (Sperre oder Captcha)")
    if "apikey" in low or "api key" in low:
        raise StooqBlocked("Stooq verlangt einen API-Schlüssel (Secret STOOQ_APIKEY anlegen, siehe README)")
    if "limit" in low and "exceeded" in low:
        raise StooqBlocked("Stooq: Tageslimit erreicht")
    lines = [l for l in raw.strip().splitlines() if l and l[0].isdigit()]
    rows = [l.split(",") for l in lines if len(l.split(",")) >= 5]
    closes = [float(r[4]) for r in rows]
    if len(closes) < 2:
        raise RuntimeError("Stooq: keine Daten (" + raw[:60].replace("\n", " ") + ")")
    cur = next((c for suf, c in STOOQ_CURRENCY.items() if sym.endswith(suf)), None)
    return closes[-1], closes, cur, rows[-1][0]


def changes(price, closes):
    return {
        "week": pct(price, closes[-6] if len(closes) >= 6 else closes[0]),
        "month": pct(price, closes[-22] if len(closes) >= 22 else closes[0]),
        "year": pct(price, closes[0]),
    }


COINGECKO = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "xrp": "ripple", "bnb": "binancecoin"}


def crypto_quotes():
    out = {}
    today = now_berlin().date().isoformat()
    for sid, cid in COINGECKO.items():
        try:
            raw = fetch(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=eur&days=365&interval=daily",
                        headers={"Accept": "application/json"}, timeout=15, tries=2)
            closes = [p[1] for p in json.loads(raw)["prices"]]
            out[sid] = {"price": fmt_price(sid.upper() + "-EUR", closes[-1], "EUR"),
                        "change": changes(closes[-1], closes), "asOf": today, "src": "CoinGecko"}
        except Exception as e:  # noqa: BLE001
            print(f"  CoinGecko {cid}: {e.__class__.__name__}: {e}")
        time.sleep(2.5)  # freies Limit schonen
    return out


def fx_quotes():
    end = dt.date.today()
    start = end - dt.timedelta(days=370)
    raw = None
    for base in ("https://api.frankfurter.dev/v1", "https://api.frankfurter.app"):
        try:
            raw = fetch(f"{base}/{start}..{end}?from=EUR&to=USD,GBP,CHF,JPY", timeout=15, tries=2)
            break
        except Exception as e:  # noqa: BLE001
            print(f"  Frankfurter ({base}): {e.__class__.__name__}: {e}")
    if raw is None:
        return {}
    rates = json.loads(raw)["rates"]
    days = sorted(rates)
    series = {
        "eurusd": [rates[d]["USD"] for d in days],
        "eurgbp": [rates[d]["GBP"] for d in days],
        "eurchf": [rates[d]["CHF"] for d in days],
        "usdjpy": [rates[d]["JPY"] / rates[d]["USD"] for d in days],
    }
    return {sid: {"price": fmt_num(v[-1], 2 if v[-1] >= 50 else 4), "change": changes(v[-1], v),
                  "asOf": days[-1], "src": "EZB"}
            for sid, v in series.items()}


def yfinance_quotes(tickers):
    """Yahoo über das Paket yfinance. Es tritt gegenüber Yahoo wie ein echter Chrome-Browser auf
    (curl_cffi). Ohne das blockt Yahoo Anfragen aus GitHub Actions mit „429 Too Many Requests“.
    Gibt {ticker: (preis, schlusskurse, währung, datum)} zurück."""
    import yfinance as yf  # wird im Workflow installiert (pip install yfinance)
    df = yf.download(list(tickers), period="1y", interval="1d", group_by="ticker", auto_adjust=False,
                     progress=False, threads=4, timeout=20)
    out = {}
    if df is None or getattr(df, "empty", True):
        return out
    cols = df.columns
    lvl0 = set(cols.get_level_values(0)) if getattr(cols, "nlevels", 1) > 1 else set()
    for t in tickers:
        try:
            if t in lvl0:
                s = df[t]["Close"]
            elif "Close" in lvl0:
                s = df["Close"][t]
            elif len(tickers) == 1 and "Close" in cols:
                s = df["Close"]
            else:
                continue
            s = s.dropna()
            if len(s) < 2:
                continue
            closes = [float(x) for x in s.tolist()]
            day = s.index[-1].date().isoformat()
            out[t] = (closes[-1], closes, None, day)
        except Exception:  # noqa: BLE001
            continue
    return out


def update_markets():
    old = load_json("markets.json", {}).get("quotes", {})
    quotes, sources, errors = {}, {}, []

    # Krypto und Devisen aus eigenen, freien Quellen
    try:
        quotes.update(crypto_quotes())
    except Exception as e:  # noqa: BLE001
        print(f"  Krypto: {e}")
    try:
        quotes.update(fx_quotes())
    except Exception as e:  # noqa: BLE001
        print(f"  Devisen: {e}")
    for q in quotes.values():
        sources[q["src"]] = sources.get(q["src"], 0) + 1

    def put(sid, ticker, got, name):
        price, closes, cur, day = got
        quotes[sid] = {"price": fmt_price(ticker, price, cur or guess_currency(ticker)),
                       "change": changes(price, closes), "asOf": day, "src": name}
        sources[name] = sources.get(name, 0) + 1

    todo = {sid: t for sid, t in TICKERS.items() if sid not in quotes}

    # 1) yfinance (zuverlässigster Weg aus GitHub Actions)
    try:
        got = yfinance_quotes(list(todo.values()))
        for sid, ticker in todo.items():
            if ticker in got:
                put(sid, ticker, got[ticker], "Yahoo")
        print(f"  yfinance: {len(got)} von {len(todo)} Werten")
    except ImportError:
        errors.append("yfinance nicht installiert (Workflow-Schritt „Python-Pakete installieren“ fehlt)")
    except Exception as e:  # noqa: BLE001
        errors.append(f"yfinance: {e.__class__.__name__}: {str(e)[:80]}")
    todo = {sid: t for sid, t in todo.items() if sid not in quotes}

    # 2) Ausweichweg: Yahoo direkt, gebündelt
    yahoo = Yahoo() if todo else None
    items = list(todo.items())
    for i in range(0, len(items), 20):
        chunk = dict(items[i:i + 20])
        try:
            got = yahoo.spark(list(chunk.values()))
        except Exception as e:  # noqa: BLE001
            errors.append(f"Yahoo (gebündelt): {e.__class__.__name__}: {str(e)[:80]}")
            got = {}
        for sid, ticker in chunk.items():
            if ticker in got:
                put(sid, ticker, got[ticker], "Yahoo")
        time.sleep(1)

    # 3) Was fehlt: einzeln bei Yahoo, sonst Stooq
    stooq_blocked = None
    for sid, ticker in TICKERS.items():
        if sid in quotes:
            continue
        for name, fn in (("Yahoo", yahoo.history), ("Stooq", stooq_history)):
            if name == "Yahoo" and (yahoo.blocked or len(errors) > 40):
                continue
            if name == "Stooq" and stooq_blocked:
                continue
            try:
                put(sid, ticker, fn(ticker), name)
                break
            except StooqBlocked as e:
                stooq_blocked = str(e)
                errors.append(str(e))
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name} {ticker}: {e.__class__.__name__}: {str(e)[:80]}")
        time.sleep(0.3)

    # 4) Was dann noch fehlt: letzten bekannten Wert behalten und als veraltet markieren
    kept, missing = [], []
    for sid in TICKERS:
        if sid in quotes:
            continue
        if sid in old:
            quotes[sid] = {**old[sid], "stale": True}
            kept.append(sid)
        else:
            missing.append(sid)

    fresh = sum(1 for q in quotes.values() if not q.get("stale"))
    total = len(TICKERS)
    print("Kurse je Quelle:", sources or "keine")
    print(f"Kurse: {fresh} aktuell, {len(kept)} veraltet, {len(missing)} ohne Daten (von {total})")
    for e in errors[:15]:
        print("  -", e)
    if not sources and not old:
        print("Kurse: keine Quelle erreichbar, Datei bleibt unverändert")
        return
    hint = ""
    if fresh < total * 0.5:
        hint = stooq_blocked or "Kursquellen haben die Abfrage abgelehnt. Siehe README, Abschnitt Aktienkurse."
    n = now_berlin()
    save_json("markets.json", {
        "updatedAt": n.isoformat(),
        "updatedAtLabel": label_de(n),
        "source": ", ".join(sources),
        "status": {"total": total, "fresh": fresh, "stale": kept, "missing": missing,
                   "hint": hint, "errors": errors[:8]},
        "quotes": quotes,
    })

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
    # Erweiterung Oktober 2026: mehr Wirtschaft, mehr KI, mehr internationale Sicht.
    # Fällt ein Feed aus, wird er einfach übersprungen.
    ("handelsblatt", "wirtschaft", "https://www.handelsblatt.com/contentexport/feed/schlagzeilen"),
    ("wiwo", "wirtschaft", "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen"),
    ("managermagazin", "wirtschaft", "https://www.manager-magazin.de/news/index.rss"),
    ("gruenderszene", "wirtschaft", "https://www.businessinsider.de/gruenderszene/feed/"),
    ("bbc", "wirtschaft", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("guardian", "technologie", "https://www.theguardian.com/uk/technology/rss"),
    ("netzpolitik", "technologie", "https://netzpolitik.org/feed/"),
    ("thedecoder", "ki", "https://the-decoder.de/feed/"),
    ("venturebeat", "ki", "https://venturebeat.com/category/ai/feed/"),
]
NEWS_COUNT = 15        # so viele Meldungen kommen pro Tag ins Dashboard (angezeigt werden erst 5)
PER_FEED = 8           # höchstens so viele aktuelle Meldungen je Quelle als Kandidaten
AD_PATTERN = re.compile(r"^\s*[\[(]?\s*(anzeige|sponsored|werbung|advertorial|partner-?content)\b", re.I)
PODCAST_FEED = "https://handelsblatt-morningbriefing.podigee.io/feed/mp3"
NS = {"atom": "http://www.w3.org/2005/Atom",
      "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
      "content": "http://purl.org/rss/1.0/modules/content/"}


def parse_date(s):
    if not s:
        return None
    d = None
    try:
        d = email.utils.parsedate_to_datetime(s.strip())
    except Exception:  # noqa: BLE001
        try:
            d = dt.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


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
            items = parse_feed(fetch(url, timeout=15, tries=2))
            recent = [i for i in items if (not i["date"] or i["date"] > cutoff)
                      and not AD_PATTERN.search(i["title"])][:PER_FEED]
        except Exception as e:  # noqa: BLE001
            print(f"  Feed fehlgeschlagen: {src} ({e.__class__.__name__}: {e})")
            continue
        for i in recent:
            out.append({"src": src, "cat": cat, **{k: i[k] for k in ("title", "url", "summary")}})
    print(f"Nachrichten: {len(out)} Kandidaten aus {len({c['src'] for c in out})} Quellen")
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


def shorten(text, limit):
    """Kürzt an einer Wortgrenze und hängt … an, statt mitten im Wort abzuschneiden."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-–")
    return cut + " …"


STOPWORDS = set("""
der die das den dem des ein eine einer eines einem einen und oder aber auch auf aus bei bis durch für gegen
im in ins mit nach nicht noch nur ob ohne seit sich sie er es wir ihr um unter vom von vor wie wird werden wurde
zu zum zur über so als am an ist sind sein hat haben mehr neue neuen neuer neues jetzt soll sollen will kann können
heute gibt was wer warum wieso the a an of to for on in and or with how why what new is are was from at by after
beim dass wegen sowie diese dieser weitere weiter mehr erste ersten zwei drei viele jahr jahre jahren prozent millionen milliarden euro dollar laut sagt
""".split())


def keywords(text, n=6):
    words = re.findall(r"[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9\-]{2,}", text or "")
    out = []
    for w in words:
        lw = w.lower()
        if lw in STOPWORDS or lw.isdigit() or lw in (o.lower() for o in out):
            continue
        out.append(w)
    # Großgeschriebene, längere Wörter (Namen, Fachbegriffe) zuerst
    out.sort(key=lambda w: (not w[0].isupper(), -len(w)))
    return out[:n]


def similar(a, b):
    """Ähnlichkeit zweier Überschriften (0 bis 1) über gemeinsame Schlagworte."""
    A = {w.lower() for w in keywords(a, 12) if len(w) >= 4}
    B = {w.lower() for w in keywords(b, 12) if len(w) >= 4}
    common = A & B
    if len(common) < 2:
        return 0.0
    return len(common) / len(A | B)


def group_duplicates(cands):
    """Fasst Meldungen zum selben Ereignis zusammen (ohne KI, über Titel-Ähnlichkeit)."""
    groups = []
    for c in cands:
        for g in groups:
            if g[0]["src"] != c["src"] and similar(g[0]["title"], c["title"]) >= 0.3:
                if all(x["src"] != c["src"] for x in g):
                    g.append(c)
                break
        else:
            groups.append([c])
    return groups


def story_from(group, cat=None, headline=None, takeaway=None, topic=None, tags=None):
    main = group[0]
    seen, sources = set(), []
    for c in group:
        if c["src"] in seen:
            continue
        seen.add(c["src"])
        sources.append({"src": c["src"], "url": c["url"]})
    kw = keywords(main["title"])
    return {
        "cat": cat if cat in ("wirtschaft", "technologie", "ki") else main["cat"],
        "src": main["src"],
        "url": main["url"],
        "headline": clean(headline, 160) or main["title"],
        "takeaway": clean(takeaway, 260) if takeaway else shorten(main["summary"], 200),
        "topic": clean(topic, 40) or (kw[0] if kw else ""),
        "tags": [clean(t, 30) for t in (tags or kw[:4]) if t][:5],
        "sources": sources,
    }


def ask_claude(candidates, podcast):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("  Kein ANTHROPIC_API_KEY gesetzt: Auswahl ohne KI")
        return None
    model = os.environ.get("CLAUDE_MODEL") or "claude-haiku-4-5-20251001"
    listing = "\n".join(
        f"[{n}] ({c['src']}, {c['cat']}) {c['title']} :: {shorten(c['summary'], 220)}"
        for n, c in enumerate(candidates))
    prompt = f"""Du kuratierst das Morgen-Dashboard "Teconomic News" für einen deutschen BWL-Studenten (International Business).

Aufgabe 1: Wähle aus den Meldungen unten die {NEWS_COUNT} wichtigsten des Tages aus Wirtschaft, Technologie und KI, sortiert nach Wichtigkeit (wichtigste zuerst).
- Berichten mehrere Quellen über dasselbe Ereignis, ist das EINE Meldung: nenne in "ids" alle zugehörigen Nummern, die beste Quelle zuerst.
- Mische die Bereiche und Quellen: höchstens 3 Meldungen mit derselben Hauptquelle. Bevorzuge deutsche Quellen bei gleicher Relevanz.
- Keine Werbung, keine Gewinnspiele, keine reinen Produkttests oder Kaufberatungen.
Für jede Meldung:
- "headline": deutsche Überschrift, max. 110 Zeichen, sachlich
- "takeaway": Kernaussage in einem deutschen Satz, max. 170 Zeichen: worum es geht und warum es relevant ist. Neutral, keine Anlageempfehlung.
- "cat": "wirtschaft", "technologie" oder "ki"
- "topic": das Thema in 1 bis 3 Wörtern, mit dem man es über mehrere Tage verfolgen kann (z. B. "Erbschaftsteuer", "Nvidia", "EU AI Act")
- "tags": 2 bis 4 kurze deutsche Schlagworte (Unternehmen, Branche, Themenfeld)

Aufgabe 2: Fasse die Podcast-Folge in genau 3 kurzen deutschen Kernaussagen zusammen (je max. 130 Zeichen). Nutze nur die Folgenbeschreibung, erfinde nichts.

Antworte NUR mit JSON in dieser Form:
{{"topStories":[{{"ids":[<Nummer>, ...],"cat":"...","headline":"...","takeaway":"...","topic":"...","tags":["...","..."]}}],"podcastTakeaways":["...","...","..."]}}

MELDUNGEN:
{listing}

PODCAST: {podcast['title'] if podcast else '(nicht verfügbar)'}
{podcast['description'] if podcast else ''}
"""
    body = json.dumps({
        "model": model,
        "max_tokens": 6000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    raw = fetch("https://api.anthropic.com/v1/messages", data=body, timeout=120, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    text = "".join(b.get("text", "") for b in json.loads(raw)["content"])
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def fallback_selection(candidates, have_urls=()):
    """Ohne KI: Dubletten zusammenfassen, dann Bereiche und Quellen abwechselnd mischen."""
    groups = [g for g in group_duplicates(candidates) if not any(c["url"] in have_urls for c in g)]
    # Ereignisse, über die mehrere Quellen berichten, sind meist wichtiger
    groups.sort(key=lambda g: -len(g))
    by_cat = {}
    for g in groups:
        by_cat.setdefault(g[0]["cat"], []).append(g)
    picked, per_src = [], {}
    while len(picked) < NEWS_COUNT and any(by_cat.values()):
        for cat in ("wirtschaft", "technologie", "ki"):
            pool = by_cat.get(cat) or []
            while pool:
                g = pool.pop(0)
                if per_src.get(g[0]["src"], 0) < 2:
                    per_src[g[0]["src"]] = per_src.get(g[0]["src"], 0) + 1
                    picked.append(story_from(g))
                    break
            if len(picked) >= NEWS_COUNT:
                break
        if all(not v for v in by_cat.values()):
            break
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
        used = set()
        for s in ai.get("topStories", [])[:NEWS_COUNT]:
            ids = s.get("ids") if isinstance(s.get("ids"), list) else [s.get("id")]
            group = []
            for i in ids:
                try:
                    i = int(i)
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(candidates) and i not in used:
                    used.add(i)
                    group.append(candidates[i])
            if not group:
                continue
            tags = s.get("tags") if isinstance(s.get("tags"), list) else None
            stories.append(story_from(group, s.get("cat"), s.get("headline"), s.get("takeaway"),
                                      s.get("topic"), tags))
        pod_points = [clean(t, 200) for t in ai.get("podcastTakeaways", [])][:3]
        print(f"Nachrichten: {len(stories)} Meldungen mit KI-Kernaussage")
    if len(stories) < NEWS_COUNT:
        have = {x["url"] for s in stories for x in s["sources"]}
        extra = fallback_selection(candidates, have)[:NEWS_COUNT - len(stories)]
        stories += extra
        print(f"Nachrichten: {len(extra)} Meldungen ohne KI ergänzt")

    old = load_json("news.json", {})
    n = now_berlin()
    out = {
        "date": n.date().isoformat(),
        "updatedAt": n.isoformat(),
        "updatedAtLabel": n.strftime("%d.%m.%Y, %H:%M Uhr"),
        "ai": bool(ai),
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
    save_archive(out)


def save_archive(out):
    """Legt jede Tagesausgabe unter data/archive/JJJJ-MM-TT.json ab (für Archiv und Themen-Verlauf)."""
    day = out.get("date")
    if not day:
        return
    save_json(f"archive/{day}.json", out)
    index = load_json("archive/index.json", {"days": []})
    days = sorted(set(index.get("days", []) + [day]), reverse=True)[:120]
    save_json("archive/index.json", {"days": days})
    print(f"Archiv: {day} gespeichert ({len(days)} Tage)")

# ---------------------------------------------------------------- Start

def main():
    force = "--force-news" in sys.argv or os.environ.get("FORCE_NEWS") == "true"
    try:
        update_markets()
    except Exception as e:  # noqa: BLE001
        print(f"Kurse: Fehler ({e.__class__.__name__}: {e})")
    n = now_berlin()
    done_today = load_json("news.json", {}).get("date") == n.date().isoformat()
    if force or (n.hour >= NEWS_HOUR and not done_today):
        try:
            update_news()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"Nachrichten: Fehler ({e.__class__.__name__}: {e})")
    else:
        print("Nachrichten: heute schon aktuell oder noch vor 7 Uhr, übersprungen")


if __name__ == "__main__":
    main()

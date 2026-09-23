# Teconomic News

Dashboard mit Nachrichten, Podcast und Kursen zu Wirtschaft, Technologie und KI. Läuft kostenlos auf GitHub Pages und aktualisiert sich selbst.

## Was sich wann aktualisiert

| Bereich | Wann | Quelle |
|---|---|---|
| Aktien, Indizes, Krypto, Devisen | stündlich | Yahoo Finance |
| Top-Meldungen mit KI-Kernaussage | täglich ab ca. 7:00 Uhr | RSS-Feeds (Tagesschau, Spiegel, FAZ, Heise, t3n u. a.) + Claude |
| Podcast-Folge mit Kernaussagen | täglich ab ca. 7:00 Uhr | Feed des Handelsblatt Morning Briefing + Claude |

GitHub startet geplante Läufe manchmal mit 10 bis 30 Minuten Verspätung.

## Dateien

- `index.html`: das Dashboard
- `data/news.json`, `data/markets.json`: die Daten, die das Dashboard lädt
- `scripts/update.py`: holt neue Daten
- `.github/workflows/update.yml`: Zeitplan und Veröffentlichung

## Einrichtung (einmalig, ca. 15 Minuten)

### 1. Repository anlegen

1. Auf github.com anmelden, oben rechts **+ → New repository**.
2. Name: `teconomic-news`, Sichtbarkeit **Public**, sonst nichts ankreuzen. **Create repository**.
3. Auf der leeren Seite auf **uploading an existing file** klicken.
4. Den entpackten Ordnerinhalt hineinziehen: `index.html`, `README.md` und die Ordner `data`, `scripts`, `.github`.
   - Der Ordner `.github` ist auf dem Mac versteckt. Im Finder mit **Cmd + Shift + .** einblenden. Unter Windows im Explorer **Ansicht → Ausgeblendete Elemente**.
5. **Commit changes**.

Prüfen: Im Repository muss der Pfad `.github/workflows/update.yml` sichtbar sein.

### 2. GitHub Pages einschalten

**Settings → Pages → Build and deployment → Source: GitHub Actions** auswählen.

### 3. API-Schlüssel für die KI-Kernaussagen

Ohne Schlüssel läuft alles auch, dann stehen statt der KI-Kernaussagen die Anreißer der Quellen da.

1. Auf console.anthropic.com anmelden, unter **Billing** etwas Guthaben aufladen.
2. Unter **API Keys → Create Key** einen Schlüssel erstellen und kopieren.
3. Im Repository: **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `ANTHROPIC_API_KEY`
   - Secret: den Schlüssel einfügen

Kosten: ein Aufruf pro Tag mit Claude Haiku, grob geschätzt unter 1 $ pro Monat. Das API-Guthaben ist getrennt von einem Claude-Abo.

Optional: Unter **Variables** eine Variable `CLAUDE_MODEL` anlegen, um ein anderes Modell zu nutzen (Standard: `claude-haiku-4-5-20251001`).

### 4. Erster Lauf

1. Tab **Actions** öffnen. Falls gefragt, Workflows aktivieren.
2. Links **Daten aktualisieren und veröffentlichen** wählen, rechts **Run workflow**.
3. Häkchen bei **Nachrichten und Podcast jetzt neu erstellen** setzen, starten.
4. Nach 2 bis 3 Minuten ist das Dashboard erreichbar unter:
   `https://<dein-github-name>.github.io/teconomic-news/`

## Anpassen

- **Uhrzeit der Nachrichten:** `NEWS_HOUR` in `scripts/update.py`.
- **Nachrichtenquellen:** Liste `FEEDS` in `scripts/update.py`. Die Quellen-ID muss in `SOURCES` in `index.html` vorkommen.
- **Aktien:** `TICKERS` in `scripts/update.py` (Yahoo-Kürzel) und `STOCKS` in `index.html` (Anzeige). Die IDs müssen übereinstimmen.

## Hinweise

- Yahoo Finance ist keine offizielle, dokumentierte Schnittstelle. Kurse können verzögert sein. Schlägt ein Abruf fehl, bleibt der letzte bekannte Wert stehen.
- Die Favoriten bei den Aktien speichert jeder Besucher in seinem eigenen Browser.
- Keine Anlageberatung.

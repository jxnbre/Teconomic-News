# Teconomic News

Dashboard mit Nachrichten, Podcast und Kursen zu Wirtschaft, Technologie und KI. Läuft kostenlos auf GitHub Pages und aktualisiert sich selbst.

## Was sich wann aktualisiert

| Bereich | Wann | Quelle |
|---|---|---|
| Aktien, Indizes, Krypto, Devisen | stündlich | Yahoo Finance |
| Top-Meldungen mit KI-Kernaussage | täglich ab ca. 7:00 Uhr | 23 RSS-Feeds (Tagesschau, Spiegel, Handelsblatt, Heise, The Decoder u. a.) + Claude |
| Podcast-Folge mit Kernaussagen | täglich ab ca. 7:00 Uhr | Feed des Handelsblatt Morning Briefing + Claude |

GitHub startet geplante Läufe manchmal mit 10 bis 30 Minuten Verspätung.

## Neu (Oktober 2026)

- **15 statt 5 Meldungen pro Tag.** Oben stehen 5, der Rest über „Weitere Meldungen anzeigen“.
- **Dubletten zusammengefasst.** Berichten mehrere Quellen über dasselbe, erscheint es einmal mit „Auch berichtet von: …“.
- **Sortierung „Für dich“.** Lernt aus „Relevant“ / „Nicht relevant“ (Schlagworte, Quelle, Bereich) und sortiert ab dem nächsten Laden danach. Umschaltbar auf „Nach Wichtigkeit“. Unter „Meine Themen“ steht, was gelernt wurde.
- **Quellen einstellen.** Unter „Meine Themen → Quellen“: Bevorzugt / Normal / Aus.
- **Thema verfolgen.** Button an jeder Meldung. Verfolgte Themen stehen 7 Tage lang unter „Heute“.
- **Stand-Anzeige.** Uhrzeit und Alter der Ausgabe, Warnung wenn es noch keine Ausgabe von heute gibt.
- **Aktienkurse.** Gebündelter Abruf (ca. 4 statt 80 Anfragen), Kennzeichnung „verzögert“, veraltete Werte grau, fehlende Werte als „keine Daten“.
- Werbung („Anzeige:“) wird aussortiert, Kernaussagen werden an Wortgrenzen gekürzt.

Bewertungen, Quellen-Einstellungen und verfolgte Themen werden nur im eigenen Browser gespeichert.

## Dateien

- `index.html`: das Dashboard
- `data/news.json`, `data/markets.json`: die Daten, die das Dashboard lädt
- `scripts/update.py`: holt neue Daten
- `config/sources.json`: eigene Websites (wird vom Dashboard gepflegt)
- `data/sources.json`: Status der eigenen Websites (wird vom Skript geschrieben)
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

## Eigene Websites: einmalige Einrichtung

Unter **Meine Themen → Quellen → Eigene Websites** kannst du eigene Nachrichtenseiten hinzufügen. Das Dashboard trägt sie in `config/sources.json` ein und startet sofort einen Lauf. Das Skript sucht den Nachrichten-Feed der Seite (sonst ihre Schlagzeilen über Google News), die KI nimmt passende Meldungen zu Wirtschaft, Technologie und KI bevorzugt auf.

Dafür braucht das Dashboard einmal pro Gerät einen GitHub-Zugang:

1. Auf github.com oben rechts auf dein Profilbild → **Settings** → ganz unten **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Token name:** `Teconomic Dashboard`. **Expiration:** z. B. 1 Jahr.
3. **Repository access:** **Only select repositories** → `Teconomic-News` auswählen.
4. **Permissions → Repository permissions:**
   - **Contents:** Read and write
   - **Actions:** Read and write
5. **Generate token**, den Schlüssel (beginnt mit `github_pat_`) kopieren.
6. Im Dashboard unter **Meine Themen → Quellen → Eigene Websites** einfügen und **Speichern**.

Der Schlüssel wird nur im Browser dieses Geräts gespeichert, nicht im Code. Er kann nur dieses eine Repository ändern. Bei Verlust auf GitHub unter Fine-grained tokens löschen.

## Aktienkurse: wenn Werte fehlen

Die kostenlosen Kursquellen sperren Anfragen aus GitHub Actions manchmal. So prüfst du den Zustand:

1. `https://<dein-github-name>.github.io/teconomic-news/data/markets.json` öffnen.
2. Unter `status` stehen `fresh` (aktuelle Werte), `missing` (ohne Daten), `hint` und `errors`.

Steht dort, dass **Stooq einen API-Schlüssel verlangt**:

1. Auf stooq.com eine Kursseite öffnen (z. B. `https://stooq.com/q/d/?s=sap.de`) und unten den Download als CSV anklicken. Stooq zeigt dann an, wie man den kostenlosen Schlüssel bekommt.
2. Im Repository: **Settings → Secrets and variables → Actions → New repository secret**, Name `STOOQ_APIKEY`, Wert: der Schlüssel.
3. Unter **Actions** den Workflow einmal von Hand starten.

## Hinweise

- Yahoo Finance ist keine offizielle, dokumentierte Schnittstelle. Kurse können verzögert sein. Schlägt ein Abruf fehl, bleibt der letzte bekannte Wert stehen.
- Die Favoriten bei den Aktien speichert jeder Besucher in seinem eigenen Browser.
- Keine Anlageberatung.

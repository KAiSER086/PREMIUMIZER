# ⚡ PREMIUMIZER • Universal Highspeed Downloader & Debrid Discord Bot (Deutsch)

[![Discord.py](https://img.shields.io/badge/discord.py-v2.3.2-blue.svg)](https://github.com/Rapptz/discord.py)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](docker-compose.yml)

> 🇬🇧 **[Click here for English documentation (README.md)](README.md)**

Ein leistungsstarker Discord-Bot, der deinen Discord-Server in ein privates Highspeed-Download-Center verwandelt, angetrieben von **[Premiumize.me](https://www.premiumize.me)**. Poste Links, Torrents oder Container-Dateien direkt in den Chat und erhalte gestreamte Downloads live in deine privaten Nachrichten (DMs).

---

## ✨ Hauptfunktionen

- ⚡ **Universeller Smart Drop:**
  - **Filehoster & Videoseiten:** Rapidgator, DDownload, 1fichier, Mega, YouTube uvm.
  - **Torrents & Usenet:** Drag & Drop von `.torrent`- & `.nzb`-Dateien oder `magnet:?`-Links.
  - **Container-Entschlüsselung:** `.dlc`-Dateien werden automatisch entschlüsselt und heruntergeladen.
- 📦 **Gemischte Multi-Batch Drops:**
  - Beliebig viele Links, Torrents, NZBs und DLCs gleichzeitig in einer einzigen Chat-Nachricht.
- ⚡ **Instant-Cache Hit Erkennung:**
  - Erkennt automatisch auf Premiumize-Servern gecachte Dateien (0 Sek. Wartezeit).
- 🌐 **Echtzeit Live-Streaming:**
  - Streamt Downloads direkt zu **GoFile** oder **Pixeldrain**, ohne lokalen Festplattenspeicher zu belegen. Dateien ≤10 MB werden direkt per Discord-Anhang zugestellt.
- 🚦 **Echtzeit-Live-Fortschritt & Phasenfarben:**
  - Live-Ladebalken, Geschwindigkeit und ETA alle 2,5 Sek. mit dynamischem Farbwechsel (Gelb ➔ Blau ➔ Lila ➔ Grün).
- 🔒 **100% Privatsphäre & User-Isolation:**
  - Chat-Nachrichten werden sofort diskret gelöscht. Live-Fortschritt und fertige Dateien landen in deinen privaten DMs.
  - Normale Nutzer sehen bei `/status` und `/myhistory` nur ihre eigenen Downloads.
- 🌍 **Hybrid Multi-Language Support (i18n):**
  - Öffentliche Hilfetafeln folgen der Server-Einstellung (`BOT_LANGUAGE=en` oder `de`).
  - Private DMs und Buttons passen sich automatisch an die Discord-Sprache des jeweiligen Nutzers an.
- 🧹 **24/7 Automatisches Wartungssystem:**
  - Täglicher Hintergrundtask bereinigt `/temp`, vakuumisiert die SQLite-Historie (>90 Tage) und aktualisiert den Hoster-Cache.
- 🚨 **Admin Frühwarnsystem:**
  - Automatische Warnungen via Telegram und Discord Log-Kanal bei < 20% Fair-Use Punkten oder > 950 GB Cloud-Speicher.

---

## 🤖 Discord Bot im Developer Portal erstellen & Rechte einrichten

Befolge diese Schritte, um deinen Discord Bot zu erstellen und einzuladen:

1. **Application erstellen:**
   - Öffne das **[Discord Developer Portal](https://discord.com/developers/applications)**.
   - Klicke oben rechts auf **"New Application"**, vergib einen Namen (z. B. `PREMIUMIZER`) und klicke auf **Create**.
2. **Bot-Token abrufen:**
   - Klicke im linken Menü auf **"Bot"**.
   - Klicke auf **"Reset Token"** (oder **"Copy"**), um dein `DISCORD_BOT_TOKEN` zu kopieren.
3. **Privileged Gateway Intents aktivieren (WICHTIG!):**
   - Scrolle im **"Bot"**-Reiter nach unten zum Abschnitt **"Privileged Gateway Intents"**.
   - Aktiviere **`MESSAGE CONTENT INTENT`** *(Erforderlich, damit Smart Drop Links und Datei-Anhänge im Chat auslesen kann)*.
4. **Bot auf den Server einladen:**
   - Klicke im linken Menü auf **"OAuth2"** ➔ **"URL Generator"**.
   - Wähle unter **Scopes**:
     - `bot`
     - `applications.commands`
   - Wähle unter **Bot Permissions**:
     - `Send Messages` (Nachrichten senden)
     - `Embed Links` (Links einbetten)
     - `Attach Files` (Dateien anhängen)
     - `Read Message History` (Nachrichtenverlauf lesen)
     - `Manage Messages` (Nachrichten verwalten - *erforderlich, um Links aus Datenschutzgründen im Kanal sofort zu löschen*)
   - Kopiere die generierte URL ganz unten, öffne sie im Browser und wähle deinen Server aus.

---

## 📋 Slash Commands

| Befehl | Beschreibung |
| :--- | :--- |
| `/status` | Zeigt laufende Downloads, Fortschrittsbalken und Geschwindigkeiten an (User-isoliert). |
| `/cancel <task_id>` | Bricht einen laufenden Download ab (oder Klick auf den Abbrechen-Button in DMs). |
| `/posthelp [pin]` | *(Admin)* Postet die permanente interaktive Hilfetafel mit Buttons in den Kanal. |
| `/botlogs [lines]` | *(Admin)* Zeigt die neuesten Fehler- und Status-Logs des Bots direkt in Discord an. |

---

## 🚀 Schnellstart & Installation

### Option 1: Mit Docker Compose (Empfohlen • 2 Minuten)

```bash
# 1. Repository klonen
git clone https://github.com/KAiSER086/PREMIUMIZER.git
cd PREMIUMIZER

# 2. Konfiguration anlegen & ausfüllen
cp .env.example .env
nano .env

# 3. Mit Docker im Hintergrund starten
docker-compose up -d --build
```

---

### Option 2: Linux Systemd Dienst (Standalone)

```bash
# 1. Repository klonen & Abhängigkeiten installieren
git clone https://github.com/KAiSER086/PREMIUMIZER.git
cd PREMIUMIZER
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Konfiguration anlegen & ausfüllen
cp .env.example .env
nano .env

# 3. Hintergrund-Dienst aktivieren & starten
sudo cp premiumize-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now premiumize-bot
```

---

## ⚙️ Konfiguration (`.env`)

```env
# Discord Bot Token (aus dem Discord Developer Portal)
DISCORD_BOT_TOKEN=dein_discord_bot_token_hier

# Premiumize API Key (https://www.premiumize.me/account)
PREMIUMIZE_API_KEY=dein_premiumize_api_key_hier

# Bot-Sprache (en = Englisch Standard, de = Deutsch)
BOT_LANGUAGE=de

# Standard Stream-Uploader (gofile, pixeldrain, litterbox)
DEFAULT_UPLOADER=gofile

# Maximale gleichzeitige Downloads
MAX_CONCURRENT_TASKS=2

# Automatisches Aufräumen (empfohlen: true)
AUTOCLEAN_LOCAL=true
AUTOCLEAN_PREMIUMIZE=true

# Optionale Admin-Benachrichtigungen (Telegram & Discord Audit-Kanal)
# TELEGRAM_BOT_TOKEN= (Token von @BotFather)
# TELEGRAM_CHAT_ID= (Deine Telegram Chat-ID)
# ADMIN_CHANNEL_ID= (Discord Audit-Kanal ID)
```

---

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.

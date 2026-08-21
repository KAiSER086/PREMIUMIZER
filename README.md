# ⚡ PREMIUMIZER • Universal Highspeed Downloader & Debrid Discord Bot

[![Discord.py](https://img.shields.io/badge/discord.py-v2.3.2-blue.svg)](https://github.com/Rapptz/discord.py)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](docker-compose.yml)
[![i18n](https://img.shields.io/badge/i18n-English%20%7C%20German-orange.svg)](#-internationalization-i18n)

> 🇩🇪 **[Hier klicken für die deutsche Dokumentation (README_DE.md)](README_DE.md)**

A high-performance Discord Bot that turns any Discord channel into a private, highspeed debrid download center powered by **[Premiumize.me](https://www.premiumize.me)**. Drop links, torrents, or container files directly into Discord and receive live streamed downloads straight to your private DMs.

---

## ✨ Key Features

- ⚡ **Universal Smart Drop:**
  - **Filehosters & Video Sites:** Rapidgator, DDownload, 1fichier, Mega, YouTube, and 50+ supported hosters.
  - **Torrents & Usenet:** Drag & drop `.torrent` and `.nzb` files or paste `magnet:?` links.
  - **Container Decryption:** Drop `.dlc` containers — links are automatically decrypted and downloaded.
- 📦 **Mixed Multi-Batch Drops:**
  - Post any combination of multiple links, torrents, NZBs, and DLCs simultaneously in a single message.
- ⚡ **Instant-Cache Hit Detection:**
  - Automatically detects cached files on Premiumize servers (0s cloud wait time).
- 🌐 **Direct Live-Streaming:**
  - Streams downloads directly to **GoFile** or **Pixeldrain** without filling local server storage. Files ≤10 MB are delivered directly as native Discord attachments.
- 🚦 **Real-Time Live Progress & Phase Colors:**
  - Live progress bars, transfer speeds, and ETA updated every 2.5s with dynamic phase colors (Yellow ➔ Blue ➔ Purple ➔ Green).
- 🔒 **100% Privacy & User Isolation:**
  - Chat posts are auto-deleted immediately upon arrival. Live progress and final downloads land in private user DMs.
  - Regular users only see their own downloads in `/status` and `/myhistory`, while server admins can view global activity.
- 🌍 **Hybrid Multi-Language Support (i18n):**
  - Public help boards follow server configuration (`BOT_LANGUAGE=en` or `de`).
  - Private DMs, buttons, and status messages automatically adapt to each user's Discord client language.
- 🧹 **24/7 Automated Maintenance:**
  - Daily cleanup worker cleans stale temp files, defragments and prunes SQLite history (>90 days), and refreshes service caches.
- 🚨 **Admin Quota & Storage Early Warnings:**
  - Automatic alerts via Telegram and Discord log channel when Fair-Use points drop below 20% or cloud storage exceeds 950 GB.

---

## 🤖 Creating the Discord Bot & Permissions

Follow these steps to create your bot in the Discord Developer Portal:

1. **Create Application:**
   - Open the **[Discord Developer Portal](https://discord.com/developers/applications)**.
   - Click **"New Application"**, enter a name (e.g. `PREMIUMIZER`), and click **Create**.
2. **Create Bot & Get Token:**
   - Navigate to the **"Bot"** tab in the left sidebar.
   - Click **"Reset Token"** (or **"Copy"**) to obtain your `DISCORD_BOT_TOKEN`.
3. **Enable Privileged Gateway Intents (CRITICAL!):**
   - In the **"Bot"** tab, scroll down to **"Privileged Gateway Intents"**.
   - Enable **`MESSAGE CONTENT INTENT`** *(Required for Smart Drop to read links and attachments)*.
4. **Generate Bot Invite Link:**
   - Navigate to **"OAuth2"** ➔ **"URL Generator"**.
   - Under **Scopes**, check:
     - `bot`
     - `applications.commands`
   - Under **Bot Permissions**, check:
     - `Send Messages`
     - `Embed Links`
     - `Attach Files`
     - `Read Message History`
     - `Manage Messages` *(Required to auto-delete user links for privacy)*
   - Copy the generated URL at the bottom and open it in your browser to invite the bot to your server.

---

## 📋 Slash Commands

| Command | Description |
| :--- | :--- |
| `/status` | View active downloads, progress bars, and speeds (User-isolated). |
| `/cancel <task_id>` | Cancels a running download task (or click the Cancel button in DMs). |
| `/posthelp [pin]` | *(Admin)* Posts the permanent interactive help board with buttons to the channel. |
| `/botlogs [lines]` | *(Admin)* View recent bot activity and error logs directly inside Discord. |

---

## 🚀 Quick Start & Installation

### Option 1: Docker Compose (Recommended • 2 Minutes)

```bash
# 1. Clone the repository
git clone https://github.com/KAiSER086/PREMIUMIZER.git
cd PREMIUMIZER

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Start with Docker in background
docker-compose up -d --build
```

---

### Option 2: Linux Systemd Service (Standalone)

```bash
# 1. Clone repository & install dependencies
git clone https://github.com/KAiSER086/PREMIUMIZER.git
cd PREMIUMIZER
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Enable & start background service
sudo cp premiumize-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now premiumize-bot
```

---

## ⚙️ Configuration (`.env`)

```env
# Discord Bot Token (from Discord Developer Portal)
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Premiumize API Key (https://www.premiumize.me/account)
PREMIUMIZE_API_KEY=your_premiumize_api_key_here

# Bot Language (en = English default, de = German)
BOT_LANGUAGE=en

# Default Stream Uploader (gofile, pixeldrain, litterbox)
DEFAULT_UPLOADER=gofile

# Maximum concurrent download tasks
MAX_CONCURRENT_TASKS=2

# Automatic storage cleanup (recommended: true)
AUTOCLEAN_LOCAL=true
AUTOCLEAN_PREMIUMIZE=true

# Optional Admin Notifications (Telegram & Discord Audit Log)
# TELEGRAM_BOT_TOKEN= (Token from @BotFather)
# TELEGRAM_CHAT_ID= (Your Telegram Chat ID)
# ADMIN_CHANNEL_ID= (Discord Audit Channel ID)
```

---

## 🌐 Internationalization (i18n)

PREMIUMIZER features a built-in hybrid internationalization engine:
- **Server Language:** Set `BOT_LANGUAGE=en` or `BOT_LANGUAGE=de` in `.env` for the permanent channel help board.
- **Client Localization:** Interactive buttons, progress DMs, and slash command descriptions automatically localize based on each user's Discord app language.

---

## 📄 License

This project is licensed under the MIT License.

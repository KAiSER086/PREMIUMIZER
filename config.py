import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
BOT_LANGUAGE = os.getenv("BOT_LANGUAGE", "en").strip().lower()

# Premiumize Configuration
PREMIUMIZE_API_KEY = os.getenv("PREMIUMIZE_API_KEY", "").strip()

# Free Uploader Configuration
DEFAULT_UPLOADER = os.getenv("DEFAULT_UPLOADER", "auto").strip().lower()
PIXELDRAIN_API_KEY = os.getenv("PIXELDRAIN_API_KEY", "").strip()
GOFILE_API_TOKEN = os.getenv("GOFILE_API_TOKEN", "").strip()

# Storage & Download Settings
BASE_DIR = Path(__file__).resolve().parent
TEMP_DOWNLOAD_DIR = Path(os.getenv("TEMP_DOWNLOAD_DIR", str(BASE_DIR / "downloads")))
TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"

# Discord Attachment Upload Limit: 10MB (Standard Discord Bot Limit for unboosted servers)
DISCORD_MAX_UPLOAD_MB = float(os.getenv("DISCORD_MAX_UPLOAD_MB", "10"))
DISCORD_MAX_UPLOAD_BYTES = int(DISCORD_MAX_UPLOAD_MB * 1024 * 1024)

# Concurrency & Performance
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(1024 * 1024)))  # 1MB chunks

# Cleanup Options
AUTOCLEAN_LOCAL = os.getenv("AUTOCLEAN_LOCAL", "true").lower() in ("true", "1", "yes")
AUTOCLEAN_PREMIUMIZE = os.getenv("AUTOCLEAN_PREMIUMIZE", "true").lower() in ("true", "1", "yes")

# Privacy & Notification Mode (true = only visible to command author)
EPHEMERAL_MODE = os.getenv("EPHEMERAL_MODE", "true").lower() in ("true", "1", "yes")
DM_NOTIFY_USER = os.getenv("DM_NOTIFY_USER", "false").lower() in ("true", "1", "yes")

# Telegram Notifications (Optional Admin & User Logs)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()  # Admin Chat ID(s)
TELEGRAM_ADMIN_CHAT_IDS = [
    cid.strip()
    for cid in os.getenv("TELEGRAM_CHAT_ID", "").split(",")
    if cid.strip()
]

# User-specific Telegram notifications: {discord_user_id: telegram_chat_id}
TELEGRAM_USER_CHATS = {}
raw_user_chats = os.getenv("TELEGRAM_USER_CHATS", "")
if raw_user_chats:
    for item in raw_user_chats.split(","):
        item = item.strip()
        if ":" in item:
            d_id, tg_id = item.split(":", 1)
            d_id, tg_id = d_id.strip(), tg_id.strip()
            if d_id.isdigit() and tg_id:
                TELEGRAM_USER_CHATS[int(d_id)] = tg_id

# Discord Admin Notifications (Audit Log)
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0")) if os.getenv("ADMIN_USER_ID", "0").isdigit() else 0
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "0")) if os.getenv("ADMIN_CHANNEL_ID", "0").isdigit() else 0

# Access Control (comma separated IDs; if empty -> allow all)
ALLOWED_USERS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
]
ALLOWED_ROLES = [
    int(rid.strip())
    for rid in os.getenv("ALLOWED_ROLE_IDS", "").split(",")
    if rid.strip().isdigit()
]
ALLOWED_CHANNELS = [
    int(cid.strip())
    for cid in os.getenv("ALLOWED_CHANNEL_IDS", "").split(",")
    if cid.strip().isdigit()
]

def validate_config():
    """Validates the critical environment settings."""
    errors = []
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN is not set in environment (.env)!")
    if not PREMIUMIZE_API_KEY:
        errors.append("PREMIUMIZE_API_KEY is not set in environment (.env)!")
    return errors

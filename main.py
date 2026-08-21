import sys
import os
import asyncio
import logging
import signal
import discord
from discord.ext import commands

import config
from core.database import DatabaseManager
from core.premiumize import PremiumizeClient
from core.uploader import UploaderManager
from core.downloader import HttpDownloader
from core.task_manager import TaskManager
from cogs.download_cog import DownloadCog
from cogs.help_cog import HelpCog, PermanentHelpView

import logging.handlers
from pathlib import Path

# Configure Persistent Logging Directory & Handlers
LOGS_DIR = config.BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 1. General Bot Log (Max 5MB per file, keeps 5 backups)
general_file_handler = logging.handlers.RotatingFileHandler(
    LOGS_DIR / "bot.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
general_file_handler.setLevel(logging.INFO)
general_file_handler.setFormatter(log_formatter)

# 2. Dedicated Error Log (Records Warnings & Errors with Tracebacks)
error_file_handler = logging.handlers.RotatingFileHandler(
    LOGS_DIR / "errors.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
error_file_handler.setLevel(logging.WARNING)
error_file_handler.setFormatter(log_formatter)

# 3. Console Output Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# Apply handlers to root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(general_file_handler)
root_logger.addHandler(error_file_handler)
root_logger.addHandler(console_handler)

# Suppress noisy discord voice warnings (PyNaCl/davey) since bot operates on text/files
logging.getLogger("discord.client").setLevel(logging.ERROR)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)

logger = logging.getLogger("DiscordPMBot")

class PremiumizeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        # Initialize Core Services
        self.db_manager = DatabaseManager(config.DB_PATH)
        self.pm_client = PremiumizeClient(config.PREMIUMIZE_API_KEY)
        self.uploader_manager = UploaderManager(
            default_uploader=config.DEFAULT_UPLOADER,
            pixeldrain_key=config.PIXELDRAIN_API_KEY,
            gofile_token=config.GOFILE_API_TOKEN
        )
        self.downloader = HttpDownloader(chunk_size=config.CHUNK_SIZE)
        self.task_manager = TaskManager(
            pm_client=self.pm_client,
            uploader_manager=self.uploader_manager,
            downloader=self.downloader,
            db_manager=self.db_manager,
            temp_dir=config.TEMP_DOWNLOAD_DIR,
            max_concurrent=config.MAX_CONCURRENT_TASKS,
            autoclean_pm=config.AUTOCLEAN_PREMIUMIZE,
            autoclean_local=config.AUTOCLEAN_LOCAL,
            bot=self
        )
        self.has_synced = False

    async def setup_hook(self):
        # 1. Initialize SQLite Database
        await self.db_manager.init_db()

        # 2. Register Cogs
        await self.add_cog(DownloadCog(self, self.task_manager))
        await self.add_cog(HelpCog(self, self.pm_client, self.db_manager))

        # 3. Register Persistent Views for permanent buttons
        self.add_view(PermanentHelpView(self.pm_client, self.db_manager))

        # 4. Start Task Manager Queue
        self.task_manager.start()
        logger.info("Task Manager worker started.")

    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        
        # Sync slash commands once on connection
        if not self.has_synced:
            try:
                logger.info("Syncing slash commands with Discord...")
                synced = await self.tree.sync()
                self.has_synced = True
                logger.info(f"Successfully synced {len(synced)} slash commands.")
            except Exception as e:
                logger.error(f"Failed to sync slash commands: {e}")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Downloads"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)
        logger.info("Bot is ready and listening for commands!")

    async def close(self):
        logger.info("Shutting down bot...")
        await self.task_manager.stop()
        await super().close()


async def main():
    errors = config.validate_config()
    if errors:
        logger.error("Configuration errors found:")
        for err in errors:
            logger.error(f" - {err}")
        logger.error("Please verify your .env file configuration.")
        return

    bot = PremiumizeBot()

    try:
        await bot.start(config.DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord Bot Token! Please verify DISCORD_BOT_TOKEN in your .env file.")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())

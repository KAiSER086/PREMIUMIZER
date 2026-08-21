import os
import shutil
import time
import uuid
import asyncio
import aiohttp
import logging
import io
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import discord

import datetime
import config
from core.premiumize import PremiumizeClient
from core.uploader import UploaderManager
from core.downloader import HttpDownloader
from core.database import DatabaseManager
from core.i18n import t
from core.utils import (
    safe_float,
    safe_int,
    format_bytes,
    format_speed,
    format_eta,
    render_progress_bar,
    create_task_embed,
    create_success_embed,
    create_error_embed
)

logger = logging.getLogger(__name__)

class DownloadTask:
    def __init__(
        self,
        task_id: str,
        user_id: int,
        user_name: str,
        channel_id: int,
        source: str,
        uploader_name: str = "auto",
        torrent_bytes: Optional[bytes] = None,
        torrent_filename: Optional[str] = None,
        autoclean_pm: bool = True,
        autoclean_local: bool = True,
        user_lang: str = "en"
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.user_name = user_name
        self.channel_id = channel_id
        self.source = source
        self.uploader_name = uploader_name or "auto"
        self.torrent_bytes = torrent_bytes
        self.torrent_filename = torrent_filename
        self.autoclean_pm = autoclean_pm
        self.autoclean_local = autoclean_local
        self.user_lang = user_lang

        self.status = "QUEUED"  # QUEUED, PM_TRANSFER, STREAMING, COMPLETED, FAILED, CANCELLED
        self.phase_text = t("phase_queued", lang=user_lang)
        self.progress_percent = 0.0
        self.speed = 0.0
        self.eta = 0.0
        self.file_name = torrent_filename or "Unbekannt"
        self.file_size = 0
        self.download_url = ""
        self.error_message = ""
        
        self.is_folder = False
        self.folder_files: List[Dict[str, Any]] = []
        self.is_discord_attachment = False
        self.is_cached = False

        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

        self.cancel_event = asyncio.Event()
        self.pm_transfer_id: Optional[str] = None
        self.pm_file_id: Optional[str] = None
        self.pm_folder_id: Optional[str] = None
        self.local_file_path: Optional[Path] = None

        # Discord message reference for live editing
        self.discord_message: Optional[discord.Message] = None
        self.last_embed_update = 0.0


class TaskManager:
    PHASE_COLORS = {
        "QUEUED": 0xF39C12,       # Gelb / Orange
        "PM_TRANSFER": 0x3498DB,  # Blau
        "STREAMING": 0x9B59B6,    # Lila
        "COMPLETED": 0x2ECC71,    # Grün
        "FAILED": 0xE74C3C,       # Rot
        "CANCELLED": 0xE74C3C     # Rot
    }

    def __init__(
        self,
        pm_client: PremiumizeClient,
        uploader_manager: UploaderManager,
        downloader: HttpDownloader,
        db_manager: DatabaseManager,
        temp_dir: Path,
        max_concurrent: int = 2,
        autoclean_pm: bool = True,
        autoclean_local: bool = True,
        bot: Optional[discord.Client] = None
    ):
        self.pm_client = pm_client
        self.uploader_manager = uploader_manager
        self.downloader = downloader
        self.db_manager = db_manager
        self.temp_dir = temp_dir
        self.max_concurrent = max_concurrent
        self.default_autoclean_pm = autoclean_pm
        self.default_autoclean_local = autoclean_local
        self.bot = bot

        self.tasks: Dict[str, DownloadTask] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.worker_task: Optional[asyncio.Task] = None
        self.maintenance_task: Optional[asyncio.Task] = None
        self.running = False
        self.last_quota_warning = 0.0

    def start(self):
        """Starts background worker queue and daily maintenance."""
        if not self.running:
            self.running = True
            self.worker_task = asyncio.create_task(self._queue_worker())
            self.maintenance_task = asyncio.create_task(self._daily_maintenance_worker())
            logger.info("TaskManager worker and maintenance service started.")

    async def stop(self):
        """Stops the worker and maintenance service."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
        if self.maintenance_task:
            self.maintenance_task.cancel()

    async def _daily_maintenance_worker(self):
        """Runs periodic cleanup & maintenance every 24 hours."""
        while self.running:
            try:
                # Wait 60s after startup for first maintenance run
                await asyncio.sleep(60)
                if not self.running:
                    break

                logger.info("Running daily maintenance routine...")

                # 1. Clean temp directory of stale files (> 2 hours old)
                now = time.time()
                cleaned_files = 0
                if self.temp_dir.exists():
                    for item in self.temp_dir.iterdir():
                        try:
                            if item.is_file():
                                if (now - item.stat().st_mtime) > 7200:
                                    item.unlink()
                                    cleaned_files += 1
                            elif item.is_dir():
                                if (now - item.stat().st_mtime) > 7200:
                                    shutil.rmtree(item, ignore_errors=True)
                                    cleaned_files += 1
                        except Exception as e:
                            logger.warning(f"Failed to clean temp item {item}: {e}")

                # 2. Refresh Premiumize services list
                try:
                    await self.pm_client.get_services_list()
                except Exception as e:
                    logger.warning(f"Maintenance services refresh failed: {e}")

                # 3. Prune DB history (> 90 days) & VACUUM
                pruned_rows = await self.db_manager.prune_old_records(retention_days=90)

                logger.info(f"Daily maintenance completed: {cleaned_files} temp items cleaned, {pruned_rows} old records pruned.")

                # Wait 24 hours until next maintenance cycle
                await asyncio.sleep(86400)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily maintenance worker: {e}")
                await asyncio.sleep(3600)

    def generate_task_id(self) -> str:
        return f"pm-{uuid.uuid4().hex[:6]}"

    async def add_task(
        self,
        user_id: int,
        user_name: str,
        channel_id: int,
        source: str,
        uploader_name: str = "auto",
        torrent_bytes: Optional[bytes] = None,
        torrent_filename: Optional[str] = None,
        autoclean_pm: Optional[bool] = None,
        autoclean_local: Optional[bool] = None,
        discord_message: Optional[discord.Message] = None,
        user_lang: str = "en"
    ) -> DownloadTask:
        """Creates and enqueues a new download task."""
        task_id = self.generate_task_id()
        task = DownloadTask(
            task_id=task_id,
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            source=source,
            uploader_name=uploader_name or "auto",
            torrent_bytes=torrent_bytes,
            torrent_filename=torrent_filename,
            autoclean_pm=self.default_autoclean_pm if autoclean_pm is None else autoclean_pm,
            autoclean_local=self.default_autoclean_local if autoclean_local is None else autoclean_local,
            user_lang=user_lang
        )
        task.discord_message = discord_message
        self.tasks[task_id] = task
        await self.queue.put(task)
        logger.info(f"Task {task_id} added to queue by {user_name}.")
        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self.tasks.get(task_id)

    def get_active_tasks(self) -> List[DownloadTask]:
        return [
            t for t in self.tasks.values()
            if t.status in ("QUEUED", "PM_TRANSFER", "STREAMING", "DOWNLOADING", "UPLOADING")
        ]

    async def cancel_task(self, task_id: str, cancelled_by: str = "Benutzer") -> bool:
        """Cancels an active or queued task."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.status in ("COMPLETED", "FAILED", "CANCELLED"):
            return False

        task.cancel_event.set()
        task.status = "CANCELLED"
        task.error_message = f"Vorgang abgebrochen durch {cancelled_by}."
        task.finished_at = time.time()

        # Clean up PM transfer if active
        if task.pm_transfer_id:
            try:
                await self.pm_client.delete_transfer(task.pm_transfer_id)
            except Exception:
                pass

        await self._update_discord_message(
            task,
            embed=create_error_embed(task.task_id, task.user_name, task.error_message, task.file_name),
            force=True
        )
        return True

    async def unrestrict_url(self, user_id: int, user_name: str, url: str) -> Dict[str, Any]:
        """Directly unrestricts a hoster URL instantly using Premiumize directdl endpoint."""
        url = url.strip()
        file_name = "Unbekannte Datei"
        direct_link = ""
        file_size = 0

        # Method 1: Instant directdl API call
        try:
            res_dl = await self.pm_client.directdl(src=url)
            direct_link = res_dl.get("location") or ""
            file_name = res_dl.get("filename") or file_name
            file_size = safe_int(res_dl.get("filesize"), 0)
            
            if not direct_link and res_dl.get("content"):
                first_item = res_dl["content"][0]
                direct_link = first_item.get("link") or ""
                file_name = first_item.get("path") or file_name
                file_size = safe_int(first_item.get("size"), file_size)
        except Exception as dl_err:
            logger.info(f"directdl endpoint not available for URL ({url[:60]}...), trying transfer create fallback: {dl_err}")

        # Method 2: Transfer create fallback
        if not direct_link:
            res = await self.pm_client.create_transfer(src=url)
            transfer_id = res.get("id")
            if res.get("name"):
                file_name = res.get("name")

            for _ in range(30):
                status_obj = await self.pm_client.get_transfer_status(transfer_id)
                if not status_obj:
                    break
                
                if status_obj.get("file_id"):
                    item_info = await self.pm_client.get_item_details(status_obj["file_id"])
                    direct_link = item_info.get("directlink") or item_info.get("link") or ""
                    file_name = item_info.get("name") or file_name
                    file_size = safe_int(item_info.get("size"), 0)
                    if direct_link:
                        break

                if status_obj.get("folder_id"):
                    folder_info = await self.pm_client.get_folder_contents(status_obj["folder_id"])
                    items = folder_info.get("content", [])
                    file_items = [i for i in items if i.get("type") == "file"]
                    if file_items:
                        file_items.sort(key=lambda x: safe_int(x.get("size"), 0), reverse=True)
                        direct_link = file_items[0].get("directlink") or file_items[0].get("link") or ""
                        file_name = file_items[0].get("name") or file_name
                        file_size = safe_int(file_items[0].get("size"), 0)
                        if direct_link:
                            break

                if status_obj.get("status") in ("finished", "seeding"):
                    if status_obj.get("file_id"):
                        item_info = await self.pm_client.get_item_details(status_obj["file_id"])
                        direct_link = item_info.get("directlink") or item_info.get("link") or ""
                        file_name = item_info.get("name") or file_name
                        file_size = safe_int(item_info.get("size"), 0)
                    break
                elif status_obj.get("status") in ("error", "banned", "timeout"):
                    raise Exception(f"Premiumize Fehler: {status_obj.get('message', status_obj.get('status'))}")

                await asyncio.sleep(1.5)

        if not direct_link:
            raise Exception("Premiumize konnte keinen Direktlink für diese URL auflösen.")

        # Record in DB
        unrestrict_task_id = self.generate_task_id()
        await self.db_manager.record_download(
            task_id=unrestrict_task_id,
            user_id=user_id,
            user_name=user_name,
            file_name=file_name,
            file_size=file_size,
            source_url=url,
            uploader="Premiumize Direct",
            download_url=direct_link,
            status="UNRESTRICTED",
            duration_seconds=0.0
        )

        return {
            "task_id": unrestrict_task_id,
            "file_name": file_name,
            "file_size": file_size,
            "direct_link": direct_link
        }

    async def _queue_worker(self):
        """Worker loop that picks up tasks from queue and executes them with concurrency limit."""
        while self.running:
            try:
                task: DownloadTask = await self.queue.get()
                asyncio.create_task(self._process_task_with_semaphore(task))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue worker: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_task_with_semaphore(self, task: DownloadTask):
        async with self.semaphore:
            await self._execute_task(task)
            self.queue.task_done()

    async def _execute_task(self, task: DownloadTask):
        task.started_at = time.time()
        logger.info(f"Starting execution of task {task.task_id} ({task.file_name})...")

        try:
            # -------------------------------------------------------------
            # STEP 1: PREMIUMIZE CLOUD TRANSFER
            # -------------------------------------------------------------
            task.status = "PM_TRANSFER"
            task.phase_text = "⏳ 1/2: Übertragung in Premiumize Cloud..."

            # Check if source is already cached on Premiumize
            if task.source and not task.torrent_bytes and not task.source.startswith(("Torrent:", "Usenet NZB:")):
                try:
                    cache_check = await self.pm_client.check_cache([task.source])
                    if cache_check.get("status") == "success" and cache_check.get("response", [False])[0] is True:
                        task.is_cached = True
                        task.phase_text = "⚡ Instant-Cache Hit: Sofortige Bereitstellung..."
                        logger.info(f"Task {task.task_id} is cached on Premiumize servers (Instant Cache Hit)!")
                except Exception:
                    pass

            await self._update_discord_status(task, "Transfer wird bei Premiumize initialisiert...", 0.0)

            pm_res = await self.pm_client.create_transfer(
                src=task.source if not task.torrent_bytes else None,
                file_bytes=task.torrent_bytes,
                filename=task.torrent_filename
            )

            task.pm_transfer_id = pm_res.get("id")
            if pm_res.get("name"):
                task.file_name = pm_res.get("name")

            # Poll Premiumize transfer status until finished
            direct_download_url = None

            while not task.cancel_event.is_set():
                status_obj = await self.pm_client.get_transfer_status(task.pm_transfer_id)
                if not status_obj:
                    break

                pm_status = str(status_obj.get("status") or "").lower()
                task.progress_percent = safe_float(status_obj.get("progress"), 0.0) * 100.0
                task.speed = safe_float(status_obj.get("speed"), 0.0)
                task.eta = safe_float(status_obj.get("eta"), 0.0)
                if status_obj.get("name"):
                    task.file_name = status_obj.get("name")

                task.pm_file_id = status_obj.get("file_id")
                task.pm_folder_id = status_obj.get("folder_id")

                details = f"⚡ Geschwindigkeit: `{format_speed(task.speed)}` • ⏳ Restzeit: `{format_eta(task.eta)}`"
                await self._update_discord_status(
                    task,
                    f"Cloud-Download: `{pm_status.capitalize()}` ({status_obj.get('message', '') or ''})",
                    task.progress_percent,
                    details=details
                )

                if pm_status in ("finished", "seeding"):
                    break
                elif pm_status in ("error", "timeout", "deleted", "banned"):
                    raise Exception(f"Premiumize Fehler: {status_obj.get('message', pm_status)}")

                await asyncio.sleep(2.5)

            if task.cancel_event.is_set():
                return

            # -------------------------------------------------------------
            # STEP 2: RESOLVE DIRECT LINK / ZIP MULTI-FILE
            # -------------------------------------------------------------
            if task.pm_folder_id:
                folder_info = await self.pm_client.get_folder_contents(task.pm_folder_id)
                items = folder_info.get("content", [])
                file_items = [i for i in items if i.get("type") == "file"]
                task.folder_files = file_items

                # Try generating ZIP for entire folder
                zip_url = await self.pm_client.generate_zip_url(folder_id=task.pm_folder_id)
                if zip_url:
                    direct_download_url = zip_url
                    folder_name = folder_info.get("name") or task.file_name or "Download_Paket"
                    if not folder_name.lower().endswith(".zip"):
                        folder_name = f"{folder_name}.zip"
                    task.file_name = folder_name
                    task.is_folder = True
                    task.file_size = sum(safe_int(i.get("size"), 0) for i in file_items)
                elif file_items:
                    file_items.sort(key=lambda x: safe_int(x.get("size"), 0), reverse=True)
                    primary_file = file_items[0]
                    direct_download_url = primary_file.get("directlink") or primary_file.get("link")
                    task.file_name = primary_file.get("name") or task.file_name
                    task.file_size = safe_int(primary_file.get("size"), 0)
            elif task.pm_file_id:
                file_info = await self.pm_client.get_item_details(task.pm_file_id)
                direct_download_url = file_info.get("directlink") or file_info.get("link")
                task.file_name = file_info.get("name") or task.file_name
                task.file_size = safe_int(file_info.get("size"), 0)
            else:
                status_obj = await self.pm_client.get_transfer_status(task.pm_transfer_id)
                if status_obj and status_obj.get("file_id"):
                    file_info = await self.pm_client.get_item_details(status_obj["file_id"])
                    direct_download_url = file_info.get("directlink") or file_info.get("link")
                    task.file_name = file_info.get("name") or task.file_name
                    task.file_size = safe_int(file_info.get("size"), 0)

            if not direct_download_url:
                raise Exception("Premiumize Direktlink konnte nicht generiert werden.")

            # -------------------------------------------------------------
            # STEP 3: DISCORD DIRECT ATTACHMENT OR STREAMING PIPE
            # -------------------------------------------------------------
            # Only try Discord attachment if <= 10MB (or explicit discord choice <= 10MB)
            try_discord_attachment = (
                (task.uploader_name in ("auto", "discord") and task.file_size > 0 and task.file_size <= config.DISCORD_MAX_UPLOAD_BYTES)
            )

            discord_file_attachment: Optional[discord.File] = None
            discord_send_successful = False

            if try_discord_attachment:
                task.status = "STREAMING"
                task.phase_text = "📥 Bereite Datei als Discord-Anhang vor..."
                await self._update_discord_status(task, "Datei wird für Discord-Anhang vorbereitet...", 50.0)

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(direct_download_url) as resp:
                            if resp.status == 200:
                                file_bytes = await resp.read()
                                if len(file_bytes) <= config.DISCORD_MAX_UPLOAD_BYTES:
                                    task.file_size = len(file_bytes)
                                    buf = io.BytesIO(file_bytes)
                                    discord_file_attachment = discord.File(fp=buf, filename=task.file_name)
                except Exception as dl_att_err:
                    logger.warning(f"Could not buffer file for Discord attachment: {dl_att_err}")
                    discord_file_attachment = None

            # Attempt sending attachment directly to user PM/DM
            if discord_file_attachment and self.bot:
                try:
                    user_obj = self.bot.get_user(task.user_id)
                    if not user_obj:
                        user_obj = await self.bot.fetch_user(task.user_id)
                        
                    temp_success_embed = create_success_embed(
                        task_id=task.task_id,
                        user_name=task.user_name,
                        file_name=task.file_name,
                        file_size=task.file_size,
                        download_url="",
                        uploader_name="Discord Anhang (PM)",
                        duration_str=format_eta(int(time.time() - task.started_at)),
                        raw_source=task.source,
                        is_discord_attachment=True
                    )
                    
                    if user_obj:
                        try:
                            await user_obj.send(
                                content=f"✅ Hier ist deine Datei **{task.file_name}**:",
                                embed=temp_success_embed,
                                file=discord_file_attachment
                            )
                            task.is_discord_attachment = True
                            task.uploader_name = "Discord Anhang (PM)"
                            discord_send_successful = True
                        except discord.Forbidden:
                            # User has DMs closed, post in channel
                            if task.discord_message:
                                await task.discord_message.channel.send(
                                    content=f"✅ <@{task.user_id}> Hier ist deine Datei (deine DMs sind geschlossen):",
                                    embed=temp_success_embed,
                                    file=discord_file_attachment
                                )
                                task.is_discord_attachment = True
                                task.uploader_name = "Discord Anhang"
                                discord_send_successful = True
                except Exception as attach_err:
                    logger.warning(f"Discord DM upload failed (e.g. 413 size limit), falling back to GoFile: {attach_err}")
                    discord_send_successful = False
                    task.is_discord_attachment = False

            # If not sent via Discord attachment, stream to GoFile/Pixeldrain
            if not discord_send_successful:
                task.status = "STREAMING"
                target_uploader = task.uploader_name if task.uploader_name not in ("auto", "discord", "Discord Anhang") else "gofile"
                task.uploader_name = target_uploader
                uploader_display = target_uploader.capitalize()
                task.phase_text = f"🚀 2/2: Übertragung zu {uploader_display}..."

                async def on_stream_progress(curr: int, total: int, speed: float, eta: float):
                    task.speed = speed
                    task.eta = eta
                    pct = (curr / total * 100.0) if total > 0 else 0.0
                    task.progress_percent = pct
                    details = (
                        f"📦 Übertragen: `{format_bytes(curr)}` / `{format_bytes(total)}`\n"
                        f"⚡ Geschwindigkeit: `{format_speed(speed)}` • ⏳ Restzeit: `{format_eta(eta)}`"
                    )
                    await self._update_discord_status(
                        task,
                        f"Wird auf {task.uploader_name.capitalize()} bereitgestellt...",
                        pct,
                        details=details
                    )

                async with self.downloader.open_download_stream(direct_download_url, custom_filename=task.file_name) as (chunk_gen, stream_size, stream_name):
                    task.file_size = stream_size or task.file_size
                    task.file_name = stream_name or task.file_name

                    def make_stream():
                        return chunk_gen(cancel_event=task.cancel_event)

                    upload_res = await self.uploader_manager.upload_stream_with_fallback(
                        stream_factory=make_stream,
                        total_size=task.file_size,
                        filename=task.file_name,
                        preferred_uploader=task.uploader_name,
                        progress_callback=on_stream_progress,
                        cancel_event=task.cancel_event
                    )

                task.download_url = upload_res.get("download_url", "")
                task.uploader_name = upload_res.get("uploader", task.uploader_name)
                task.file_size = upload_res.get("file_size", task.file_size)

            if task.cancel_event.is_set():
                return

            # -------------------------------------------------------------
            # STEP 4: CLEANUP & NOTIFY
            # -------------------------------------------------------------
            task.status = "COMPLETED"
            task.finished_at = time.time()
            elapsed_sec = int(task.finished_at - task.started_at)
            duration_str = format_eta(elapsed_sec)

            # Record in SQLite Database
            await self.db_manager.record_download(
                task_id=task.task_id,
                user_id=task.user_id,
                user_name=task.user_name,
                file_name=task.file_name,
                file_size=task.file_size,
                source_url=task.source,
                uploader=task.uploader_name,
                download_url=task.download_url or ("Discord Anhang" if task.is_discord_attachment else ""),
                status="COMPLETED",
                duration_seconds=elapsed_sec
            )

            # Cloud cleanup
            if task.autoclean_pm:
                if task.pm_transfer_id:
                    try:
                        await self.pm_client.delete_transfer(task.pm_transfer_id)
                    except Exception:
                        pass
                if task.pm_file_id:
                    try:
                        await self.pm_client.delete_item(task.pm_file_id)
                    except Exception:
                        pass
                if task.pm_folder_id:
                    try:
                        await self.pm_client.delete_folder(task.pm_folder_id)
                    except Exception:
                        pass

            # Build final Discord embed & view
            success_embed = create_success_embed(
                task_id=task.task_id,
                user_name=task.user_name,
                file_name=task.file_name,
                file_size=task.file_size,
                download_url=task.download_url,
                uploader_name=task.uploader_name,
                duration_str=duration_str,
                raw_source=task.source,
                folder_files=task.folder_files if task.is_folder else None,
                is_discord_attachment=task.is_discord_attachment
            )

            view = None
            if not task.is_discord_attachment and task.download_url:
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label=f"📥 Download ({task.uploader_name.capitalize()})",
                    url=task.download_url,
                    style=discord.ButtonStyle.link
                ))

            # Send or edit Discord message
            if task.discord_message:
                try:
                    is_dm = isinstance(task.discord_message.channel, discord.DMChannel)
                    if task.is_discord_attachment:
                        if is_dm:
                            try:
                                await task.discord_message.delete()
                            except Exception:
                                pass
                        else:
                            channel_embed = discord.Embed(
                                title=t("download_complete_title", lang=task.user_lang),
                                description=f"<@{task.user_id}> • {t('download_complete_msg', lang=task.user_lang, filename=task.file_name)} 📬",
                                color=0x2ECC71,
                                timestamp=datetime.datetime.now(datetime.timezone.utc)
                            )
                            channel_embed.set_footer(text=f"Task-ID: {task.task_id}")
                            await task.discord_message.edit(
                                content=None,
                                embed=channel_embed,
                                view=None
                            )
                    else:
                        msg_content = f"✅ {t('download_complete_msg', lang=task.user_lang, filename=task.file_name)}"
                        await task.discord_message.edit(
                            content=msg_content,
                            embed=success_embed,
                            view=view
                        )
                except Exception as ex:
                    logger.warning(f"Could not edit final message for task {task.task_id}: {ex}")

            # Send admin audit notifications
            await self._send_admin_audit_notification(task, event="completed")

        except Exception as err:
            logger.error(f"Task {task.task_id} failed: {err}", exc_info=True)
            task.status = "FAILED"
            task.error_message = str(err)
            task.finished_at = time.time()

            await self.db_manager.record_download(
                task_id=task.task_id,
                user_id=task.user_id,
                user_name=task.user_name,
                file_name=task.file_name,
                file_size=task.file_size,
                source_url=task.source,
                uploader=task.uploader_name,
                download_url="",
                status="FAILED",
                duration_seconds=int(task.finished_at - (task.started_at or task.finished_at)),
                error_message=str(err)
            )

            err_embed = create_error_embed(task.task_id, task.user_name, str(err), task.file_name, lang=task.user_lang)
            await self._update_discord_message(task, embed=err_embed, force=True)
            await self._send_admin_audit_notification(task, event="failed")

    async def _send_admin_audit_notification(self, task: DownloadTask, event: str = "completed"):
        """Sends admin audit notifications to Telegram, Discord Channel, and User DM."""
        try:
            if not self.bot:
                return

            if event == "completed":
                embed = discord.Embed(
                    title="⚡ PREMIUMIZER: Download Completed",
                    description=f"**File:** `{task.file_name}`",
                    color=0x2ECC71,
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.add_field(name="👤 User", value=f"<@{task.user_id}> (`{task.user_name}`)", inline=True)
                embed.add_field(name="📦 Size", value=format_bytes(task.file_size), inline=True)
                embed.add_field(name="🌐 Uploader", value=task.uploader_name.capitalize(), inline=True)
                if task.download_url:
                    embed.add_field(name="🔗 Download Link", value=f"[Open]({task.download_url})\n`{task.download_url}`", inline=False)
                embed.add_field(name="🔗 Source", value=f"```{task.source[:150]}```", inline=False)
            elif event == "failed":
                embed = discord.Embed(
                    title="⚠️ PREMIUMIZER: Download Failed",
                    description=f"```{task.error_message[:300]}```",
                    color=0xE74C3C,
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.add_field(name="👤 User", value=f"<@{task.user_id}> (`{task.user_name}`)", inline=True)
                embed.add_field(name="🔗 Source", value=f"```{task.source[:150]}```", inline=False)
            else:
                return

            embed.set_footer(text=f"Task-ID: {task.task_id}")

            # Send to Admin Log Channel
            if config.ADMIN_CHANNEL_ID:
                ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
                if not ch:
                    try:
                        ch = await self.bot.fetch_channel(config.ADMIN_CHANNEL_ID)
                    except Exception:
                        pass
                if ch:
                    await ch.send(embed=embed, silent=True)

            # Send to Admin User
            if config.ADMIN_USER_ID:
                u = self.bot.get_user(config.ADMIN_USER_ID)
                if not u:
                    try:
                        u = await self.bot.fetch_user(config.ADMIN_USER_ID)
                    except Exception:
                        pass
                if u:
                    await u.send(embed=embed, silent=True)

            # Send to Telegram
            if config.TELEGRAM_BOT_TOKEN:
                recipients = set(config.TELEGRAM_ADMIN_CHAT_IDS)
                user_tg_id = config.TELEGRAM_USER_CHATS.get(task.user_id)
                if user_tg_id:
                    recipients.add(user_tg_id)

                if recipients:
                    try:
                        tg_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
                        if event == "completed":
                            elapsed_sec = int(task.finished_at - task.started_at) if (task.finished_at and task.started_at) else 0
                            tg_text = (
                                "⚡ <b>PREMIUMIZER: Download abgeschlossen</b>\n\n"
                                f"👤 <b>User:</b> {task.user_name} (<code>{task.user_id}</code>)\n"
                                f"📁 <b>Datei:</b> <code>{task.file_name}</code>\n"
                                f"📦 <b>Größe:</b> {format_bytes(task.file_size)}\n"
                                f"🌐 <b>Hoster:</b> {task.uploader_name.capitalize()}\n"
                                f"⏱️ <b>Dauer:</b> {format_eta(elapsed_sec)}\n\n"
                                f"🔗 <b>Download:</b> {task.download_url or 'Discord Anhang'}\n"
                                f"🔗 <b>Quelle:</b> <code>{task.source[:150]}</code>"
                            )
                        else:
                            tg_text = (
                                "⚠️ <b>PREMIUMIZER: Download fehlgeschlagen</b>\n\n"
                                f"👤 <b>User:</b> {task.user_name} (<code>{task.user_id}</code>)\n"
                                f"❌ <b>Fehler:</b> <code>{task.error_message[:250]}</code>\n"
                                f"🔗 <b>Quelle:</b> <code>{task.source[:150]}</code>"
                            )

                        async with aiohttp.ClientSession() as session:
                            for cid in recipients:
                                try:
                                    await session.post(
                                        tg_url,
                                        json={
                                            "chat_id": cid,
                                            "text": tg_text,
                                            "parse_mode": "HTML",
                                            "disable_web_page_preview": False
                                        },
                                        timeout=aiohttp.ClientTimeout(total=10)
                                    )
                                except Exception as post_err:
                                    logger.warning(f"Failed to send Telegram notification to {cid}: {post_err}")
                    except Exception as tg_err:
                        logger.warning(f"Failed to send Telegram admin notification: {tg_err}")

            # Send DM to requester only if the progress message was NOT already delivered to user's DM
            is_already_dm = bool(task.discord_message and isinstance(task.discord_message.channel, discord.DMChannel))
            if config.DM_NOTIFY_USER and event == "completed" and not task.is_discord_attachment and not is_already_dm:
                try:
                    user_obj = self.bot.get_user(task.user_id)
                    if not user_obj:
                        user_obj = await self.bot.fetch_user(task.user_id)
                    if user_obj:
                        elapsed_sec = int(task.finished_at - task.started_at) if (task.finished_at and task.started_at) else 0
                        duration_str = format_eta(elapsed_sec, lang=task.user_lang)
                        dm_embed = create_success_embed(
                            task_id=task.task_id,
                            user_name=task.user_name,
                            file_name=task.file_name,
                            file_size=task.file_size,
                            download_url=task.download_url,
                            uploader_name=task.uploader_name,
                            duration_str=duration_str,
                            raw_source=task.source,
                            folder_files=task.folder_files if task.is_folder else None,
                            is_discord_attachment=task.is_discord_attachment,
                            lang=task.user_lang
                        )
                        dm_view = None
                        if not task.is_discord_attachment and task.download_url:
                            dm_view = discord.ui.View()
                            dm_view.add_item(discord.ui.Button(
                                label=t("download_btn", lang=task.user_lang, uploader=task.uploader_name.capitalize()),
                                url=task.download_url,
                                style=discord.ButtonStyle.link
                            ))
                        await user_obj.send(
                            content=f"✅ {t('download_complete_msg', lang=task.user_lang, filename=task.file_name)}",
                            embed=dm_embed,
                            view=dm_view
                        )
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to user {task.user_id} (DMs closed).")
                except Exception as dm_err:
                    logger.warning(f"Failed to send DM to user {task.user_id}: {dm_err}")
        except Exception as e:
            logger.warning(f"Failed to send admin notification: {e}")

        # Check account quota and warn admin if low
        try:
            await self._check_account_quota_warnings()
        except Exception:
            pass

    async def _check_account_quota_warnings(self):
        """Checks if Premiumize Fair-Use points or Cloud Space are nearly exhausted and alerts Admin."""
        now = time.time()
        if (now - self.last_quota_warning) < 21600:  # Max once per 6 hours
            return

        try:
            acc_info = await self.pm_client.get_account_info(force_refresh=True)
            limit_used = safe_float(acc_info.get("limit_used"), 0.0)
            space_used = safe_int(acc_info.get("space_used"), 0)

            warning_messages = []
            if limit_used >= 0.80:
                warning_messages.append(
                    f"⚠️ **Fair-Use Warnung:** Punkte sind zu **{limit_used * 100.0:.1f}%** aufgebraucht (nur noch {(1.0 - limit_used) * 100.0:.1f}% verbleibend)!"
                )
            if space_used >= 950 * 1024 * 1024 * 1024:
                warning_messages.append(
                    f"⚠️ **Cloud-Speicher Warnung:** Speicher ist fast voll (**{format_bytes(space_used)}** belegt)!"
                )

            if warning_messages:
                self.last_quota_warning = now
                warn_text = "\n".join(warning_messages)
                logger.warning(f"Quota Alert: {warn_text}")

                # Send Telegram alert
                if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_ADMIN_CHAT_IDS:
                    tg_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
                    tg_text = f"🚨 <b>PREMIUMIZER: Account-Warnung</b>\n\n{warn_text}"
                    async with aiohttp.ClientSession() as session:
                        for cid in config.TELEGRAM_ADMIN_CHAT_IDS:
                            try:
                                await session.post(
                                    tg_url,
                                    json={"chat_id": cid, "text": tg_text, "parse_mode": "HTML"},
                                    timeout=aiohttp.ClientTimeout(total=8)
                                )
                            except Exception:
                                pass

                # Send Discord alert
                if self.bot and config.ADMIN_CHANNEL_ID:
                    ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
                    if ch:
                        embed = discord.Embed(
                            title="🚨 Premiumize Account-Frühwarnung",
                            description=warn_text,
                            color=0xE67E22,
                            timestamp=datetime.datetime.now(datetime.timezone.utc)
                        )
                        await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"Error in _check_account_quota_warnings: {e}")

    async def _update_discord_status(
        self,
        task: DownloadTask,
        status_text: str,
        percent: float,
        details: str = "",
        color: Optional[int] = None
    ):
        """Generates embed and updates discord message if throttle interval passed."""
        now = time.time()
        if (now - task.last_embed_update) < 2.5:
            return

        task.last_embed_update = now
        bar = render_progress_bar(percent)
        chosen_color = color if color is not None else self.PHASE_COLORS.get(task.status, 0x3498DB)
        embed = create_task_embed(
            task_id=task.task_id,
            user_name=task.user_name,
            status_text=status_text,
            phase=task.phase_text,
            file_name=task.file_name,
            progress_bar=bar,
            details=details,
            color=chosen_color,
            is_cached=task.is_cached,
            lang=task.user_lang
        )
        await self._update_discord_message(task, embed=embed)

    async def _update_discord_message(
        self,
        task: DownloadTask,
        embed: discord.Embed,
        view: Optional[discord.ui.View] = None,
        content: Optional[str] = None,
        force: bool = False
    ):
        if not task.discord_message:
            return
        try:
            kwargs = {"embed": embed}
            if view is not None:
                kwargs["view"] = view
            if content is not None:
                kwargs["content"] = content
            await task.discord_message.edit(**kwargs)
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            if e.status == 429:
                logger.warning(f"Discord rate limited on message edit: {e}")
            else:
                logger.warning(f"Failed to edit Discord message for task {task.task_id}: {e}")

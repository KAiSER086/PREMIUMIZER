import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Literal
import logging
import re

from core.task_manager import TaskManager
from core.utils import format_speed, format_eta, render_progress_bar, check_interaction_access
from core.dlc_decrypter import extract_links_from_dlc
from core.i18n import t, get_locale_lang
import config

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'(https?://[^\s<>"]+|magnet:\?xt=urn:[^\s<>"]+)', re.IGNORECASE)

class CancelButtonView(discord.ui.View):
    def __init__(self, task_id: str, task_manager: TaskManager, user_id: int, lang: str = "en"):
        super().__init__(timeout=3600)
        self.task_id = task_id
        self.task_manager = task_manager
        self.user_id = user_id
        self.lang = lang
        self.cancel_button.label = t("cancel_btn_label", lang=lang)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_lang = get_locale_lang(interaction.locale)
        if interaction.user.id != self.user_id and not getattr(interaction.user.guild_permissions, "administrator", False):
            await interaction.response.send_message(t("cancel_not_allowed", lang=user_lang), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        success = await self.task_manager.cancel_task(self.task_id, cancelled_by=interaction.user.display_name)
        if success:
            button.disabled = True
            button.label = t("phase_canceled", lang=user_lang)
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(f"🛑 {t('cancel_btn_clicked', lang=user_lang, task_id=self.task_id)}", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ {t('phase_failed', lang=user_lang)}", ephemeral=True)


class DownloadCog(commands.Cog):
    def __init__(self, bot: commands.Bot, task_manager: TaskManager):
        self.bot = bot
        self.task_manager = task_manager

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-detect dropped URLs, magnet links, .torrent, .nzb, or .dlc files and start downloads."""
        if message.author.bot or not message.guild:
            return

        # Whitelist checks
        if config.ALLOWED_CHANNELS and message.channel.id not in config.ALLOWED_CHANNELS:
            return
        if config.ALLOWED_USERS and message.author.id not in config.ALLOWED_USERS:
            return
        if config.ALLOWED_ROLES:
            user_roles = [r.id for r in getattr(message.author, "roles", [])]
            if not any(rid in config.ALLOWED_ROLES for rid in user_roles):
                return

        # Read file attachments into memory BEFORE deleting message (prevent Discord CDN 404)
        direct_files = []
        for att in message.attachments:
            fn = att.filename.lower()
            if fn.endswith((".torrent", ".nzb")):
                try:
                    data = await att.read()
                    direct_files.append((att.filename, data))
                except Exception as e:
                    logger.error(f"Failed to read attachment {att.filename}: {e}")

        dlc_files = []
        for att in message.attachments:
            if att.filename.lower().endswith(".dlc"):
                try:
                    data = await att.read()
                    dlc_files.append((att.filename, data))
                except Exception as e:
                    logger.error(f"Failed to read DLC attachment {att.filename}: {e}")

        # Gather text links / magnets
        content = message.content.strip()
        text_links = []
        if content and not content.startswith("/"):
            raw_matches = URL_REGEX.findall(content)
            if raw_matches:
                text_links = list(dict.fromkeys(raw_matches))

        # Check if message has anything relevant
        if not direct_files and not dlc_files and not text_links:
            return

        # Now safe to delete the message from the public channel
        try:
            await message.delete()
        except Exception:
            pass

        lang = getattr(config, "BOT_LANGUAGE", "en")

        # Calculate total sources count (files + containers + links)
        total_items = len(direct_files) + len(dlc_files) + len(text_links)

        # If it's a multi-item batch drop, send a summary DM first
        if total_items > 1:
            batch_desc_parts = []
            if direct_files:
                torrent_count = sum(1 for fn, _ in direct_files if fn.lower().endswith(".torrent"))
                nzb_count = sum(1 for fn, _ in direct_files if fn.lower().endswith(".nzb"))
                if torrent_count:
                    batch_desc_parts.append(t("torrent_count", lang=lang, count=torrent_count))
                if nzb_count:
                    batch_desc_parts.append(t("nzb_count", lang=lang, count=nzb_count))
            if dlc_files:
                batch_desc_parts.append(t("dlc_count", lang=lang, count=len(dlc_files)))
            if text_links:
                batch_desc_parts.append(t("links_count", lang=lang, count=len(text_links)))

            batch_embed = discord.Embed(
                title=t("smart_drop_multi_title", lang=lang, count=total_items),
                description=t("smart_drop_multi_desc", lang=lang, items="\n".join(batch_desc_parts)),
                color=0x3498DB
            )
            batch_embed.add_field(name=t("target_dest", lang=lang), value=t("target_auto_val", lang=lang), inline=True)
            batch_embed.add_field(name=t("auto_clean", lang=lang), value=t("yes", lang=lang), inline=True)

            try:
                await message.author.send(content=t("smart_drop_multi_received", lang=lang), embed=batch_embed)
            except discord.Forbidden:
                await message.channel.send(content=t("smart_drop_multi_received_for", lang=lang, user_id=message.author.id), embed=batch_embed)

        # 1. Process all direct attachments (.torrent / .nzb)
        for filename, file_bytes in direct_files:
            try:
                is_nzb = filename.lower().endswith(".nzb")
                type_label = t("nzb_label", lang=lang) if is_nzb else t("torrent_label", lang=lang)

                initial_embed = discord.Embed(
                    title=f"⚡ {type_label} {t('phase_pm_transfer', lang=lang)}",
                    description=f"`{filename}`...",
                    color=0x3498DB
                )
                initial_embed.add_field(name=f"📁 {type_label}", value=f"```{filename}```", inline=False)
                initial_embed.add_field(name=t("target_dest", lang=lang), value=t("target_auto_val", lang=lang), inline=True)
                initial_embed.add_field(name=t("auto_clean", lang=lang), value=t("yes", lang=lang), inline=True)

                try:
                    msg = await message.author.send(content=t("smart_drop_started", lang=lang), embed=initial_embed)
                except discord.Forbidden:
                    msg = await message.channel.send(content=t("smart_drop_started_for", lang=lang, user_id=message.author.id), embed=initial_embed)

                task = await self.task_manager.add_task(
                    user_id=message.author.id,
                    user_name=message.author.display_name,
                    channel_id=message.channel.id,
                    source=f"{type_label}: {filename}",
                    uploader_name="auto",
                    torrent_bytes=file_bytes,
                    torrent_filename=filename,
                    autoclean_pm=True,
                    discord_message=msg,
                    user_lang=lang
                )
                view = CancelButtonView(task.task_id, self.task_manager, message.author.id, lang=lang)
                await msg.edit(view=view)
            except Exception as ex:
                logger.error(f"Failed to process direct file {filename}: {ex}", exc_info=True)

        # 2. Process all DLC container attachments
        for dlc_filename, dlc_bytes in dlc_files:
            try:
                parsing_embed = discord.Embed(
                    title=t("dlc_title", lang=lang),
                    description=t("dlc_decrypting", lang=lang, filename=dlc_filename),
                    color=0x3498DB
                )
                parsing_embed.add_field(name="📁 Container", value=f"```{dlc_filename}```", inline=False)

                try:
                    status_msg = await message.author.send(content=t("dlc_received", lang=lang), embed=parsing_embed)
                except discord.Forbidden:
                    status_msg = await message.channel.send(content=t("dlc_received_for", lang=lang, user_id=message.author.id), embed=parsing_embed)

                try:
                    extracted_links = await extract_links_from_dlc(dlc_bytes, filename=dlc_filename)
                except Exception as dlc_err:
                    err_embed = discord.Embed(
                        title=t("dlc_decrypt_failed_title", lang=lang),
                        description=t("dlc_decrypt_failed_desc", lang=lang, filename=dlc_filename, error=str(dlc_err)[:250]),
                        color=0xE74C3C
                    )
                    await status_msg.edit(content=None, embed=err_embed)
                    continue

                if not extracted_links:
                    err_embed = discord.Embed(
                        title=t("dlc_no_links_title", lang=lang),
                        description=t("dlc_no_links_desc", lang=lang, filename=dlc_filename),
                        color=0xE74C3C
                    )
                    await status_msg.edit(content=None, embed=err_embed)
                    continue

                success_dlc_embed = discord.Embed(
                    title=t("dlc_success_title", lang=lang),
                    description=t("dlc_success_desc", lang=lang, filename=dlc_filename, count=len(extracted_links)),
                    color=0x2ECC71
                )
                preview_links = "\n".join(f"• `{l[:55]}...`" if len(l) > 55 else f"• `{l}`" for l in extracted_links[:5])
                if len(extracted_links) > 5:
                    preview_links += "\n" + t("dlc_more_links", lang=lang, count=len(extracted_links) - 5)
                success_dlc_embed.add_field(name=t("dlc_found_links", lang=lang, count=len(extracted_links)), value=preview_links, inline=False)
                await status_msg.edit(content=None, embed=success_dlc_embed)

                for target_url in extracted_links:
                    dl_embed = discord.Embed(
                        title=t("smart_drop_title", lang=lang),
                        description=f"`{dlc_filename}`:",
                        color=0x3498DB
                    )
                    dl_embed.add_field(name=t("download_link", lang=lang), value=f"```{target_url[:80]}...```" if len(target_url) > 80 else f"```{target_url}```", inline=False)
                    dl_embed.add_field(name=t("target_dest", lang=lang), value=t("target_auto_val", lang=lang), inline=True)
                    dl_embed.add_field(name=t("auto_clean", lang=lang), value=t("yes", lang=lang), inline=True)

                    try:
                        msg = await message.author.send(content=t("smart_drop_started", lang=lang), embed=dl_embed)
                    except discord.Forbidden:
                        msg = await message.channel.send(content=t("smart_drop_started_for", lang=lang, user_id=message.author.id), embed=dl_embed)

                    task = await self.task_manager.add_task(
                        user_id=message.author.id,
                        user_name=message.author.display_name,
                        channel_id=message.channel.id,
                        source=target_url,
                        uploader_name="auto",
                        autoclean_pm=True,
                        discord_message=msg,
                        user_lang=lang
                    )
                    view = CancelButtonView(task.task_id, self.task_manager, message.author.id, lang=lang)
                    await msg.edit(view=view)
            except Exception as ex:
                logger.error(f"Failed to process DLC {dlc_filename}: {ex}", exc_info=True)

        # 3. Process all text links / magnets
        for target_url in text_links:
            try:
                is_magnet = target_url.startswith("magnet:?")
                dl_embed = discord.Embed(
                    title=t("smart_drop_title", lang=lang),
                    description="Link:",
                    color=0x3498DB
                )
                if is_magnet:
                    dl_embed.add_field(name="🧲 Magnet", value=f"```{target_url[:80]}...```" if len(target_url) > 80 else f"```{target_url}```", inline=False)
                else:
                    dl_embed.add_field(name=t("download_link", lang=lang), value=f"```{target_url[:80]}...```" if len(target_url) > 80 else f"```{target_url}```", inline=False)

                dl_embed.add_field(name=t("target_dest", lang=lang), value=t("target_auto_val", lang=lang), inline=True)
                dl_embed.add_field(name=t("auto_clean", lang=lang), value=t("yes", lang=lang), inline=True)

                is_supported, warn_msg = self.task_manager.pm_client.check_hoster_status(target_url, lang=lang)
                if warn_msg:
                    dl_embed.add_field(name=f"⚠️ {t('hoster_label', lang=lang)}", value=warn_msg, inline=False)

                try:
                    msg = await message.author.send(content=t("smart_drop_started", lang=lang), embed=dl_embed)
                except discord.Forbidden:
                    msg = await message.channel.send(content=t("smart_drop_started_for", lang=lang, user_id=message.author.id), embed=dl_embed)

                task = await self.task_manager.add_task(
                    user_id=message.author.id,
                    user_name=message.author.display_name,
                    channel_id=message.channel.id,
                    source=target_url,
                    uploader_name="auto",
                    autoclean_pm=True,
                    discord_message=msg,
                    user_lang=lang
                )
                view = CancelButtonView(task.task_id, self.task_manager, message.author.id, lang=lang)
                await msg.edit(view=view)
            except Exception as ex:
                logger.error(f"Failed to process text link {target_url[:50]}: {ex}", exc_info=True)


    @app_commands.command(name="status", description="Shows active downloads and current transfer progress.")
    async def status(self, interaction: discord.Interaction):
        allowed, err_msg = check_interaction_access(interaction)
        if not allowed:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        lang = get_locale_lang(interaction.locale)
        is_admin = (
            (interaction.guild and interaction.user.id == interaction.guild.owner_id)
            or (config.ALLOWED_USERS and interaction.user.id in config.ALLOWED_USERS)
            or (config.ADMIN_USER_ID and interaction.user.id == config.ADMIN_USER_ID)
            or getattr(interaction.user.guild_permissions, "administrator", False)
        )

        all_active = self.task_manager.get_active_tasks()
        
        if is_admin:
            active = all_active
            title = t("status_title_admin", lang=lang)
        else:
            active = [t_item for t_item in all_active if t_item.user_id == interaction.user.id]
            title = t("status_title_user", lang=lang, user=interaction.user.display_name)

        if not active:
            await interaction.response.send_message(f"ℹ️ {t('status_no_active', lang=lang)}", ephemeral=True)
            return

        embed = discord.Embed(
            title=title,
            description=f"**{len(active)}** task(s):",
            color=0x3498DB
        )

        for task in active[:10]:
            p_bar = render_progress_bar(task.progress_percent)
            if is_admin:
                val = (
                    f"**{t('status_field', lang=lang)}:** {task.phase_text}\n"
                    f"**{t('progress_field', lang=lang)}:** {p_bar}\n"
                    f"**User:** `{task.user_name}` • **{t('target_dest', lang=lang)}:** {task.uploader_name.capitalize()}"
                )
            else:
                val = (
                    f"**{t('status_field', lang=lang)}:** {task.phase_text}\n"
                    f"**{t('progress_field', lang=lang)}:** {p_bar}\n"
                    f"**{t('target_dest', lang=lang)}:** {task.uploader_name.capitalize()}"
                )
            if task.speed > 0:
                val += f"\n**Speed:** `{format_speed(task.speed)}` • **ETA:** `{format_eta(task.eta, lang=lang)}`"
            embed.add_field(
                name=f"🔹 `{task.task_id}` - {task.file_name[:40]}",
                value=val,
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cancel", description="Cancels an active download task by ID.")
    @app_commands.describe(task_id="The Task ID (e.g. pm-a1b2c3)")
    async def cancel(self, interaction: discord.Interaction, task_id: str):
        allowed, err_msg = check_interaction_access(interaction)
        if not allowed:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        lang = get_locale_lang(interaction.locale)
        task = self.task_manager.get_task(task_id.strip())
        if not task:
            await interaction.response.send_message(f"❌ Task `{task_id}` not found.", ephemeral=True)
            return

        if task.user_id != interaction.user.id and not getattr(interaction.user.guild_permissions, "administrator", False):
            await interaction.response.send_message(t("cancel_not_allowed", lang=lang), ephemeral=True)
            return

        success = await self.task_manager.cancel_task(task.task_id, cancelled_by=interaction.user.display_name)
        if success:
            await interaction.response.send_message(f"✅ {t('cancel_btn_clicked', lang=lang, task_id=task.task_id)}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Task `{task.task_id}` could not be canceled.", ephemeral=True)


async def setup(bot: commands.Bot):
    pass

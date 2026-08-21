import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import datetime
from core.premiumize import PremiumizeClient
from core.database import DatabaseManager
from core.utils import format_bytes, render_progress_bar, safe_float, safe_int, check_interaction_access, create_stats_embed, create_history_embed
from core.i18n import t, get_locale_lang
import config

def build_help_embed(lang: Optional[str] = None) -> discord.Embed:
    """Builds the comprehensive help & info embed."""
    target_lang = lang or getattr(config, "BOT_LANGUAGE", "en")
    embed = discord.Embed(
        title=t("help_title", lang=target_lang),
        description=t("bot_description", lang=target_lang),
        color=0x3498DB
    )

    embed.add_field(
        name=t("help_how_to_title", lang=target_lang),
        value=t("help_how_to_desc", lang=target_lang),
        inline=False
    )

    embed.add_field(
        name=t("help_status_title", lang=target_lang),
        value=t("help_status_desc", lang=target_lang),
        inline=False
    )

    embed.add_field(
        name=t("help_features_title", lang=target_lang),
        value=t("help_features_desc", lang=target_lang),
        inline=False
    )

    embed.set_footer(text="PREMIUMIZER • Info & Help")
    return embed


class PermanentHelpView(discord.ui.View):
    """Persistent interactive view for permanent channel help embed."""
    def __init__(self, pm_client: PremiumizeClient, db_manager: DatabaseManager, lang: Optional[str] = None):
        super().__init__(timeout=None)
        self.pm_client = pm_client
        self.db_manager = db_manager
        default_lang = lang or getattr(config, "BOT_LANGUAGE", "en")
        
        self.btn_hosters.label = t("btn_hosters_label", lang=default_lang)
        self.btn_account.label = t("btn_account_label", lang=default_lang)
        self.btn_stats.label = t("btn_stats_label", lang=default_lang)
        self.btn_history.label = t("btn_history_label", lang=default_lang)

    @discord.ui.button(label="Supported Hosters", style=discord.ButtonStyle.primary, custom_id="btn_help_hosters", emoji="🌐")
    async def btn_hosters(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_lang = get_locale_lang(interaction.locale)
        try:
            data = await self.pm_client.get_services_list()
            aliases = data.get("aliases", {})
            directdl = data.get("directdl", [])
            all_hosters = sorted(list(set(list(aliases.keys()) + directdl)))

            embed = discord.Embed(
                title=f"🌐 {t('btn_hosters_label', lang=user_lang)} ({len(all_hosters)})",
                description=f"Premiumize currently supports **{len(all_hosters)} filehosters** and streaming services:",
                color=0x2ECC71
            )

            chunk_size = 14
            chunks = [all_hosters[i:i + chunk_size] for i in range(0, len(all_hosters), chunk_size)]
            for idx, chunk in enumerate(chunks, 1):
                embed.add_field(
                    name=f"📁 Hosters (A-Z) [{idx}]",
                    value="\n".join(f"• `{h}`" for h in chunk),
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            err_msg = str(e).strip() or "Timeout fetching services."
            await interaction.followup.send(f"❌ Error: `{err_msg}`", ephemeral=True)

    @discord.ui.button(label="Account Status", style=discord.ButtonStyle.secondary, custom_id="btn_help_account", emoji="📊")
    async def btn_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_lang = get_locale_lang(interaction.locale)
        try:
            acc_info = await self.pm_client.get_account_info()
            customer_id = str(acc_info.get("customer_id", t("unknown", lang=user_lang)))
            masked_id = f"***{customer_id[-4:]}" if len(customer_id) >= 4 else customer_id
            
            premium_until = acc_info.get("premium_until")
            if premium_until:
                exp_dt = datetime.datetime.fromtimestamp(premium_until, tz=datetime.timezone.utc)
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                days_left = (exp_dt - now_dt).days
                exp_date_str = f"<t:{int(premium_until)}:D>"
                exp_str = t("acc_expires_val", lang=user_lang, days=days_left, date=exp_date_str)
            else:
                exp_str = t("acc_status_inactive", lang=user_lang)

            limit_used = safe_float(acc_info.get("limit_used"), 0.0)
            limit_pct = limit_used * 100.0
            limit_bar = render_progress_bar(limit_pct)
            space_used = safe_int(acc_info.get("space_used"), 0)
            storage_pct = min(100.0, (space_used / (1000 * 1024 * 1024 * 1024)) * 100.0)

            embed = discord.Embed(
                title=t("acc_title", lang=user_lang),
                color=0xF1C40F,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="👤 Customer-ID", value=f"`{masked_id}`", inline=True)
            embed.add_field(name=f"⏳ {t('acc_expires_label', lang=user_lang)}", value=exp_str, inline=True)
            embed.add_field(
                name=f"💾 {t('acc_storage_label', lang=user_lang)}",
                value=t("acc_storage_val", lang=user_lang, used=format_bytes(space_used), percent=f"{storage_pct:.1f}"),
                inline=True
            )
            embed.add_field(
                name=f"📊 {t('acc_fairuse_label', lang=user_lang)}",
                value=f"{limit_bar}\n" + t("acc_fairuse_val", lang=user_lang, used=f"{limit_pct:.1f}", remaining=f"{100.0 - limit_pct:.1f}"),
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            err_msg = str(e).strip() or "Timeout fetching account status."
            await interaction.followup.send(f"❌ Error: `{err_msg}`", ephemeral=True)

    @discord.ui.button(label="Bot Statistics", style=discord.ButtonStyle.secondary, custom_id="btn_help_stats", emoji="📈")
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_lang = get_locale_lang(interaction.locale)
        try:
            stats = await self.db_manager.get_global_stats()
            embed = create_stats_embed(stats, lang=user_lang)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            err_msg = str(e).strip() or "Error calculating statistics."
            await interaction.followup.send(f"❌ Error: `{err_msg}`", ephemeral=True)

    @discord.ui.button(label="My History", style=discord.ButtonStyle.secondary, custom_id="btn_help_history", emoji="📜")
    async def btn_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_lang = get_locale_lang(interaction.locale)
        try:
            is_admin = (
                (interaction.guild and interaction.user.id == interaction.guild.owner_id)
                or (config.ALLOWED_USERS and interaction.user.id in config.ALLOWED_USERS)
                or (config.ADMIN_USER_ID and interaction.user.id == config.ADMIN_USER_ID)
                or getattr(interaction.user.guild_permissions, "administrator", False)
            )
            if is_admin:
                history = await self.db_manager.get_all_history(limit=8)
                embed = create_history_embed("All Users", history, is_admin_global=True, lang=user_lang)
            else:
                history = await self.db_manager.get_user_history(interaction.user.id, limit=6)
                embed = create_history_embed(interaction.user.display_name, history, is_admin_global=False, lang=user_lang)
                
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            err_msg = str(e).strip() or "Error fetching history."
            await interaction.followup.send(f"❌ Error: `{err_msg}`", ephemeral=True)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot, pm_client: PremiumizeClient, db_manager: DatabaseManager):
        self.bot = bot
        self.pm_client = pm_client
        self.db_manager = db_manager

    @app_commands.command(name="posthelp", description="Posts the interactive help board with buttons to this channel (Admin only).")
    @app_commands.describe(
        language="Language for the help board (de = Deutsch, en = English). Default: Auto-detect",
        pin="Pin message at the top of the channel? (Default: True)"
    )
    @app_commands.choices(language=[
        app_commands.Choice(name="Deutsch (German)", value="de"),
        app_commands.Choice(name="English", value="en")
    ])
    @app_commands.default_permissions(administrator=True)
    async def posthelp(
        self,
        interaction: discord.Interaction,
        language: Optional[str] = None,
        pin: Optional[bool] = True
    ):
        allowed, err_msg = check_interaction_access(interaction)
        if not allowed:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        user_lang = get_locale_lang(interaction.locale)
        is_admin_or_owner = (
            (interaction.guild and interaction.user.id == interaction.guild.owner_id)
            or (config.ALLOWED_USERS and interaction.user.id in config.ALLOWED_USERS)
            or (config.ADMIN_USER_ID and interaction.user.id == config.ADMIN_USER_ID)
            or getattr(interaction.user.guild_permissions, "administrator", False)
        )
        if not is_admin_or_owner:
            await interaction.response.send_message(t("admin_only_cmd", lang=user_lang), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        board_lang = language or get_locale_lang(interaction.locale)
        embed = build_help_embed(lang=board_lang)
        view = PermanentHelpView(self.pm_client, self.db_manager, lang=board_lang)

        try:
            msg = await interaction.channel.send(embed=embed, view=view)
            pinned_text = ""
            if pin:
                try:
                    await msg.pin(reason="Permanent help board")
                    pinned_text = " (pinned)"
                except Exception as pin_err:
                    pinned_text = f" (pin failed: {pin_err})"

            success_msg = f"✅ Hilfetafel erfolgreich in <#{interaction.channel_id}> gepostet ({board_lang.upper()}){pinned_text}!" if user_lang == "de" else f"✅ Help board successfully posted in <#{interaction.channel_id}> ({board_lang.upper()}){pinned_text}!"
            await interaction.followup.send(success_msg, ephemeral=True)
        except Exception as ex:
            await interaction.followup.send(f"❌ Error: `{ex}`", ephemeral=True)

    @app_commands.command(name="botlogs", description="Shows recent bot error and activity logs (Admin only).")
    @app_commands.describe(lines="Number of log lines to show (Default: 15, Max: 30)")
    @app_commands.default_permissions(administrator=True)
    async def botlogs(self, interaction: discord.Interaction, lines: Optional[int] = 15):
        allowed, err_msg = check_interaction_access(interaction)
        if not allowed:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        user_lang = get_locale_lang(interaction.locale)
        is_admin_or_owner = (
            (interaction.guild and interaction.user.id == interaction.guild.owner_id)
            or (config.ALLOWED_USERS and interaction.user.id in config.ALLOWED_USERS)
            or (config.ADMIN_USER_ID and interaction.user.id == config.ADMIN_USER_ID)
            or getattr(interaction.user.guild_permissions, "administrator", False)
        )
        if not is_admin_or_owner:
            await interaction.response.send_message(t("admin_only_cmd", lang=user_lang), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        log_path = config.BASE_DIR / "logs" / "bot.log"
        error_path = config.BASE_DIR / "logs" / "errors.log"

        def read_tail(path, n=15):
            if not path.exists():
                return "No log file found."
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines_list = f.readlines()
                    return "".join(lines_list[-n:]).strip() or "Log file is empty."
            except Exception as e:
                return f"Error reading log file: {e}"

        n_lines = min(max(1, lines or 15), 30)
        bot_tail = read_tail(log_path, n_lines)
        error_tail = read_tail(error_path, n_lines)

        embed = discord.Embed(
            title=t("logs_title", lang=user_lang),
            color=0x3498DB,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(
            name=t("logs_bot_field", lang=user_lang),
            value=f"```\n{bot_tail[-950:]}\n```" if bot_tail else "```(empty)```",
            inline=False
        )
        embed.add_field(
            name=t("logs_err_field", lang=user_lang),
            value=f"```\n{error_tail[-950:]}\n```" if error_tail else "```(empty)```",
            inline=False
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    pass

import datetime
import math
from typing import Any, Optional, List, Dict
import discord
from core.i18n import t, get_locale_lang

def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely converts a value to float, handling None or invalid formats."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val: Any, default: int = 0) -> int:
    """Safely converts a value to int, handling None or invalid formats."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def format_bytes(size_bytes: Optional[int | float]) -> str:
    """Formats bytes into human readable string (KB, MB, GB, TB)."""
    size = safe_float(size_bytes, 0.0)
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {units[i]}"

def format_speed(bytes_per_sec: Optional[float]) -> str:
    """Formats transfer speed in B/s, KB/s, MB/s."""
    speed = safe_float(bytes_per_sec, 0.0)
    if speed <= 0:
        return "0 B/s"
    return f"{format_bytes(speed)}/s"

def format_eta(seconds: Optional[int | float], lang: Optional[str] = None) -> str:
    """Formats ETA seconds into human readable duration."""
    if seconds is None:
        return t("unknown", lang=lang)
    sec = safe_int(seconds, -1)
    if sec < 0:
        return t("unknown", lang=lang)
    if sec < 60:
        return f"{sec}s"
    minutes = sec // 60
    rem_seconds = sec % 60
    if minutes < 60:
        return f"{minutes}m {rem_seconds}s"
    hours = minutes // 60
    rem_minutes = minutes % 60
    return f"{hours}h {rem_minutes}m"

def render_progress_bar(percent: Optional[float], length: int = 10) -> str:
    """
    Renders an ASCII/Unicode progress bar.
    percent: 0.0 to 100.0 (or 0.0 to 1.0)
    """
    pct = safe_float(percent, 0.0)
    if pct > 1.0 and pct <= 100.0:
        fraction = pct / 100.0
    else:
        fraction = max(0.0, min(1.0, pct))
        pct = fraction * 100.0

    filled_len = int(round(length * fraction))
    bar = "█" * filled_len + "░" * (length - filled_len)
    return f"`[{bar}]` **{pct:.1f}%**"

def create_task_embed(
    task_id: str,
    user_name: str,
    status_text: str,
    phase: str,
    file_name: str = "...",
    progress_bar: str = "",
    details: str = "",
    color: int = 0x3498DB,
    is_cached: bool = False,
    lang: Optional[str] = None
) -> discord.Embed:
    """Generates a standardized status embed for download/upload tasks."""
    embed = discord.Embed(
        title=t("bot_title", lang=lang),
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    if is_cached:
        embed.description = t("cache_hit_badge", lang=lang)
    
    embed.add_field(name=t("file_package", lang=lang), value=f"```{file_name[:80]}```", inline=False)
    embed.add_field(name=t("status_field", lang=lang), value=f"**{phase}**\n{status_text}", inline=False)
    
    if progress_bar:
        embed.add_field(name=t("progress_field", lang=lang), value=progress_bar, inline=False)
        
    if details:
        embed.add_field(name=t("details_field", lang=lang), value=details, inline=False)
        
    footer_text = f"Task-ID: {task_id} • {user_name}"
    embed.set_footer(text=footer_text)
    return embed

def create_success_embed(
    task_id: str,
    user_name: str,
    file_name: str,
    file_size: int,
    download_url: str,
    uploader_name: str,
    duration_str: str,
    raw_source: str = "",
    folder_files: Optional[List[Dict[str, Any]]] = None,
    is_discord_attachment: bool = False,
    speed_avg_str: Optional[str] = None,
    lang: Optional[str] = None
) -> discord.Embed:
    """Generates a finished/success embed with download link and buttons."""
    embed = discord.Embed(
        title=t("download_complete_title", lang=lang),
        color=0x2ECC71,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    if is_discord_attachment:
        embed.description = f"**{user_name}** • {t('download_complete_msg', lang=lang, filename=file_name)} 📬"
    else:
        embed.description = f"{file_name} • {uploader_name.capitalize()}"
    
    embed.add_field(name=t("file_package", lang=lang), value=f"```{file_name}```", inline=False)
    embed.add_field(name=t("size_label", lang=lang), value=format_bytes(file_size), inline=True)
    embed.add_field(name=t("hoster_label", lang=lang), value=uploader_name.capitalize(), inline=True)
    embed.add_field(name=t("duration_label", lang=lang), value=duration_str, inline=True)
    
    if speed_avg_str:
        embed.add_field(name=t("speed_avg_label", lang=lang), value=speed_avg_str, inline=True)

    if not is_discord_attachment and download_url:
        embed.add_field(
            name=t("download_link", lang=lang),
            value=f"[**{t('download_btn', lang=lang, uploader=uploader_name.capitalize())}**]({download_url})\n`{download_url}`",
            inline=False
        )

    if folder_files:
        files_text = []
        for f in folder_files[:6]:
            fn = f.get("name", "File")[:35]
            fs = format_bytes(f.get("size", 0))
            files_text.append(f"• `{fn}` ({fs})")
        if len(folder_files) > 6:
            files_text.append(t("dlc_more_links", lang=lang, count=len(folder_files) - 6))
        embed.add_field(
            name=f"📦 Files ({len(folder_files)})",
            value="\n".join(files_text),
            inline=False
        )
    
    embed.set_footer(text=f"Task-ID: {task_id} • {user_name}")
    return embed

def create_error_embed(
    task_id: str,
    user_name: str,
    error_message: str,
    file_name: str = "Unknown",
    lang: Optional[str] = None
) -> discord.Embed:
    """Generates an error embed with a reassuring developer notification badge."""
    embed = discord.Embed(
        title=t("download_error_title", lang=lang),
        description=f"```{error_message[:350]}```",
        color=0xE74C3C,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name=t("file_package", lang=lang), value=f"`{file_name[:60]}`", inline=False)
    embed.set_footer(text=f"Task-ID: {task_id} • {user_name}")
    return embed

def create_history_embed(user_name: str, history: List[Dict[str, Any]], is_admin_global: bool = False, lang: Optional[str] = None) -> discord.Embed:
    """Generates an embed showing the user's download history or global admin history."""
    if is_admin_global:
        title = t("history_title_global", lang=lang)
    else:
        title = t("history_title_user", lang=lang, user=user_name)

    embed = discord.Embed(
        title=title,
        color=0x3498DB,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    if not history:
        embed.description = t("history_empty", lang=lang)
        return embed

    embed.description = f"**{len(history)}** items:"
    for item in history:
        fname = item.get("file_name", t("unknown", lang=lang))[:38]
        fsize = format_bytes(item.get("file_size", 0))
        uploader = item.get("uploader", "Hoster")
        link = item.get("download_url", "")
        ts = item.get("timestamp", 0)
        u_name = item.get("user_name", "")
        time_str = f"<t:{ts}:R>" if ts else ""
        
        if is_admin_global and u_name:
            val = f"👤 `{u_name}` • 📦 `{fsize}` • 🌐 `{uploader}`\n⏳ {time_str}"
        else:
            val = f"📦 `{fsize}` • 🌐 `{uploader}` • ⏳ {time_str}"

        if link and link != "Discord Anhang" and link != "Discord Attachment":
            val += f" • 🔗 [Download]({link})"
        elif "Discord" in str(link):
            val += " • 📎 Discord Attachment"
            
        embed.add_field(
            name=f"📁 {fname}",
            value=val,
            inline=False
        )

    embed.set_footer(text=f"PREMIUMIZER • {user_name}")
    return embed

def create_stats_embed(stats: Dict[str, Any], lang: Optional[str] = None) -> discord.Embed:
    """Generates an embed showing global bot stats."""
    embed = discord.Embed(
        title=t("stats_title", lang=lang),
        color=0x2ECC71,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    total_dl = stats.get("total_downloads", 0)
    total_bytes = format_bytes(stats.get("total_bytes", 0))
    users_count = stats.get("unique_users", 0)
    avg_dur = format_eta(stats.get("avg_duration", 0), lang=lang)
    p24_dl = stats.get("past_24h_downloads", 0)
    p24_bytes = format_bytes(stats.get("past_24h_bytes", 0))

    embed.add_field(name=f"📥 {t('stats_total_dl', lang=lang)}", value=f"**{total_dl}**", inline=True)
    embed.add_field(name=f"📦 {t('stats_total_vol', lang=lang)}", value=f"**{total_bytes}**", inline=True)
    embed.add_field(name=f"👥 {t('stats_users', lang=lang)}", value=f"**{users_count}**", inline=True)
    embed.add_field(name=f"⏱️ {t('stats_avg_dur', lang=lang)}", value=f"**{avg_dur}**", inline=True)
    embed.add_field(name=f"⏱️ {t('stats_24h_dl', lang=lang)}", value=f"**{p24_dl}** ({p24_bytes})", inline=True)
    
    uploader_counts = stats.get("uploader_counts", {})
    if uploader_counts:
        top_uploaders = [f"• **{u.capitalize()}:** {cnt}x" for u, cnt in uploader_counts.items()]
        embed.add_field(name=t("stats_top_uploaders", lang=lang), value="\n".join(top_uploaders), inline=True)
    
    embed.set_footer(text="PREMIUMIZER • Live Statistics")
    return embed

def check_interaction_access(interaction: discord.Interaction) -> tuple[bool, str]:
    """
    Validates if interaction is in an allowed channel and from an allowed user/role.
    Returns (True, '') if allowed, or (False, 'error message') if forbidden.
    """
    import config
    lang = get_locale_lang(interaction.locale)
    
    # Check channel whitelist
    if config.ALLOWED_CHANNELS and interaction.channel_id not in config.ALLOWED_CHANNELS:
        ch_mentions = ", ".join(f"<#{cid}>" for cid in config.ALLOWED_CHANNELS)
        return False, f"{t('access_denied_channel', lang=lang)} ({ch_mentions})"

    # Check user whitelist
    if config.ALLOWED_USERS and interaction.user.id not in config.ALLOWED_USERS:
        return False, t("access_denied_user", lang=lang)

    # Check role whitelist
    if config.ALLOWED_ROLES:
        user_roles = [r.id for r in getattr(interaction.user, "roles", [])]
        if not any(rid in config.ALLOWED_ROLES for rid in user_roles):
            return False, t("access_denied_role", lang=lang)

    return True, ""

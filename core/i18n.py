import os
from typing import Optional, Dict, Any
import discord
import config

# Comprehensive translations dictionary
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # App info
        "bot_title": "⚡ Premiumize Downloader & Uploader",
        "bot_description": "Download files and unrestrict filehosters via Premiumize.\nFiles are instantly streamed without wait times to **GoFile** or delivered directly via DM.",
        
        # Smart drop & batch
        "smart_drop_title": "⚡ Smart Drop Started",
        "smart_drop_started": "⚡ Auto-download started:",
        "smart_drop_started_for": "⚡ Auto-download started for <@{user_id}>:",
        "smart_drop_multi_title": "⚡ Smart Drop: Multi-Batch Detected! ({count} Sources)",
        "smart_drop_multi_desc": "The following items were received and are being processed:\n{items}",
        "smart_drop_multi_received": "⚡ Multi-Batch received:",
        "smart_drop_multi_received_for": "⚡ Multi-Batch received for <@{user_id}>:",
        
        # Sources & Items
        "torrent_count": "• **{count}x Torrent(s)**",
        "nzb_count": "• **{count}x Usenet NZB(s)**",
        "dlc_count": "• **{count}x DLC Container(s)**",
        "links_count": "• **{count}x Download Link(s)**",
        "torrent_label": "Torrent",
        "nzb_label": "Usenet NZB",
        "file_package": "📁 File / Package",
        "target_dest": "🌐 Destination",
        "target_auto_val": "Auto (Discord <=10MB / GoFile)",
        "auto_clean": "🧹 Auto-Clean",
        "yes": "Yes",
        "no": "No",
        "unknown": "Unknown",
        
        # DLC Handling
        "dlc_title": "⚡ Smart Drop: DLC Container Detected!",
        "dlc_decrypting": "The DLC file `{filename}` is being decrypted...",
        "dlc_received": "⚡ DLC container received:",
        "dlc_received_for": "⚡ DLC received for <@{user_id}>:",
        "dlc_decrypt_failed_title": "❌ DLC Decryption Failed",
        "dlc_decrypt_failed_desc": "Container `{filename}` could not be decrypted:\n```{error}```",
        "dlc_no_links_title": "❌ No Links Found",
        "dlc_no_links_desc": "No valid download links were found in `{filename}`.",
        "dlc_success_title": "✅ DLC Successfully Decrypted!",
        "dlc_success_desc": "`{filename}`: Found **{count} download links**.\nStarting downloads...",
        "dlc_found_links": "🔗 Found Links ({count})",
        "dlc_more_links": "• *... and {count} more links.*",
        
        # Cache Hit & Status
        "cache_hit_badge": "⚡ **Instant-Cache Hit:** Instantly available without cloud download time!",
        "status_field": "🔄 Status",
        "progress_field": "📊 Progress",
        "details_field": "ℹ️ Details",
        "phase_queued": "Queued",
        "phase_pm_transfer": "Transferring to Premiumize Cloud...",
        "phase_streaming": "Live streaming to {uploader}...",
        "phase_completed": "Completed",
        "phase_failed": "Failed",
        "phase_canceled": "Canceled",
        
        # Status phrases
        "status_in_queue": "In Queue (#{pos}) • Waiting for free slot...",
        "status_pm_transferring": "⏳ Phase 1/2: Cloud Transfer",
        "status_streaming_upload": "🚀 Phase 2/2: Live Streaming",
        
        # Completion & Error
        "download_complete_title": "✅ Download Complete",
        "download_complete_msg": "✅ Your download **{filename}** is ready!",
        "download_btn": "📥 Download ({uploader})",
        "download_link": "🔗 Download Link",
        "download_error_title": "❌ Download Failed",
        "download_canceled_title": "🛑 Download Canceled",
        "duration_label": "⏱️ Duration",
        "size_label": "📦 Size",
        "speed_avg_label": "⚡ Avg Speed",
        "hoster_label": "🌐 Hoster",
        "source_label": "🔗 Source",
        
        # Cancel Button
        "cancel_btn_label": "Cancel",
        "cancel_btn_clicked": "🛑 Download task `{task_id}` was canceled by user.",
        "cancel_not_allowed": "⛔ You can only cancel your own downloads.",
        
        # Hoster Warning
        "hoster_status_warn": "⚠️ The hoster `{domain}` is currently not on the active Premiumize services list. The bot will attempt the download anyway.",
        
        # Slash Commands
        "cmd_status_desc": "Shows active downloads and current transfer progress.",
        "cmd_cancel_desc": "Cancels a running download task.",
        "cmd_posthelp_desc": "Posts a permanent interactive help board with buttons to this channel (Admin only).",
        "cmd_botlogs_desc": "Shows recent bot log and error entries (Admin only).",
        "access_denied_channel": "⛔ This bot cannot be used in this channel.",
        "access_denied_role": "⛔ You do not have the required role to use this bot.",
        "access_denied_user": "⛔ You do not have permission to use this bot.",
        "admin_only_cmd": "⛔ This command is reserved for administrators.",
        
        # Help Board
        "help_title": "⚡ PREMIUMIZER • Highspeed Downloader & Debrid Bot",
        "help_how_to_title": "⚡ How to Start Downloads (Smart Drop)",
        "help_how_to_desc": (
            "Simply post links, torrents, or containers **directly into this channel**:\n"
            "• **Filehoster & Video Links:** Rapidgator, DDownload, 1fichier, Mega, YouTube, etc.\n"
            "• **Torrents & Usenet:** `.torrent` & `.nzb` files (drag & drop) or `magnet:?` links.\n"
            "• **Containers:** `.dlc` files are automatically decrypted.\n"
            "• **📦 Multi-Batch Support:** Post any number of links & files simultaneously in a single message *(e.g., 3 Torrents + 2 NZBs + 4 DLCs + 5 Links)*!\n"
            "• **⚡ Instant-Cache:** Cloud wait time is skipped completely for cached files.\n\n"
            "🔒 *100% Private & Discreet:* Your message is **instantly auto-deleted from the channel**. Live progress and finished download links are delivered **directly to your private DMs**!"
        ),
        "help_status_title": "📊 Status & Management",
        "help_status_desc": (
            "• </status:0> - View live progress of your active downloads.\n"
            "• </cancel:0> `task_id:[ID]` - Cancel a running download.\n\n"
            "🔘 *Use the interactive buttons below for account status, supported hosters, statistics & your history!*"
        ),
        "help_features_title": "🚀 Integrated Features",
        "help_features_desc": (
            "⚡ **Direct Streaming:** Files are streamed directly to GoFile/Pixeldrain.\n"
            "🧹 **Auto-Cleanup:** Temporary local and cloud storage are cleaned automatically.\n"
            "🔒 **User Isolation:** You only see your own downloads and personal history."
        ),
        
        # Interactive Buttons
        "btn_hosters_label": "Supported Hosters",
        "btn_account_label": "Account Status",
        "btn_stats_label": "Bot Statistics",
        "btn_history_label": "My History",
        
        # Account Embed
        "acc_title": "👑 Premiumize Account Status",
        "acc_status_label": "Status",
        "acc_status_active": "✅ Premium Active",
        "acc_status_inactive": "❌ Inactive / Expired",
        "acc_expires_label": "Expires In",
        "acc_expires_val": "{days} Days ({date})",
        "acc_fairuse_label": "Fair-Use Points",
        "acc_fairuse_val": "{used}% used ({remaining}% remaining)",
        "acc_storage_label": "Cloud Storage",
        "acc_storage_val": "{used} / 1,000 GB ({percent}%)",
        
        # Stats Embed
        "stats_title": "📊 Global Download Statistics",
        "stats_total_dl": "Total Downloads",
        "stats_total_vol": "Transferred Volume",
        "stats_users": "Active Users",
        "stats_avg_dur": "Ø Duration",
        "stats_24h_dl": "24h Downloads",
        "stats_24h_vol": "24h Volume",
        "stats_top_uploaders": "🌐 Uploader Distribution",
        
        # History Embed
        "history_title_user": "📜 Download History • {user}",
        "history_title_global": "📜 Global Download History • All Users",
        "history_empty": "No completed downloads found in history.",
        
        # Status Embed
        "status_title_user": "📊 Active Downloads ({user})",
        "status_title_admin": "📊 Active Downloads (Admin: All Users)",
        "status_no_active": "Currently no active downloads in progress.",
        
        # Logs Embed
        "logs_title": "📋 Bot Logs & System Status",
        "logs_bot_field": "📄 General Logs (bot.log)",
        "logs_err_field": "⚠️ Error Logs (errors.log)",
    },
    
    "de": {
        # App info
        "bot_title": "⚡ Premiumize Downloader & Uploader",
        "bot_description": "Lade Dateien über Premiumize herunter und entsperre Filehoster.\nDateien werden in Echtzeit ohne Wartezeit auf **GoFile** bereitgestellt oder direkt per privater Nachricht zugestellt.",
        
        # Smart drop & batch
        "smart_drop_title": "⚡ Smart Drop gestartet",
        "smart_drop_started": "⚡ Auto-Download gestartet:",
        "smart_drop_started_for": "⚡ Auto-Download gestartet für <@{user_id}>:",
        "smart_drop_multi_title": "⚡ Smart Drop: Multi-Batch erkannt! ({count} Quellen)",
        "smart_drop_multi_desc": "Folgende Aufträge wurden empfangen und werden verarbeitet:\n{items}",
        "smart_drop_multi_received": "⚡ Multi-Batch empfangen:",
        "smart_drop_multi_received_for": "⚡ Multi-Batch empfangen für <@{user_id}>:",
        
        # Sources & Items
        "torrent_count": "• **{count}x Torrent(s)**",
        "nzb_count": "• **{count}x Usenet NZB(s)**",
        "dlc_count": "• **{count}x DLC-Container**",
        "links_count": "• **{count}x Download-Link(s)**",
        "torrent_label": "Torrent",
        "nzb_label": "Usenet NZB",
        "file_package": "📁 Datei / Paket",
        "target_dest": "🌐 Ziel",
        "target_auto_val": "Auto (Discord <=10MB / GoFile)",
        "auto_clean": "🧹 Auto-Clean",
        "yes": "Ja",
        "no": "Nein",
        "unknown": "Unbekannt",
        
        # DLC Handling
        "dlc_title": "⚡ Smart Drop: DLC-Container erkannt!",
        "dlc_decrypting": "Die DLC-Datei `{filename}` wird entschlüsselt...",
        "dlc_received": "⚡ DLC-Container empfangen:",
        "dlc_received_for": "⚡ DLC empfangen für <@{user_id}>:",
        "dlc_decrypt_failed_title": "❌ DLC-Entschlüsselung fehlgeschlagen",
        "dlc_decrypt_failed_desc": "Der Container `{filename}` konnte nicht entschlüsselt werden:\n```{error}```",
        "dlc_no_links_title": "❌ Keine Links gefunden",
        "dlc_no_links_desc": "In `{filename}` wurden keine gültigen Download-Links gefunden.",
        "dlc_success_title": "✅ DLC erfolgreich entschlüsselt!",
        "dlc_success_desc": "`{filename}`: **{count} Download-Links** gefunden.\nStarte Downloads...",
        "dlc_found_links": "🔗 Gefundene Links ({count})",
        "dlc_more_links": "• *... und {count} weitere Links.*",
        
        # Cache Hit & Status
        "cache_hit_badge": "⚡ **Instant-Cache Hit:** Sofortige Bereitstellung ohne Cloud-Downloadzeit!",
        "status_field": "🔄 Status",
        "progress_field": "📊 Fortschritt",
        "details_field": "ℹ️ Details",
        "phase_queued": "In Warteschlange",
        "phase_pm_transfer": "Übertragung in Premiumize Cloud...",
        "phase_streaming": "Live-Streaming zu {uploader}...",
        "phase_completed": "Abgeschlossen",
        "phase_failed": "Fehlgeschlagen",
        "phase_canceled": "Abgebrochen",
        
        # Status phrases
        "status_in_queue": "In Warteschlange (#{pos}) • Warte auf freien Slot...",
        "status_pm_transferring": "⏳ Phase 1/2: Cloud Transfer",
        "status_streaming_upload": "🚀 Phase 2/2: Live Streaming",
        
        # Completion & Error
        "download_complete_title": "✅ Download abgeschlossen",
        "download_complete_msg": "✅ Dein Download **{filename}** ist fertig!",
        "download_btn": "📥 Download ({uploader})",
        "download_link": "🔗 Download-Link",
        "download_error_title": "❌ Download fehlgeschlagen",
        "download_canceled_title": "🛑 Download abgebrochen",
        "duration_label": "⏱️ Dauer",
        "size_label": "📦 Größe",
        "speed_avg_label": "⚡ Ø-Speed",
        "hoster_label": "🌐 Hoster",
        "source_label": "🔗 Quelle",
        
        # Cancel Button
        "cancel_btn_label": "Abbrechen",
        "cancel_btn_clicked": "🛑 Download `{task_id}` wurde vom Nutzer abgebrochen.",
        "cancel_not_allowed": "⛔ Du kannst nur deine eigenen Downloads abbrechen.",
        
        # Hoster Warning
        "hoster_status_warn": "⚠️ Der Hoster `{domain}` steht aktuell nicht auf der aktiven Premiumize-Hosterliste. Der Bot versucht den Download trotzdem.",
        
        # Slash Commands
        "cmd_status_desc": "Zeigt laufende Downloads und den aktuellen Fortschritt an.",
        "cmd_cancel_desc": "Bricht einen laufenden Download ab.",
        "cmd_posthelp_desc": "Postet eine dauerhafte interaktive Hilfetafel mit Buttons in diesen Kanal (Nur Admins).",
        "cmd_botlogs_desc": "Zeigt die letzten Fehler- und Status-Logs des Bots an (Nur Admins).",
        "access_denied_channel": "⛔ In diesem Kanal ist der Bot nicht aktiv.",
        "access_denied_role": "⛔ Du hast nicht die erforderliche Rolle zur Nutzung des Bots.",
        "access_denied_user": "⛔ Du hast keine Berechtigung für diesen Bot.",
        "admin_only_cmd": "⛔ Dieser Befehl ist ausschließlich für Administratoren reserviert.",
        
        # Help Board
        "help_title": "⚡ PREMIUMIZER • Highspeed Downloader & Debrid Bot",
        "help_how_to_title": "⚡ So startest du Downloads (Smart Drop)",
        "help_how_to_desc": (
            "Poste einfach Links, Torrents oder Container **direkt als Chat-Nachricht in diesen Kanal**:\n"
            "• **Hoster- & Videolinks:** Rapidgator, DDownload, 1fichier, Mega, YouTube uvm.\n"
            "• **Torrents & Usenet:** `.torrent`- & `.nzb`-Dateien (Drag & Drop) oder `magnet:?`-Links.\n"
            "• **Container:** `.dlc`-Dateien werden automatisch entschlüsselt.\n"
            "• **📦 Multi-Batch Support:** Beliebig viele Links & Dateien gleichzeitig in einem Post *(z.B. 3 Torrents + 2 NZB + 4 DLC + 5 Links)*!\n"
            "• **⚡ Instant-Cache:** Bei bereits gecachten Dateien entfällt die Cloud-Wartezeit komplett.\n\n"
            "🔒 *100% Privat & Diskret:* Deine Nachricht wird **sofort automatisch gelöscht**. Der Live-Fortschritt und die fertige Datei landen **direkt in deinen privaten Direktnachrichten (PM)**!"
        ),
        "help_status_title": "📊 Status & Verwaltung",
        "help_status_desc": (
            "• </status:0> - Zeigt dir den Live-Fortschritt deiner aktiven Downloads an.\n"
            "• </cancel:0> `task_id:[ID]` - Bricht einen laufenden Download ab.\n\n"
            "🔘 *Nutze die interaktiven Buttons unten für Account-Status, Hosterliste, Statistiken & Historie!*"
        ),
        "help_features_title": "🚀 Integrierte Features",
        "help_features_desc": (
            "⚡ **Direkt-Streaming:** Dateien werden ohne Zwischenspeichern zu GoFile/Pixeldrain gestreamt.\n"
            "🧹 **Auto-Cleanup:** Lokaler und Premiumize Cloud-Speicher werden automatisch bereinigt.\n"
            "🔒 **User-Isolation:** Du siehst immer nur deine eigenen Downloads & Historie."
        ),
        
        # Interactive Buttons
        "btn_hosters_label": "Hosterliste",
        "btn_account_label": "Account-Status",
        "btn_stats_label": "Statistiken",
        "btn_history_label": "Meine Historie",
        
        # Account Embed
        "acc_title": "👑 Premiumize Account-Status",
        "acc_status_label": "Status",
        "acc_status_active": "✅ Premium Aktiv",
        "acc_status_inactive": "❌ Inaktiv / Abgelaufen",
        "acc_expires_label": "Verbleibend",
        "acc_expires_val": "{days} Tage ({date})",
        "acc_fairuse_label": "Fair-Use Punkte",
        "acc_fairuse_val": "{used}% verbraucht ({remaining}% frei)",
        "acc_storage_label": "Cloud-Speicher",
        "acc_storage_val": "{used} / 1.000 GB ({percent}%)",
        
        # Stats Embed
        "stats_title": "📊 Globale Bot-Statistiken",
        "stats_total_dl": "Downloads Gesamt",
        "stats_total_vol": "Transferiertes Volumen",
        "stats_users": "Aktive Nutzer",
        "stats_avg_dur": "Ø Download-Dauer",
        "stats_24h_dl": "Downloads (24h)",
        "stats_24h_vol": "Volumen (24h)",
        "stats_top_uploaders": "🌐 Uploader-Verteilung",
        
        # History Embed
        "history_title_user": "📜 Download-Historie • {user}",
        "history_title_global": "📜 Globale Download-Historie • Alle Nutzer",
        "history_empty": "Noch keine abgeschlossenen Downloads in der Historie.",
        
        # Status Embed
        "status_title_user": "📊 Aktive Downloads ({user})",
        "status_title_admin": "📊 Aktive Downloads (Admin: Alle Nutzer)",
        "status_no_active": "Aktuell laufen keine aktiven Downloads.",
        
        # Logs Embed
        "logs_title": "📋 Bot-Logs & Systemstatus",
        "logs_bot_field": "📄 Allgemeine Logs (bot.log)",
        "logs_err_field": "⚠️ Fehler-Logs (errors.log)",
    }
}

def get_locale_lang(locale: Optional[discord.Locale | str] = None) -> str:
    """
    Detects language code ('en' or 'de') from Discord interaction locale or fallback setting.
    """
    if locale is not None:
        loc_str = str(locale).lower().replace("-", "_")
        if loc_str.startswith("de"):
            return "de"
        if loc_str.startswith("en"):
            return "en"
    
    # Fallback to configured default language
    default_lang = getattr(config, "BOT_LANGUAGE", "en").lower()
    return "de" if default_lang.startswith("de") else "en"

def t(key: str, lang: Optional[str] = None, **kwargs) -> str:
    """
    Translates a key into the specified language with keyword substitutions.
    Falls back to English if the translation is missing.
    """
    target_lang = lang or getattr(config, "BOT_LANGUAGE", "en").lower()
    if target_lang not in TRANSLATIONS:
        target_lang = "en"

    # Lookup translation
    lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS["en"])
    text_template = lang_dict.get(key)
    
    if text_template is None:
        # Fallback to English
        text_template = TRANSLATIONS["en"].get(key, f"[{key}]")

    if kwargs:
        try:
            return text_template.format(**kwargs)
        except Exception:
            return text_template

    return text_template

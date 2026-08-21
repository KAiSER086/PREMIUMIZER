import time
import json
import asyncio
import aiohttp
import logging
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List, Tuple

import config
from core.i18n import t

logger = logging.getLogger(__name__)

PREMIUMIZE_API_BASE = "https://www.premiumize.me/api"

class PremiumizeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._services_cache: Optional[Dict[str, Any]] = None
        self._services_cache_time: float = 0.0
        
        self._account_cache: Optional[Dict[str, Any]] = None
        self._account_cache_time: float = 0.0
        
        # Load offline fallback services cache if available
        self._load_fallback_services()

    def _load_fallback_services(self):
        services_file = config.DATA_DIR / "services.json"
        if services_file.exists():
            try:
                with open(services_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("status") == "success":
                        self._services_cache = data
                        self._services_cache_time = time.time()
                        logger.info("Loaded cached Premiumize services list from disk.")
            except Exception as e:
                logger.warning(f"Could not load disk services cache: {e}")

    async def get_account_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetches account status, fair-use points, and cloud storage usage (cached for 30s)."""
        now = time.time()
        if not force_refresh and self._account_cache and (now - self._account_cache_time) < 30:
            return self._account_cache

        url = f"{PREMIUMIZE_API_BASE}/account/info"
        params = {"apikey": self.api_key}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        timeout = aiohttp.ClientTimeout(total=60, sock_connect=15, sock_read=45)

        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    async with session.get(url, params=params) as resp:
                        if resp.status != 200:
                            if attempt == 0 and resp.status >= 500:
                                await asyncio.sleep(2.0)
                                continue
                            raise Exception(f"Premiumize Server antwortete mit HTTP {resp.status}")
                        data = await resp.json()
                        if data.get("status") != "success":
                            raise Exception(data.get("message", "Unbekannter Fehler bei Premiumize"))
                        self._account_cache = data
                        self._account_cache_time = now
                        return data
            except (asyncio.TimeoutError, aiohttp.ClientError) as net_err:
                if attempt == 0:
                    await asyncio.sleep(2.0)
                    continue
                if self._account_cache:
                    return self._account_cache
                raise Exception("Premiumize API antwortet derzeit sehr langsam (Timeout). Bitte in Kürze erneut versuchen.")
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(2.0)
                    continue
                if self._account_cache:
                    return self._account_cache
                raise e

    async def get_services_list(self) -> Dict[str, Any]:
        """Fetches live list of supported file hosters (cached in memory and disk for ultra-fast instant UI response)."""
        now = time.time()
        if self._services_cache and (now - self._services_cache_time) < 3600:
            return self._services_cache

        url = f"{PREMIUMIZE_API_BASE}/services/list"
        params = {"apikey": self.api_key}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        timeout = aiohttp.ClientTimeout(total=45, sock_connect=15, sock_read=30)

        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    async with session.get(url, params=params) as resp:
                        if resp.status != 200:
                            if attempt == 0 and resp.status >= 500:
                                await asyncio.sleep(1.0)
                                continue
                            if self._services_cache:
                                return self._services_cache
                            raise Exception(f"Premiumize Server antwortete mit HTTP {resp.status}")
                        data = await resp.json()
                        if data.get("status") != "success":
                            if self._services_cache:
                                return self._services_cache
                            raise Exception(data.get("message", "Fehler beim Laden der Hosterliste"))
                        
                        self._services_cache = data
                        self._services_cache_time = now
                        
                        # Save to disk cache
                        try:
                            services_file = config.DATA_DIR / "services.json"
                            with open(services_file, "w", encoding="utf-8") as f:
                                json.dump(data, f)
                        except Exception:
                            pass
                            
                        return data
            except Exception:
                if self._services_cache:
                    return self._services_cache
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                if self._services_cache:
                    return self._services_cache
                raise Exception("Premiumize API Zeitüberschreitung beim Laden der Hoster.")

    async def directdl(self, src: str) -> Dict[str, Any]:
        """
        Instantly unrestricts a supported filehoster URL (Rapidgator, DDownload, Mega, 1fichier etc.)
        via Premiumize directdl API endpoint without starting a cloud transfer.
        """
        url = f"{PREMIUMIZE_API_BASE}/transfer/directdl"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        data = {"apikey": self.api_key, "src": src}
        timeout = aiohttp.ClientTimeout(total=45, sock_connect=15, sock_read=35)

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(url, data=data) as resp:
                if resp.status != 200:
                    raise Exception(f"Premiumize API antwortete mit HTTP {resp.status}")
                res_json = await resp.json()
                if res_json.get("status") != "success":
                    err_msg = res_json.get("message", "Link konnte von Premiumize nicht entsperrt werden.")
                    raise Exception(err_msg)
                return res_json

    async def create_transfer(
        self,
        src: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a new transfer on Premiumize.
        Can accept a URL/Magnet string in `src` or raw .torrent file bytes in `file_bytes`.
        """
        url = f"{PREMIUMIZE_API_BASE}/transfer/create"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=60, sock_connect=15, sock_read=45)
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            if file_bytes and filename:
                data = aiohttp.FormData()
                data.add_field("apikey", self.api_key)
                if folder_id:
                    data.add_field("folder_id", folder_id)
                content_type = "application/x-nzb" if filename.lower().endswith(".nzb") else "application/x-bittorrent"
                data.add_field(
                    "file",
                    file_bytes,
                    filename=filename,
                    content_type=content_type
                )
                async with session.post(url, data=data) as resp:
                    res_json = await resp.json()
            else:
                data = {"apikey": self.api_key, "src": src}
                if folder_id:
                    data["folder_id"] = folder_id
                async with session.post(url, data=data) as resp:
                    res_json = await resp.json()

            if res_json.get("status") != "success":
                err_msg = res_json.get("message", "Transfer konnte nicht gestartet werden.")
                raise Exception(f"Premiumize: {err_msg}")
            
            return res_json

    async def get_transfer_list(self) -> List[Dict[str, Any]]:
        """Retrieves list of active/current transfers."""
        url = f"{PREMIUMIZE_API_BASE}/transfer/list"
        params = {"apikey": self.api_key}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=30, sock_connect=15, sock_read=20)
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if data.get("status") != "success":
                    raise Exception(data.get("message", "Fehler beim Abrufen der Transfers."))
                return data.get("transfers", [])

    async def get_transfer_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Finds a specific transfer by ID."""
        transfers = await self.get_transfer_list()
        for t in transfers:
            if t.get("id") == transfer_id:
                return t
        return None

    async def get_item_details(self, file_id: str) -> Dict[str, Any]:
        """Gets direct download link and metadata for a single file."""
        url = f"{PREMIUMIZE_API_BASE}/item/details"
        params = {"apikey": self.api_key, "id": file_id}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=30, sock_connect=15, sock_read=20)
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if data.get("status") != "success":
                    raise Exception(data.get("message", "Datei-Details nicht gefunden."))
                return data

    async def get_folder_contents(self, folder_id: str) -> Dict[str, Any]:
        """Gets files inside a folder."""
        url = f"{PREMIUMIZE_API_BASE}/folder/list"
        params = {"apikey": self.api_key, "id": folder_id}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=30, sock_connect=15, sock_read=20)
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if data.get("status") != "success":
                    raise Exception(data.get("message", "Ordnerinhalt nicht gefunden."))
                return data

    async def generate_zip_url(
        self,
        folder_id: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        transfer_id: Optional[str] = None
    ) -> Optional[str]:
        """Generates a dynamic ZIP download location link for folders or multiple files on Premiumize."""
        url = f"{PREMIUMIZE_API_BASE}/zip/generate"
        data = {"apikey": self.api_key}
        if folder_id:
            data["folders[]"] = folder_id
        elif file_ids:
            for fid in file_ids:
                data["files[]"] = fid
        elif transfer_id:
            data["transfer_id"] = transfer_id
        else:
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=45, sock_connect=15, sock_read=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    res_json = await resp.json()
                    if res_json.get("status") == "success":
                        return res_json.get("location")
                    logger.warning(f"ZIP generation response not successful: {res_json}")
                else:
                    logger.warning(f"ZIP generation returned HTTP {resp.status}")
        return None

    async def delete_transfer(self, transfer_id: str) -> bool:
        """Deletes a transfer task."""
        url = f"{PREMIUMIZE_API_BASE}/transfer/delete"
        data = {"apikey": self.api_key, "id": transfer_id}
        timeout = aiohttp.ClientTimeout(total=20)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data) as resp:
                res_json = await resp.json()
                return res_json.get("status") == "success"

    async def delete_item(self, item_id: str) -> bool:
        """Deletes a file from Premiumize cloud storage."""
        url = f"{PREMIUMIZE_API_BASE}/item/delete"
        data = {"apikey": self.api_key, "id": item_id}
        timeout = aiohttp.ClientTimeout(total=20)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data) as resp:
                res_json = await resp.json()
                return res_json.get("status") == "success"

    async def delete_folder(self, folder_id: str) -> bool:
        """Deletes a folder from Premiumize cloud storage."""
        url = f"{PREMIUMIZE_API_BASE}/folder/delete"
        data = {"apikey": self.api_key, "id": folder_id}
        timeout = aiohttp.ClientTimeout(total=20)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data) as resp:
                res_json = await resp.json()
                return res_json.get("status") == "success"

    async def clear_finished_transfers(self) -> bool:
        """Cleans finished transfer items."""
        url = f"{PREMIUMIZE_API_BASE}/transfer/clearfinished"
        data = {"apikey": self.api_key}
        timeout = aiohttp.ClientTimeout(total=20)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data) as resp:
                res_json = await resp.json()
                return res_json.get("status") == "success"

    async def check_cache(self, items: List[str]) -> Dict[str, Any]:
        """
        Checks if given URLs, hashes, or magnets are instantly cached on Premiumize servers.
        Returns: {"status": "success", "response": [bool, ...], "filename": [...], "filesize": [...]}
        """
        if not items:
            return {"status": "error", "response": []}

        url = f"{PREMIUMIZE_API_BASE}/cache/check"
        params = {"apikey": self.api_key}
        data = [("items[]", item) for item in items]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.post(url, params=params, data=data) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")

        return {"status": "error", "response": [False] * len(items)}

    def check_hoster_status(self, url: str, lang: str = "en") -> Tuple[bool, Optional[str]]:
        """
        Checks if a given URL belongs to a currently supported and active Premiumize file hoster.
        Returns: (is_supported_or_known, optional_warning_text)
        """
        if not url:
            return True, None
        
        # Torrents, Magnets, Usenet, DLC are always supported
        if url.startswith("magnet:?") or url.lower().endswith((".torrent", ".nzb", ".dlc")):
            return True, None

        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if not netloc:
                return True, None

            domain_parts = netloc.split(".")
            root_domain = ".".join(domain_parts[-2:]) if len(domain_parts) >= 2 else netloc

            if not self._services_cache:
                return True, None

            directdl_list = [d.lower() for d in self._services_cache.get("directdl", [])]
            aliases = self._services_cache.get("aliases", {})

            is_in_directdl = any(root_domain in d or d in netloc for d in directdl_list)
            
            is_in_aliases = False
            for main_host, alias_list in aliases.items():
                if any(root_domain in a.lower() or a.lower() in netloc for a in alias_list):
                    is_in_aliases = True
                    break

            if is_in_directdl or is_in_aliases:
                return True, None

            return False, t("hoster_status_warn", lang=lang, domain=root_domain)
        except Exception:
            return True, None

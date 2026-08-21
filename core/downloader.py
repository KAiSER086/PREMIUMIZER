import os
import time
import asyncio
import aiohttp
import aiofiles
import logging
from pathlib import Path
from typing import Optional, Callable, Any, Tuple, AsyncGenerator
import urllib.parse
from contextlib import asynccontextmanager

import config
from core.utils import safe_int, format_bytes

logger = logging.getLogger(__name__)

class HttpDownloader:
    def __init__(self, chunk_size: int = 1024 * 1024):
        self.chunk_size = chunk_size

    def extract_filename_from_url(self, url: str, headers: Optional[dict] = None) -> str:
        """Attempts to extract file name from Content-Disposition header or URL."""
        if headers:
            cd = headers.get("Content-Disposition", "")
            if "filename=" in cd:
                parts = cd.split("filename=")
                if len(parts) > 1:
                    fname = parts[1].split(";")[0].strip("\"' ")
                    if fname:
                        return fname

        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path)
        name = os.path.basename(path)
        if not name or name == "/":
            name = f"download_{int(time.time())}.bin"
        return name

    @asynccontextmanager
    async def open_download_stream(self, url: str, custom_filename: Optional[str] = None):
        """
        Async context manager that connects to the direct download URL.
        Yields: (chunk_generator_func, total_size, file_name)
        """
        timeout = aiohttp.ClientTimeout(total=7200, sock_read=90)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive"
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status not in (200, 206):
                    err_body = await resp.text()
                    logger.error(f"Downloader HTTP Error {resp.status} on URL {url[:80]}: {err_body[:200]}")
                    raise Exception(f"Download-Stream fehlgeschlagen (HTTP {resp.status})")

                total_size = safe_int(resp.headers.get("Content-Length"), 0)
                file_name = custom_filename or self.extract_filename_from_url(url, resp.headers)
                clean_name = "".join(c for c in file_name if c.isalnum() or c in "._- ()[]äöüÄÖÜß+!@#$,~").strip()
                if not clean_name:
                    clean_name = f"file_{int(time.time())}.bin"

                async def chunk_generator(cancel_event: Optional[asyncio.Event] = None) -> AsyncGenerator[bytes, None]:
                    async for chunk in resp.content.iter_chunked(self.chunk_size):
                        if cancel_event and cancel_event.is_set():
                            raise asyncio.CancelledError("Download vom Benutzer abgebrochen.")
                        yield chunk

                yield (chunk_generator, total_size, clean_name)

    async def download_file(
        self,
        url: str,
        destination_dir: Path,
        custom_filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None,
        callback_interval: float = 2.0,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Tuple[Path, int, str]:
        """
        Downloads a file from URL to destination_dir (disk fallback if needed).
        Returns: (file_path, file_size, file_name)
        """
        destination_dir.mkdir(parents=True, exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=7200, sock_read=60)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive"
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status not in (200, 206):
                    err_body = await resp.text()
                    logger.error(f"Downloader HTTP Error {resp.status} on URL {url[:80]}: {err_body[:200]}")
                    raise Exception(f"Download fehlgeschlagen (HTTP {resp.status})")

                total_size = safe_int(resp.headers.get("Content-Length"), 0)
                file_name = custom_filename or self.extract_filename_from_url(url, resp.headers)
                clean_name = "".join(c for c in file_name if c.isalnum() or c in "._- ()[]äöüÄÖÜß+!@#$,~").strip()
                if not clean_name:
                    clean_name = f"file_{int(time.time())}.bin"

                dest_path = destination_dir / clean_name
                if dest_path.exists():
                    dest_path = destination_dir / f"{dest_path.stem}_{int(time.time())}{dest_path.suffix}"

                downloaded_bytes = 0
                start_time = time.time()
                last_cb_time = 0.0

                try:
                    async with aiofiles.open(dest_path, mode="wb") as f:
                        async for chunk in resp.content.iter_chunked(self.chunk_size):
                            if cancel_event and cancel_event.is_set():
                                raise asyncio.CancelledError("Download vom Benutzer abgebrochen.")

                            await f.write(chunk)
                            downloaded_bytes += len(chunk)

                            now = time.time()
                            elapsed = now - start_time
                            if progress_callback and (now - last_cb_time >= callback_interval or (total_size > 0 and downloaded_bytes >= total_size)):
                                speed = downloaded_bytes / elapsed if elapsed > 0 else 0
                                remaining = total_size - downloaded_bytes if total_size > 0 else 0
                                eta = remaining / speed if speed > 0 else 0
                                last_cb_time = now
                                try:
                                    res = progress_callback(downloaded_bytes, total_size, speed, eta)
                                    if asyncio.iscoroutine(res):
                                        await res
                                except Exception as e:
                                    logger.warning(f"Error in download progress callback: {e}")

                except (asyncio.CancelledError, Exception) as err:
                    if dest_path.exists():
                        try:
                            dest_path.unlink()
                        except Exception:
                            pass
                    raise err

                return dest_path, downloaded_bytes, clean_name

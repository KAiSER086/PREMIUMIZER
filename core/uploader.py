import os
import time
import base64
import asyncio
import aiohttp
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable, AsyncGenerator
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class UploadProgressStream:
    """Async file-like wrapper for local file uploads with progress reporting."""
    def __init__(
        self,
        file_path: Path,
        callback: Optional[Callable[[int, int, float, float], Any]] = None,
        chunk_size: int = 1024 * 1024
    ):
        self.file_path = file_path
        self.total_size = os.path.getsize(file_path)
        self.callback = callback
        self.chunk_size = chunk_size
        self.bytes_read = 0
        self.start_time = time.time()
        self.last_callback_time = 0.0

    def __len__(self):
        return self.total_size

    def __iter__(self):
        with open(self.file_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                self.bytes_read += len(chunk)
                now = time.time()
                elapsed = now - self.start_time
                if self.callback and (now - self.last_callback_time >= 2.0 or self.bytes_read >= self.total_size):
                    self.last_callback_time = now
                    speed = self.bytes_read / elapsed if elapsed > 0 else 0
                    remaining = max(0, self.total_size - self.bytes_read)
                    eta = remaining / speed if speed > 0 else 0
                    try:
                        res = self.callback(self.bytes_read, self.total_size, speed, eta)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except Exception as e:
                        logger.warning(f"Error in upload progress callback: {e}")
                yield chunk


class UploadStreamWrapper:
    """Wraps an async chunk generator from a live download stream and computes progress."""
    def __init__(
        self,
        generator: AsyncGenerator[bytes, None],
        total_size: int = 0,
        callback: Optional[Callable[[int, int, float, float], Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ):
        self.generator = generator
        self.total_size = total_size
        self.callback = callback
        self.cancel_event = cancel_event
        self.transferred = 0
        self.start_time = time.time()
        self.last_callback_time = 0.0

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if self.cancel_event and self.cancel_event.is_set():
            raise asyncio.CancelledError("Operation canceled.")

        try:
            chunk = await self.generator.__anext__()
        except StopAsyncIteration:
            raise StopAsyncIteration

        self.transferred += len(chunk)
        now = time.time()
        elapsed = now - self.start_time
        if self.callback and (now - self.last_callback_time >= 2.0 or (self.total_size > 0 and self.transferred >= self.total_size)):
            self.last_callback_time = now
            speed = self.transferred / elapsed if elapsed > 0 else 0
            remaining = max(0, self.total_size - self.transferred) if self.total_size > 0 else 0
            eta = remaining / speed if speed > 0 else 0
            try:
                res = self.callback(self.transferred, self.total_size, speed, eta)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning(f"Error in stream upload progress callback: {e}")

        return chunk


class BaseUploader(ABC):
    name: str = "base"

    @abstractmethod
    async def upload(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def upload_stream(
        self,
        stream_generator: AsyncGenerator[bytes, None],
        total_size: int,
        filename: str,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        pass


class PixeldrainUploader(BaseUploader):
    name = "pixeldrain"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def upload(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None
    ) -> Dict[str, Any]:
        file_name = filename or file_path.name
        file_size = os.path.getsize(file_path)
        url = f"https://pixeldrain.com/api/file/{file_name}"
        
        headers = {}
        if self.api_key:
            auth_str = f":{self.api_key}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        stream = UploadProgressStream(file_path, callback=progress_callback)
        timeout = aiohttp.ClientTimeout(total=7200)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.put(url, data=stream, headers=headers) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise Exception(f"Pixeldrain upload failed (HTTP {resp.status}): {text[:200]}")
                
                res_data = await resp.json()
                file_id = res_data.get("id")
                if not file_id:
                    raise Exception(f"Pixeldrain: No file ID in response: {res_data}")
                
                return {
                    "download_url": f"https://pixeldrain.com/u/{file_id}",
                    "file_name": file_name,
                    "file_size": file_size,
                    "uploader": "Pixeldrain",
                    "file_id": file_id
                }

    async def upload_stream(
        self,
        stream_generator: AsyncGenerator[bytes, None],
        total_size: int,
        filename: str,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        url = f"https://pixeldrain.com/api/file/{filename}"
        headers = {}
        if self.api_key:
            auth_str = f":{self.api_key}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        stream_wrap = UploadStreamWrapper(
            stream_generator,
            total_size=total_size,
            callback=progress_callback,
            cancel_event=cancel_event
        )

        timeout = aiohttp.ClientTimeout(total=7200)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.put(url, data=stream_wrap, headers=headers) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise Exception(f"Pixeldrain stream upload failed (HTTP {resp.status}): {text[:200]}")
                
                res_data = await resp.json()
                file_id = res_data.get("id")
                if not file_id:
                    raise Exception(f"Pixeldrain: No file ID in response: {res_data}")

                return {
                    "download_url": f"https://pixeldrain.com/u/{file_id}",
                    "file_name": filename,
                    "file_size": total_size or stream_wrap.transferred,
                    "uploader": "Pixeldrain",
                    "file_id": file_id
                }


class GoFileUploader(BaseUploader):
    name = "gofile"

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token

    async def get_best_server(self) -> str:
        url = "https://api.gofile.io/servers"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "ok":
                            servers = data.get("data", {}).get("servers", [])
                            if servers:
                                return servers[0].get("name", "store1")
            except Exception as e:
                logger.warning(f"Failed to fetch GoFile server: {e}")
        return "store1"

    async def upload(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None
    ) -> Dict[str, Any]:
        file_name = filename or file_path.name
        file_size = os.path.getsize(file_path)
        server = await self.get_best_server()
        upload_url = f"https://{server}.gofile.io/contents/uploadfile"

        stream = UploadProgressStream(file_path, callback=progress_callback)
        form = aiohttp.FormData()
        if self.api_token:
            form.add_field("token", self.api_token)
        form.add_field("file", stream, filename=file_name)

        timeout = aiohttp.ClientTimeout(total=7200)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(upload_url, data=form) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"GoFile upload failed (HTTP {resp.status}): {text[:200]}")
                
                res_data = await resp.json()
                if res_data.get("status") != "ok":
                    raise Exception(f"GoFile error: {res_data}")
                
                download_page = res_data.get("data", {}).get("downloadPage")
                if not download_page:
                    code = res_data.get("data", {}).get("code")
                    if code:
                        download_page = f"https://gofile.io/d/{code}"
                    else:
                        raise Exception("GoFile: No download link received")

                return {
                    "download_url": download_page,
                    "file_name": file_name,
                    "file_size": file_size,
                    "uploader": "GoFile",
                    "code": res_data.get("data", {}).get("code")
                }

    async def upload_stream(
        self,
        stream_generator: AsyncGenerator[bytes, None],
        total_size: int,
        filename: str,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        server = await self.get_best_server()
        upload_url = f"https://{server}.gofile.io/contents/uploadfile"

        stream_wrap = UploadStreamWrapper(
            stream_generator,
            total_size=total_size,
            callback=progress_callback,
            cancel_event=cancel_event
        )

        form = aiohttp.FormData()
        if self.api_token:
            form.add_field("token", self.api_token)
        form.add_field("file", stream_wrap, filename=filename)

        timeout = aiohttp.ClientTimeout(total=7200)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(upload_url, data=form) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"GoFile stream upload failed (HTTP {resp.status}): {text[:200]}")

                res_data = await resp.json()
                if res_data.get("status") != "ok":
                    raise Exception(f"GoFile error: {res_data}")

                download_page = res_data.get("data", {}).get("downloadPage")
                if not download_page:
                    code = res_data.get("data", {}).get("code")
                    if code:
                        download_page = f"https://gofile.io/d/{code}"
                    else:
                        raise Exception("GoFile: No download link received")

                return {
                    "download_url": download_page,
                    "file_name": filename,
                    "file_size": total_size or stream_wrap.transferred,
                    "uploader": "GoFile",
                    "code": res_data.get("data", {}).get("code")
                }


class LitterboxUploader(BaseUploader):
    name = "litterbox"

    async def upload(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None
    ) -> Dict[str, Any]:
        file_name = filename or file_path.name
        file_size = os.path.getsize(file_path)
        if file_size > 1024 * 1024 * 1024:
            raise Exception("Litterbox supports files up to 1 GB only!")

        url = "https://litterbox.catbox.moe/resources/internals/api.php"
        stream = UploadProgressStream(file_path, callback=progress_callback)

        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field("time", "72h")
        form.add_field("fileToUpload", stream, filename=file_name)

        timeout = aiohttp.ClientTimeout(total=3600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=form) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Litterbox upload failed (HTTP {resp.status}): {text[:200]}")
                
                download_url = (await resp.text()).strip()
                if not download_url.startswith("http"):
                    raise Exception(f"Litterbox error: {download_url}")
                
                return {
                    "download_url": download_url,
                    "file_name": file_name,
                    "file_size": file_size,
                    "uploader": "Litterbox (72h)",
                }

    async def upload_stream(
        self,
        stream_generator: AsyncGenerator[bytes, None],
        total_size: int,
        filename: str,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        if total_size > 1024 * 1024 * 1024:
            raise Exception("Litterbox supports files up to 1 GB only!")

        url = "https://litterbox.catbox.moe/resources/internals/api.php"
        stream_wrap = UploadStreamWrapper(
            stream_generator,
            total_size=total_size,
            callback=progress_callback,
            cancel_event=cancel_event
        )

        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field("time", "72h")
        form.add_field("fileToUpload", stream_wrap, filename=filename)

        timeout = aiohttp.ClientTimeout(total=3600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=form) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Litterbox stream upload failed (HTTP {resp.status}): {text[:200]}")

                download_url = (await resp.text()).strip()
                if not download_url.startswith("http"):
                    raise Exception(f"Litterbox error: {download_url}")

                return {
                    "download_url": download_url,
                    "file_name": filename,
                    "file_size": total_size or stream_wrap.transferred,
                    "uploader": "Litterbox (72h)",
                }


UPLOADER_MAX_SIZES = {
    "litterbox": 1 * 1024 * 1024 * 1024,       # 1 GB
    "pixeldrain": 10 * 1024 * 1024 * 1024,     # 10 GB
    "gofile": 100 * 1024 * 1024 * 1024,       # Unlimited / server limit
}

class UploaderManager:
    def __init__(
        self,
        default_uploader: str = "gofile",
        pixeldrain_key: Optional[str] = None,
        gofile_token: Optional[str] = None
    ):
        self.default_uploader = default_uploader
        self.uploaders: Dict[str, BaseUploader] = {
            "pixeldrain": PixeldrainUploader(api_key=pixeldrain_key),
            "gofile": GoFileUploader(api_token=gofile_token),
            "litterbox": LitterboxUploader(),
        }

    def get_uploader(self, name: Optional[str] = None) -> BaseUploader:
        name = (name or self.default_uploader).lower().strip()
        if name in self.uploaders:
            return self.uploaders[name]
        return self.uploaders.get("gofile", list(self.uploaders.values())[0])

    def get_ordered_candidates(self, file_size: int, preferred_uploader: Optional[str] = None) -> list[str]:
        primary_name = (preferred_uploader or self.default_uploader).lower().strip()
        order = []
        if primary_name in self.uploaders:
            order.append(primary_name)
        for k in ["gofile", "pixeldrain", "litterbox"]:
            if k not in order and k in self.uploaders:
                order.append(k)

        valid_candidates = []
        for uploader_name in order:
            max_limit = UPLOADER_MAX_SIZES.get(uploader_name, float("inf"))
            if file_size <= max_limit or file_size == 0:
                valid_candidates.append(uploader_name)
            else:
                logger.info(f"Skipping uploader '{uploader_name}' (file size: {file_size} exceeds limit {max_limit}).")

        return valid_candidates or ["gofile"]

    async def upload_stream_with_fallback(
        self,
        stream_factory: Callable[[], AsyncGenerator[bytes, None]],
        total_size: int,
        filename: str,
        preferred_uploader: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        """Tries to stream to preferred uploader first, falls back if failed."""
        candidates = self.get_ordered_candidates(total_size, preferred_uploader)
        last_error = None

        for uploader_name in candidates:
            uploader = self.uploaders.get(uploader_name)
            if not uploader:
                continue
            try:
                logger.info(f"Attempting stream upload to {uploader.name} ({filename}, {total_size} bytes)...")
                gen = stream_factory()
                return await uploader.upload_stream(
                    stream_generator=gen,
                    total_size=total_size,
                    filename=filename,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event
                )
            except Exception as e:
                logger.warning(f"Stream upload with {uploader.name} failed: {e}")
                last_error = e

        raise Exception(f"All stream uploads failed. Last error: {last_error}")

    async def upload_with_fallback(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        preferred_uploader: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float, float], Any]] = None
    ) -> Dict[str, Any]:
        file_size = os.path.getsize(file_path) if file_path.exists() else 0
        candidates = self.get_ordered_candidates(file_size, preferred_uploader)
        last_error = None

        for uploader_name in candidates:
            uploader = self.uploaders.get(uploader_name)
            if not uploader:
                continue
            try:
                logger.info(f"Attempting file upload to {uploader.name}...")
                return await uploader.upload(file_path, filename=filename, progress_callback=progress_callback)
            except Exception as e:
                logger.warning(f"File upload with {uploader.name} failed: {e}")
                last_error = e

        raise Exception(f"All file uploads failed. Last error: {last_error}")

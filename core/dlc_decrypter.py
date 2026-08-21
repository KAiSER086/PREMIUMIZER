import re
import json
import logging
import aiohttp
from typing import List

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'https?://[^\s<>"]+', re.IGNORECASE)

async def extract_links_from_dlc(dlc_bytes: bytes, filename: str = "links.dlc") -> List[str]:
    """
    Decrypts a .dlc container file using the dcrypt.it API service.
    Returns a list of extracted URLs.
    """
    if not dlc_bytes:
        raise Exception("DLC file is empty.")

    endpoints = [
        "https://dcrypt.it/decrypt/upload",
        "http://dcrypt.it/decrypt/upload",
    ]

    last_error = None

    for endpoint in endpoints:
        try:
            form = aiohttp.FormData()
            form.add_field(
                "dlcfile",
                dlc_bytes,
                filename=filename or "container.dlc",
                content_type="application/octet-stream"
            )

            timeout = aiohttp.ClientTimeout(total=20, connect=8)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*"
            }

            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.post(endpoint, data=form) as resp:
                    if resp.status != 200:
                        last_error = f"HTTP {resp.status}"
                        continue

                    raw_text = await resp.text()

                    # dcrypt.it wraps JSON in <textarea>...</textarea>
                    json_str = raw_text
                    if "<textarea>" in json_str and "</textarea>" in json_str:
                        json_str = json_str.split("<textarea>")[1].split("</textarea>")[0].strip()

                    try:
                        data = json.loads(json_str)
                    except Exception:
                        # Fallback: Regex scan for URLs in response text
                        urls = URL_REGEX.findall(raw_text)
                        if urls:
                            return list(dict.fromkeys(urls))
                        last_error = "Invalid response from decryption service"
                        continue

                    if "success" in data and "links" in data["success"]:
                        raw_links = data["success"]["links"]
                        clean_links = [link.strip() for link in raw_links if link and isinstance(link, str) and link.strip().startswith("http")]
                        if clean_links:
                            return list(dict.fromkeys(clean_links))
                    
                    if "form_errors" in data:
                        err_detail = str(data["form_errors"])
                        last_error = f"DLC decryption rejected: {err_detail}"
                        continue

        except Exception as e:
            logger.warning(f"Error calling DLC decrypt endpoint {endpoint}: {e}")
            last_error = str(e)

    raise Exception(f"DLC container could not be decrypted ({last_error or 'Service unreachable'}).")

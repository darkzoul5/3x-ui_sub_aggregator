import base64
from asyncio import gather
from binascii import Error as BinasciiError

import httpx
from fastapi import HTTPException

from logger_setup import logger
from settings import SUB_PATH


async def fetch_subscription(
    client: httpx.AsyncClient,
    vless_url: str,
) -> bytes | None:
    """
    Downloads and decodes a base64 subscription config.

    Args:
        client: Shared HTTP client session.
        vless_url: Full subscription URL.
    Returns decoded configuration as bytes, or None if failed.
    """
    try:
        logger.info(f"Fetching subscription from: {vless_url}")
        sub = await client.get(vless_url, timeout=3)
        sub.raise_for_status()
        logger.info(f"Successfully fetched from: {vless_url}")
        return base64.b64decode(sub.text)
    except (BinasciiError, ValueError) as e:
        logger.warning(f"Failed to decode subscription from {vless_url} - {str(e)}")
        return None
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch from {vless_url} - Error: {e.__class__.__name__}: {str(e)}")
        return None


def _build_vless_url(server_url: str, sub_id: str) -> str:
    """Build full VLESS subscription URL from server base URL and sub_id."""
    if not SUB_PATH:
        raise HTTPException(status_code=500, detail="VLESS endpoint is disabled")
    full_url = f"{server_url}/{SUB_PATH}/{sub_id}"
    logger.info(f"Built VLESS URL: {full_url}")
    return full_url


async def merge_all(server_urls: list[str], sub_id: str) -> bytes:
    """
    Merges VLESS/base64 subscriptions from multiple servers.

    Args:
        server_urls: List of base server URLs.
        sub_id: Subscription ID to append to each URL.
    Returns combined and encoded byte data of all valid configurations.
    """
    async with httpx.AsyncClient(verify=False) as client:
        vless_urls = [_build_vless_url(url, sub_id) for url in server_urls]
        logger.info(f"Fetching {len(vless_urls)} VLESS subscriptions")
        fetch_tasks = [
            fetch_subscription(client, vless_url)
            for vless_url in vless_urls
        ]
        results = await gather(*fetch_tasks)
        data = [x for x in results if x is not None]
        logger.info(f"VLESS fetch summary: success={len(data)}, failed={len(vless_urls) - len(data)}")

        if not data:
            logger.error("No subscriptions available")
            raise HTTPException(
                status_code=500,
                detail="There is nothing to return",
            )

        merged = b'\n'.join(data)
        return merged

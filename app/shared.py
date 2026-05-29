import base64
import os
from typing import Any

import httpx
import yaml
from fastapi import HTTPException

from logger_setup import logger
from settings import CONFIG_DIR


async def fetch_links() -> list[str]:
    """
    Fetches server URLs from config file.
    Returns list of base server URLs (trailing slashes removed).
    """
    try:
        if os.getenv('LOCAL_MODE') == 'on':
            config_path = os.path.join(CONFIG_DIR, 'config.txt')
            logger.info(f"Loading server URLs from local config: {config_path}")
            with open(config_path, encoding='utf-8') as file:
                lines = file.readlines()
        else:
            github_token = os.getenv('GITHUB_TOKEN')
            headers = {}
            if github_token:
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3.raw",
                }
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    os.getenv('CONFIG_URL'),
                    headers=headers,
                    timeout=6,
                )
                response.raise_for_status()
                lines = response.text.splitlines()
                logger.info(f"Loaded server URLs from remote config: {os.getenv('CONFIG_URL')}")

        server_urls = [
            line.strip().rstrip('/')
            for line in lines
            if line.strip().startswith('http')
        ]
        logger.info(f"Discovered {len(server_urls)} server URLs from config.txt")
        return server_urls
    except httpx.HTTPStatusError as e:
        logger.critical(f"GitHub fetch error: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail="Config file not found",
        )
    except FileNotFoundError as e:
        logger.critical(e)
        raise e


def _sanitize_sub_id(sub_id: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '_.-' else '_' for ch in sub_id)


def _load_yaml_file(file_path: str) -> Any:
    try:
        with open(file_path, encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except FileNotFoundError:
        raise
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in {file_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Invalid YAML file: {os.path.basename(file_path)}")


def _resolve_config_file(default_name: str, pattern: str, sub_id: str) -> str:
    default_path = os.path.join(CONFIG_DIR, default_name)
    safe_sub_id = _sanitize_sub_id(sub_id)
    if safe_sub_id:
        override_path = os.path.join(CONFIG_DIR, pattern.format(sub_id=safe_sub_id))
        if os.path.exists(override_path):
            return override_path
    return default_path


def _subscription_headers() -> dict[str, str]:
    profile_title_b64 = base64.b64encode(os.getenv('SUB_NAME', 'Aggregated').encode()).decode()
    return {
        "Profile-Title": f"base64:{profile_title_b64}",
        "Profile-Update-Interval": "1",
        "Subscription-Userinfo": "upload=0; download=0; total=0; expire=0",
    }

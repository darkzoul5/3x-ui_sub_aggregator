import os
import httpx
import base64
import re
import yaml
import logging
import logging.handlers
import sys
from asyncio import gather
from binascii import Error as BinasciiError
from typing import Any
from dotenv import load_dotenv
from fastapi import FastAPI, Response, HTTPException


# Load environs first so all env-based configuration is available
load_dotenv()

# Environment configuration
SUB_NAME = os.getenv('SUB_NAME', 'Aggregated')
CONFIG_DIR = os.getenv('CONFIG_DIR', '/app/configs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
path = os.getenv('URL', 'sub').strip('/')
clash_path = os.getenv('CLASH_URL', '/clash').strip('/')

if not path and not clash_path:
    raise RuntimeError("Both URL and CLASH_URL are empty. Configure at least one endpoint path.")


def _resolve_log_level(level_name: str) -> int:
    return getattr(logging, level_name, logging.INFO)


# Initialize FastAPI app
app = FastAPI()


# Logging configuration with rotation every 3 days
logger_file = logging.handlers.TimedRotatingFileHandler(
    filename="py.log",
    when="midnight",
    interval=3,
    backupCount=5   # Keep up to 5 log files
)
logger_console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt='[{asctime}] #{levelname:8} {filename}:{lineno} - {message}',
    style='{'
)
logger_file.setFormatter(formatter)
logger_console.setFormatter(formatter)
logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(_resolve_log_level(LOG_LEVEL))
logger_file.setLevel(_resolve_log_level(LOG_LEVEL))
logger_console.setLevel(_resolve_log_level(LOG_LEVEL))
logger.addHandler(logger_file)
logger.addHandler(logger_console)


# Logging filter to exclude health checks from Uvicorn access logs
class HealthCheckFilter(logging.Filter):
    """Filter out /health endpoint requests from access logs"""
    def filter(self, record):
        return '/health' not in record.getMessage()

# Apply filter to Uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


async def fetch_links() -> list[str]:
    '''
    Fetches server URLs from config file.
    Returns list of base server URLs (trailing slashes removed).
    '''
    try:
        if os.getenv('LOCAL_MODE') == 'on':
            config_path = os.path.join(CONFIG_DIR, 'config.txt')
            logger.info(f"Loading server URLs from local config: {config_path}")
            with open(config_path, encoding='utf-8') as file:
                lines = file.readlines()

        else:
            github_token = os.getenv('GITHUB_TOKEN')
            headers = {}
            # If token is provided, use it for private repo access
            if github_token:
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3.raw"
                }
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    os.getenv('CONFIG_URL'),
                    headers=headers,
                    timeout=6
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
            detail="Config file not found"
        )
    except FileNotFoundError as e:
        logger.critical(e)
        raise e


async def fetch_subscription(
    client: httpx.AsyncClient,
    vless_url: str
) -> bytes | None:
    '''
    Downloads and decodes a base64 subscription config.

    Args:
        client: Shared HTTP client session.
        vless_url: Full subscription URL.
    Returns decoded configuration as bytes, or None if failed.
    '''
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
    '''Build full VLESS subscription URL from server base URL and sub_id.'''
    if not path:
        raise HTTPException(status_code=500, detail="VLESS endpoint is disabled")
    full_url = f"{server_url}/{path}/{sub_id}"
    logger.info(f"Built VLESS URL: {full_url}")
    return full_url


def _build_clash_url(server_url: str, sub_id: str) -> str:
    '''Build full Clash subscription URL from server base URL and sub_id.'''
    if not clash_path:
        raise HTTPException(status_code=500, detail="Clash endpoint is disabled")
    full_url = f"{server_url}/{clash_path}/{sub_id}"
    logger.info(f"Built Clash URL: {full_url}")
    return full_url


async def merge_all(server_urls: list[str], sub_id: str) -> bytes:
    '''
    Merges VLESS/base64 subscriptions from multiple servers.

    Args:
        server_urls: List of base server URLs.
        sub_id: Subscription ID to append to each URL.
    Returns combined and encoded byte data of all valid configurations.
    '''
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
                detail="There is nothing to return"
            )

        merged = b'\n'.join(data)
        return merged


def _sanitize_sub_id(sub_id: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', sub_id)


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
    profile_title_b64 = base64.b64encode(SUB_NAME.encode()).decode()
    return {
        "Profile-Title": f"base64:{profile_title_b64}",
        "Profile-Update-Interval": "1",
        "Subscription-Userinfo": "upload=0; download=0; total=0; expire=0"
    }


def _load_proxy_groups(sub_id: str) -> list[dict[str, Any]]:
    file_path = _resolve_config_file(
        default_name='default-proxy-groups.yaml',
        pattern='proxy-groups-{sub_id}.yaml',
        sub_id=sub_id,
    )
    if not os.path.exists(file_path):
        logger.warning(f"Proxy groups config file is missing: {file_path}")
        return []

    data = _load_yaml_file(file_path)
    groups = data.get('proxy-groups', data) if isinstance(data, (dict, list)) else []
    if not isinstance(groups, list):
        raise HTTPException(status_code=500, detail=f"Invalid proxy groups format in {os.path.basename(file_path)}")

    result = [group for group in groups if isinstance(group, dict) and group.get('name')]
    logger.info(f"Loaded {len(result)} proxy groups from {file_path}")
    return result


def _load_rules(sub_id: str) -> list[str]:
    file_path = _resolve_config_file(
        default_name='default-rules.yaml',
        pattern='rules-{sub_id}.yaml',
        sub_id=sub_id,
    )
    if not os.path.exists(file_path):
        logger.warning(f"Rules config file is missing: {file_path}")
        return []

    data = _load_yaml_file(file_path)
    rules = data.get('rules', data) if isinstance(data, (dict, list)) else []
    if not isinstance(rules, list):
        raise HTTPException(status_code=500, detail=f"Invalid rules format in {os.path.basename(file_path)}")

    result = [rule for rule in rules if isinstance(rule, str) and rule.strip()]
    logger.info(f"Loaded {len(result)} rules from {file_path}")
    return result


def _hydrate_proxy_groups(
    groups: list[dict[str, Any]],
    proxy_names: list[str],
) -> list[dict[str, Any]]:
    hydrated = []
    proxy_set = set(proxy_names)

    for group in groups:
        updated_group = dict(group)
        current = updated_group.get('proxies', [])

        if not current:
            updated_group['proxies'] = proxy_names
        elif isinstance(current, list):
            valid = [name for name in current if isinstance(name, str) and name in proxy_set]
            if len(valid) != len(current):
                logger.warning(f"Group '{updated_group.get('name')}' has unknown proxies and they were pruned")
            updated_group['proxies'] = valid if valid else proxy_names
        else:
            updated_group['proxies'] = proxy_names

        hydrated.append(updated_group)

    return hydrated


def _deduplicate_proxy_names(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    renamed = 0
    deduplicated: list[dict[str, Any]] = []

    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        name = proxy.get('name')
        if not isinstance(name, str) or not name.strip():
            continue

        base_name = name.strip()
        count = seen.get(base_name, 0) + 1
        seen[base_name] = count

        current = dict(proxy)
        if count > 1:
            current['name'] = f"{base_name}_{count}"
            renamed += 1
        deduplicated.append(current)

    if renamed:
        logger.info(f"Renamed {renamed} duplicate proxy names")

    return deduplicated


def _parse_yaml_payload(payload: str) -> dict[str, Any] | None:
    if not payload:
        return None

    try:
        parsed = yaml.safe_load(payload)
        if isinstance(parsed, dict):
            return parsed
    except yaml.YAMLError:
        pass

    try:
        decoded = base64.b64decode(payload).decode('utf-8')
        parsed = yaml.safe_load(decoded)
        if isinstance(parsed, dict):
            return parsed
    except (BinasciiError, ValueError, UnicodeDecodeError, yaml.YAMLError):
        return None

    return None


async def fetch_clash_subscription(
    client: httpx.AsyncClient,
    clash_url: str,
) -> list[dict[str, Any]]:
    try:
        logger.info(f"Fetching clash subscription from: {clash_url}")
        response = await client.get(clash_url, timeout=4)
        response.raise_for_status()
        logger.info(f"Clash response status={response.status_code}, bytes={len(response.text)} from {clash_url}")
        logger.info(f"Clash response preview from {clash_url}: {response.text[:300]!r}")

        parsed = _parse_yaml_payload(response.text)
        if parsed is None:
            logger.warning(f"Invalid clash payload format from {clash_url}")
            return []

        logger.info(f"Clash parsed type from {clash_url}: {type(parsed).__name__}")
        if isinstance(parsed, dict):
            logger.info(f"Clash parsed keys from {clash_url}: {sorted(parsed.keys())}")

        proxies = parsed.get('proxies', [])
        if not isinstance(proxies, list):
            logger.warning(f"No proxy list in clash payload from {clash_url}")
            return []

        valid = [item for item in proxies if isinstance(item, dict) and item.get('name')]
        logger.info(f"Fetched {len(valid)} clash proxies from: {clash_url}")
        if not valid:
            logger.warning(f"Clash payload from {clash_url} had proxies key but no usable proxy entries")
        return valid
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch clash from {clash_url} - Error: {e.__class__.__name__}: {str(e)}")
        return []


async def merge_clash(server_urls: list[str], sub_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(verify=False) as client:
        clash_urls = [_build_clash_url(url, sub_id) for url in server_urls]
        logger.info(f"Fetching {len(clash_urls)} Clash subscriptions")
        tasks = [
            fetch_clash_subscription(client, clash_url)
            for clash_url in clash_urls
        ]
        responses = await gather(*tasks)

    proxies: list[dict[str, Any]] = []
    for items in responses:
        proxies.extend(items)

    logger.info(f"Clash fetch summary: sources={len(clash_urls)}, total_proxies_before_dedupe={len(proxies)}")

    proxies = _deduplicate_proxy_names(proxies)
    if not proxies:
        logger.error("No clash proxies available")
        raise HTTPException(status_code=500, detail="There are no clash proxies to return")

    proxy_names = [proxy['name'] for proxy in proxies]
    groups = _hydrate_proxy_groups(_load_proxy_groups(sub_id), proxy_names)
    rules = _load_rules(sub_id)

    return {
        'proxies': proxies,
        'proxy-groups': groups,
        'rules': rules,
    }


@app.get('/health')
async def health() -> Response:
    '''Health check endpoint'''
    return Response(content='OK', media_type='text/plain', status_code=200)


async def clash(sub_id: str = "") -> Response:
    '''
    API endpoint to aggregate native 3x-ui clash (Mihomo) subscriptions.
    '''
    server_urls = await fetch_links()
    if not server_urls:
        logger.error("No server URLs available for clash endpoint")
        raise HTTPException(status_code=500, detail="There are no server URLs to return")

    clash_doc = await merge_clash(server_urls, sub_id)
    clash_yaml = yaml.safe_dump(clash_doc, sort_keys=False, allow_unicode=True)
    logger.info(
        f"Clash response ready: proxies={len(clash_doc.get('proxies', []))}, "
        f"groups={len(clash_doc.get('proxy-groups', []))}, rules={len(clash_doc.get('rules', []))}"
    )
    return Response(content=clash_yaml, media_type='text/plain', headers=_subscription_headers())


async def main(sub_id: str = "") -> Response:
    '''
    API endpoint to aggregate VLESS/base64 subscriptions.\n
    Args:
        sub_id: Optional subscription ID to append to server URLs.
    Returns a base64-encoded text/plain response containing all valid configurations.
    '''
    server_urls = await fetch_links()
    if not server_urls:
        logger.error("No server URLs available")
        raise HTTPException(status_code=500, detail="There is nothing to return")
    
    result = await merge_all(server_urls, sub_id)
    global_sub = base64.b64encode(result)
    logger.info(f"VLESS response ready: bytes={len(global_sub)}")

    return Response(content=global_sub, media_type='text/plain', headers=_subscription_headers())


if clash_path:
    app.add_api_route(f'/{clash_path}/{{sub_id}}', clash, methods=['GET'])
    app.add_api_route(f'/{clash_path}', clash, methods=['GET'])
else:
    logger.warning("CLASH_URL is empty. Clash endpoint is disabled.")

if path:
    app.add_api_route(f'/{path}/{{sub_id}}', main, methods=['GET'])
    app.add_api_route(f'/{path}', main, methods=['GET'])
else:
    logger.warning("URL is empty. VLESS endpoint is disabled.")

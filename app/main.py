import os
import httpx
import base64
import re
import yaml
import logging
import logging.handlers
from asyncio import gather
from binascii import Error as BinasciiError
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv
from fastapi import FastAPI, Response, HTTPException


# Logging configuration with rotation every 3 days
logger_file = logging.handlers.TimedRotatingFileHandler(
    filename="py.log",
    when="midnight",
    interval=3,
    backupCount=5   # Keep up to 5 log files
)
formatter = logging.Formatter(
    fmt='[{asctime}] #{levelname:8} {filename}:{lineno} - {message}',
    style='{'
)
logger_file.setFormatter(formatter)
logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(logging.INFO)
logger.addHandler(logger_file)


# Logging filter to exclude health checks from Uvicorn access logs
class HealthCheckFilter(logging.Filter):
    """Filter out /health endpoint requests from access logs"""
    def filter(self, record):
        return '/health' not in record.getMessage()

# Apply filter to Uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


# Initialize FastAPI app
app = FastAPI()

# Load environs
load_dotenv()

# Environment configuration
SUB_NAME = os.getenv('SUB_NAME', 'Aggregated')
CONFIG_DIR = os.getenv('CONFIG_DIR', '/app/configs')
path = os.getenv('URL', 'sub').strip('/')
clash_path = os.getenv('CLASH_URL', '/clash').strip('/')

async def fetch_links() -> tuple[list[str], list[str]]:
    '''
    Fetches the configuration source file from GitHub or local .txt file.\n
    Returns a tuple of two lists:
        - HTTP subscription links
        - Direct vless configuration links
    '''
    try:
        if os.getenv('LOCAL_MODE') == 'on':
            config_path = os.path.join(CONFIG_DIR, 'config.txt')
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
            
        sub_links = [
            line.strip()
            for line in lines
            if line.strip().startswith('http')
        ]
        vless_links = [
            line.strip()
            for line in lines
            if line.strip().startswith('vless://')
        ]
            
        return sub_links, vless_links
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
    sub_link: str,
    sub_id: str
) -> bytes | None:
    '''
    Downloads and decodes a base64 subscription config
    using the provided sub_id.\n
    Args:
        client: Shared HTTP client session.
        sub_link: Base URL to the subscription service.
        sub_id: Unique identifier for the subscription.
    Returns decoded configuration as bytes, or None if failed.
    '''
    try:
        full_url = f'{sub_link}{sub_id}'
        logger.info(f"Fetching subscription from: {full_url}")
        sub = await client.get(full_url, timeout=3)
        sub.raise_for_status()
        logger.info(f"Successfully fetched from: {sub_link}")
        return base64.b64decode(sub.text)
    except (BinasciiError, ValueError) as e:
        logger.warning(f"Failed to decode subscription from {sub_link}{sub_id} - {str(e)}")
        return None
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch from {sub_link}{sub_id} - Error: {e.__class__.__name__}: {str(e)}")
        return None


async def merge_all(sub_links: list[str], vless_links: list[str], sub_id: str) -> bytes:
    '''
    Merges both 3x-ui subscriptions and direct VLESS links into
    a single byte stream.\n
    Args:
        sub_links: List of HTTP-based subscription links.
        vless_links: List of direct VLESS configuration strings.
        sub_id: Subscription ID to append to each HTTP link.
    Returns combined and encoded byte data of all valid configurations.
    '''
    async with httpx.AsyncClient(verify=False) as client:
        decoded_subs = [
            fetch_subscription(client, sub_url, sub_id) 
            for sub_url in sub_links
        ]
        tmp = await gather(*decoded_subs)
        data = [x for x in tmp if x is not None]
        
        # If there is no configs at all
        if not data and not vless_links:
            logger.error("No subscriptions or configurations available")
            raise HTTPException(
                status_code=500,
                detail="There is nothing to return"
            )
        elif not data:
            logger.warning("No subscriptions available")

        encoded_vless_links = [link.encode() for link in vless_links]
        merged_subs = b''.join(data)
        merged_configs = b'\n'.join(encoded_vless_links)

        return merged_subs + merged_configs


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


def _replace_path_segment(original_path: str, source_segment: str, target_segment: str) -> str:
    src = source_segment.strip('/')
    dst = target_segment.strip('/')
    if not dst:
        dst = 'clash'

    parts = [part for part in original_path.split('/') if part]
    for idx in range(len(parts) - 1, -1, -1):
        if parts[idx] == src:
            parts[idx] = dst
            break
    else:
        parts = [dst]

    return '/' + '/'.join(parts) + '/'


def _build_clash_base_url(sub_link: str) -> str:
    parsed = urlsplit(sub_link)
    new_path = _replace_path_segment(parsed.path, path, clash_path)
    return urlunsplit((parsed.scheme, parsed.netloc, new_path, '', ''))


def _build_clash_sources(sub_links: list[str]) -> list[str]:
    return [_build_clash_base_url(link) for link in sub_links]


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
    sub_link: str,
    sub_id: str,
) -> list[dict[str, Any]]:
    full_url = f'{sub_link}{sub_id}'
    try:
        logger.info(f"Fetching clash subscription from: {full_url}")
        response = await client.get(full_url, timeout=4)
        response.raise_for_status()

        parsed = _parse_yaml_payload(response.text)
        if parsed is None:
            logger.warning(f"Invalid clash payload format from {full_url}")
            return []

        proxies = parsed.get('proxies', [])
        if not isinstance(proxies, list):
            logger.warning(f"No proxy list in clash payload from {full_url}")
            return []

        valid = [item for item in proxies if isinstance(item, dict) and item.get('name')]
        logger.info(f"Fetched {len(valid)} clash proxies from: {full_url}")
        return valid
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch clash from {full_url} - Error: {e.__class__.__name__}: {str(e)}")
        return []


async def merge_clash(sub_links: list[str], sub_id: str) -> dict[str, Any]:
    clash_sources = _build_clash_sources(sub_links)

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [
            fetch_clash_subscription(client, sub_url, sub_id)
            for sub_url in clash_sources
        ]
        responses = await gather(*tasks)

    proxies: list[dict[str, Any]] = []
    for items in responses:
        proxies.extend(items)

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


@app.get(f'/{clash_path}/{{sub_id}}')
@app.get(f'/{clash_path}')
async def clash(sub_id: str = "") -> Response:
    '''
    API endpoint to aggregate native 3x-ui clash (Mihomo) subscriptions.
    '''
    sub_links, _ = await fetch_links()
    if not sub_links:
        logger.error("No subscription links available for clash endpoint")
        raise HTTPException(status_code=500, detail="There are no subscription links to return")

    clash_doc = await merge_clash(sub_links, sub_id)
    clash_yaml = yaml.safe_dump(clash_doc, sort_keys=False, allow_unicode=True)
    return Response(content=clash_yaml, media_type='text/plain', headers=_subscription_headers())


@app.get(f'/{path}/{{sub_id}}')
@app.get(f'/{path}')
async def main(sub_id: str = "") -> Response:
    '''
    API endpoint to encode combined configurations.\n
    Args:
        sub_id: Optional subscription ID (used for HTTP-based configs).
    Returns a base64-encoded text/plain response containing all valid configurations.
    '''
    sub_links, vless_links = await fetch_links()
    if not sub_links and not vless_links:
        logger.error("No subscriptions or configurations available")
        raise HTTPException(status_code=500, detail="There is nothing to return")
    
    result = await merge_all(sub_links, vless_links, sub_id)
    # Rename profiles to match the configured profile name
    global_sub = base64.b64encode(result)

    return Response(content=global_sub, media_type='text/plain', headers=_subscription_headers())

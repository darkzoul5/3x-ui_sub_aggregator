import base64
import os
from asyncio import gather
from binascii import Error as BinasciiError
from typing import Any

import httpx
import yaml
from fastapi import HTTPException

from logger_setup import logger
from settings import clash_path
from shared import _load_yaml_file, _resolve_config_file


def _build_clash_url(server_url: str, sub_id: str) -> str:
    """Build full Clash subscription URL from server base URL and sub_id."""
    if not clash_path:
        raise HTTPException(status_code=500, detail="Clash endpoint is disabled")
    full_url = f"{server_url}/{clash_path}/{sub_id}"
    logger.info(f"Built Clash URL: {full_url}")
    return full_url


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

    for group in groups:
        updated_group = dict(group)
        current = updated_group.get('proxies', [])

        if not current:
            updated_group['proxies'] = list(proxy_names)
        elif isinstance(current, list):
            updated_group['proxies'] = [name for name in current if isinstance(name, str)]
        else:
            logger.warning(
                f"Group '{updated_group.get('name')}' has invalid 'proxies' type; using all aggregated proxies"
            )
            updated_group['proxies'] = list(proxy_names)

        hydrated.append(updated_group)

    return hydrated


def _strip_email_from_names(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Strip email suffix from proxy names.
    Pattern: inbound-email -> inbound
    """
    stripped = []
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        current = dict(proxy)
        name = current.get('name')
        if isinstance(name, str) and '-' in name:
            clean_name = name.split('-', 1)[0].strip()
            if clean_name:
                current['name'] = clean_name
        stripped.append(current)
    return stripped


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

    proxies = _strip_email_from_names(proxies)
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

import base64
import os
import re
from asyncio import gather
from binascii import Error as BinasciiError
from collections import OrderedDict
from typing import Any

import httpx
import yaml
from fastapi import HTTPException

from logger_setup import logger
from settings import CLASH_PATH
from shared import _load_yaml_file, _resolve_config_file


_KNOWN_GROUP_SUFFIXES = {
    'raw',
    'xhttp',
    'http',
    'https',
    'ws',
    'grpc',
    'h2',
    'h3',
    'tcp',
    'tls',
}


def _looks_like_user_suffix(segment: str) -> bool:
    """Heuristic for trailing user/email labels appended by the panel."""
    cleaned = segment.strip()
    if not cleaned:
        return False
    if cleaned.casefold() in _KNOWN_GROUP_SUFFIXES or cleaned.isdigit():
        return False
    return '_' in cleaned or '@' in cleaned


def _build_clash_url(server_url: str, sub_id: str) -> str:
    """Build full Clash subscription URL from server base URL and sub_id."""
    if not CLASH_PATH:
        raise HTTPException(status_code=500, detail="Clash endpoint is disabled")
    full_url = f"{server_url}/{CLASH_PATH}/{sub_id}"
    logger.info(f"Built Clash URL: {full_url}")
    return full_url


def _load_proxy_groups(sub_id: str) -> list[dict[str, Any]] | None:
    file_path = _resolve_config_file(
        default_name='default-proxy-groups.yaml',
        pattern='proxy-groups-{sub_id}.yaml',
        sub_id=sub_id,
    )
    if not os.path.exists(file_path):
        logger.info(f"Proxy groups config file is missing: {file_path}")
        return None

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


def _strip_email_from_names(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize panel-appended user labels and transport-like suffixes from proxy names.

    Examples:
    - LV-RAW-dark_zoul -> LV
    - SW1-RAW-443-dark_zoul -> SW1
    - Sweden 2 -> Sweden 2
    """
    stripped = []
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        current = dict(proxy)
        name = current.get('name')
        if isinstance(name, str):
            clean_name = name.strip()
            if '-' in clean_name:
                prefix, suffix = clean_name.rsplit('-', 1)
                if _looks_like_user_suffix(suffix):
                    clean_name = prefix

            clean_name = re.sub(r'(?:_\d+)+$', '', clean_name)
            parts = re.split(r'\s*-\s*', clean_name)

            while len(parts) > 1:
                tail = parts[-1].strip()
                if tail.isdigit() or tail.casefold() in _KNOWN_GROUP_SUFFIXES:
                    parts.pop()
                    continue
                break

            normalized = '-'.join(part.strip() for part in parts if part.strip()).strip()
            if normalized:
                current['name'] = normalized
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


def _normalize_proxy_group_name(name: str) -> str:
    """
    Derive a common base name for a proxy group.

    Examples:
    - LV-RAW -> LV
    - SW1-RAW-443 -> SW1
    - Sweden 2 -> Sweden 2
    """
    normalized = re.sub(r'\s+', ' ', name).strip()
    normalized = re.sub(r'(?:_\d+)+$', '', normalized).strip()
    return normalized or name.strip()


def _generate_proxy_groups(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue

        name = proxy.get('name')
        if not isinstance(name, str) or not name.strip():
            continue

        display_name = _normalize_proxy_group_name(name)
        group_key = display_name.casefold()

        if group_key not in grouped:
            grouped[group_key] = {
                'name': display_name,
                'type': 'fallback',
                'proxies': [],
            }

        grouped[group_key]['proxies'].append(name)

    generated_groups = list(grouped.values())
    if not generated_groups:
        return []

    root_group_name = 'Proxy'
    if any(group['name'].casefold() == root_group_name.casefold() for group in generated_groups):
        root_group_name = 'Auto'

    root_group = {
        'name': root_group_name,
        'type': 'select',
        'proxies': [group['name'] for group in generated_groups] + ['DIRECT'],
    }

    return [root_group, *generated_groups]


def build_clash_document(
    proxies: list[dict[str, Any]],
    sub_id: str,
) -> dict[str, Any]:
    if not proxies:
        logger.error("No clash proxies available")
        raise HTTPException(status_code=500, detail="There are no clash proxies to return")

    manual_groups = _load_proxy_groups(sub_id)
    if manual_groups is not None:
        groups = manual_groups
        logger.info(f"Using manual proxy groups from config for sub_id={sub_id!r}")
    else:
        groups = _generate_proxy_groups(proxies)
        logger.info(f"Auto-generated {len(groups)} proxy groups from {len(proxies)} proxies")

    rules = _load_rules(sub_id)

    return {
        'proxies': proxies,
        'proxy-groups': groups,
        'rules': rules,
    }


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
    return build_clash_document(proxies, sub_id)

from urllib.parse import parse_qs, unquote, urlparse

from fastapi import HTTPException

from clash import _deduplicate_proxy_names, build_clash_document
from logger_setup import logger
from vless import merge_all


def _first_query_value(params: dict[str, list[str]], key: str, default: str = "") -> str:
    values = params.get(key)
    if not values:
        return default
    return values[0]


def _query_flag(params: dict[str, list[str]], key: str) -> bool:
    value = _first_query_value(params, key, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _parse_vless_line(line: str) -> dict | None:
    if not line.startswith("vless://"):
        return None

    parsed = urlparse(line)
    if parsed.scheme.lower() != "vless":
        return None

    uuid = parsed.username
    host = parsed.hostname
    port = parsed.port
    if not uuid or not host or not port:
        return None

    query = parse_qs(parsed.query, keep_blank_values=True)
    network = _first_query_value(query, "type", "tcp").strip().lower() or "tcp"
    security = _first_query_value(query, "security", "").strip().lower()
    name = unquote(parsed.fragment).strip() if parsed.fragment else host
    if not name:
        name = host

    proxy: dict = {
        "name": name,
        "type": "vless",
        "server": host,
        "port": port,
        "uuid": uuid,
        "udp": True,
        "network": network,
    }

    if _query_flag(query, "allowInsecure") or _query_flag(query, "skip-cert-verify"):
        proxy["skip-cert-verify"] = True

    servername = _first_query_value(query, "sni", _first_query_value(query, "host", host)).strip()
    if servername:
        proxy["servername"] = servername

    flow = _first_query_value(query, "flow", "")
    if flow:
        proxy["flow"] = flow

    fp = _first_query_value(query, "fp", "")
    if fp:
        proxy["client-fingerprint"] = fp

    alpn = _first_query_value(query, "alpn", "")
    if alpn:
        proxy["alpn"] = [item.strip() for item in alpn.split(",") if item.strip()]

    if security in {"tls", "reality"}:
        proxy["tls"] = True

    if network == "ws":
        ws_opts: dict[str, object] = {}
        path = _first_query_value(query, "path", "/")
        if path:
            ws_opts["path"] = path
        ws_host = _first_query_value(query, "host", "")
        if ws_host:
            ws_opts["headers"] = {"Host": ws_host}
        if ws_opts:
            proxy["ws-opts"] = ws_opts
    elif network == "grpc":
        grpc_service = _first_query_value(query, "serviceName", _first_query_value(query, "service_name", ""))
        if grpc_service:
            proxy["grpc-opts"] = {"grpc-service-name": grpc_service}
    elif network == "h2":
        h2_opts: dict[str, object] = {}
        path = _first_query_value(query, "path", "/")
        if path:
            h2_opts["path"] = path
        h2_host = _first_query_value(query, "host", "")
        if h2_host:
            h2_opts["host"] = [h2_host]
        if h2_opts:
            proxy["h2-opts"] = h2_opts

    if security == "reality":
        reality_opts: dict[str, object] = {}
        public_key = _first_query_value(query, "pbk", "")
        short_id = _first_query_value(query, "sid", "")
        spider_x = _first_query_value(query, "spx", "")
        if public_key:
            reality_opts["public-key"] = public_key
        if short_id:
            reality_opts["short-id"] = short_id
        if spider_x:
            reality_opts["spider-x"] = spider_x
        if reality_opts:
            proxy["reality-opts"] = reality_opts

    return proxy


def _parse_vless_payload(payload: str) -> list[dict]:
    proxies: list[dict] = []

    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        proxy = _parse_vless_line(line)
        if proxy is None:
            logger.warning(f"Skipping unsupported VLESS line: {line[:120]!r}")
            continue

        proxies.append(proxy)

    return proxies


async def merge_vless_to_clash(server_urls: list[str], sub_id: str) -> dict:
    merged = await merge_all(server_urls, sub_id)
    payload = merged.decode("utf-8", errors="ignore")
    proxies = _parse_vless_payload(payload)
    proxies = _deduplicate_proxy_names(proxies)

    if not proxies:
        raise HTTPException(status_code=500, detail="There are no VLESS proxies to convert")

    logger.info(f"Converted {len(proxies)} VLESS proxies to Clash format")
    return build_clash_document(proxies, sub_id)

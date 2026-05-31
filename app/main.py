import base64

from fastapi import FastAPI, Response, HTTPException

from clash import merge_clash
from logger_setup import logger
from settings import APP_VERSION, CONFIG_DIR, SUB_NAME, SUB_PATH, CLASH_PATH
from shared import fetch_links, _subscription_headers
from clash_from_vless import merge_vless_to_clash
from vless import merge_all
import yaml


app = FastAPI()

@app.on_event("startup")
async def startup_banner() -> None:
    logger.info("Starting 3x-ui aggregator %s", APP_VERSION)
    logger.info("Subscription name: %s", SUB_NAME)
    logger.info("Config directory: %s", CONFIG_DIR)
    logger.info("VLESS aggregation endpoint: %s", f"/{SUB_PATH}" if SUB_PATH else "<disabled>")
    logger.info("VLESS-to-Clash endpoint: %s", f"/{SUB_PATH}/clash" if SUB_PATH else "<disabled>")
    logger.info("Native Clash endpoint: %s", f"/{CLASH_PATH}" if CLASH_PATH else "<disabled>")

@app.get('/health')
async def health() -> Response:
    """Health check endpoint."""
    return Response(content='OK', media_type='text/plain', status_code=200)


async def clash(sub_id: str = "") -> Response:
    """
    API endpoint to aggregate native 3x-ui clash (Mihomo) subscriptions.
    """
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


async def clash_from_vless(sub_id: str = "") -> Response:
    """
    API endpoint to convert aggregated VLESS subscriptions into Clash format.
    """
    server_urls = await fetch_links()
    if not server_urls:
        logger.error("No server URLs available for clash-from-vless endpoint")
        raise HTTPException(status_code=500, detail="There are no server URLs to return")

    clash_doc = await merge_vless_to_clash(server_urls, sub_id)
    clash_yaml = yaml.safe_dump(clash_doc, sort_keys=False, allow_unicode=True)
    logger.info(
        f"VLESS-to-Clash response ready: proxies={len(clash_doc.get('proxies', []))}, "
        f"groups={len(clash_doc.get('proxy-groups', []))}, rules={len(clash_doc.get('rules', []))}"
    )
    return Response(content=clash_yaml, media_type='text/plain', headers=_subscription_headers())


async def main(sub_id: str = "") -> Response:
    """
    API endpoint to aggregate VLESS/base64 subscriptions.
    """
    server_urls = await fetch_links()
    if not server_urls:
        logger.error("No server URLs available")
        raise HTTPException(status_code=500, detail="There is nothing to return")

    result = await merge_all(server_urls, sub_id)
    global_sub = base64.b64encode(result)
    logger.info(f"VLESS response ready: bytes={len(global_sub)}")

    return Response(content=global_sub, media_type='text/plain', headers=_subscription_headers())


if SUB_PATH:
    app.add_api_route(f'/{SUB_PATH}/clash/{{sub_id}}', clash_from_vless, methods=['GET'])
    app.add_api_route(f'/{SUB_PATH}/clash', clash_from_vless, methods=['GET'])
    app.add_api_route(f'/{SUB_PATH}/{{sub_id}}', main, methods=['GET'])
    app.add_api_route(f'/{SUB_PATH}', main, methods=['GET'])
else:
    logger.warning("SUB_PATH is empty. VLESS aggregation and VLESS-to-Clash endpoints are disabled.")

if CLASH_PATH:
    app.add_api_route(f'/{CLASH_PATH}/{{sub_id}}', clash, methods=['GET'])
    app.add_api_route(f'/{CLASH_PATH}', clash, methods=['GET'])
else:
    logger.warning("CLASH_PATH is empty. Native Clash endpoint is disabled.")

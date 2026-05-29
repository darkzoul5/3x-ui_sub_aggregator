import base64

from fastapi import FastAPI, Response, HTTPException

from clash import merge_clash
from logger_setup import logger
from settings import APP_VERSION, CONFIG_DIR, SUB_NAME, clash_path, path
from shared import fetch_links, _subscription_headers
from vless import merge_all
import yaml


app = FastAPI()

@app.on_event("startup")
async def startup_banner() -> None:
    logger.info("Starting 3x-ui aggregator %s", APP_VERSION)
    logger.info("Subscription name: %s", SUB_NAME)
    logger.info("Config directory: %s", CONFIG_DIR)
    logger.info("Legacy VLESS endpoint: %s", f"/{path}" if path else "<disabled>")
    logger.info("Clash endpoint: %s", f"/{clash_path}" if clash_path else "<disabled>")

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

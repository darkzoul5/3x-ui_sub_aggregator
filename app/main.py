import os
import httpx
import base64
import logging
import logging.handlers
from asyncio import gather
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

# Get profile name from environment, default to "Aggregated"
PROFILE_NAME = os.getenv('PROFILE_NAME', 'Aggregated')

async def fetch_links() -> tuple[list[str], list[str]]:
    '''
    Fetches the configuration source file from GitHub or local .txt file.\n
    Returns a tuple of two lists:
        - HTTP subscription links
        - Direct vless configuration links
    '''
    try:
        if os.getenv('LOCAL_MODE') == 'on':
            with open('configs.txt', encoding='utf-8') as file:
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


path = os.getenv('URL')


@app.get('/health')
async def health() -> Response:
    '''Health check endpoint'''
    return Response(content='OK', media_type='text/plain', status_code=200)


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

    # Add subscription metadata headers for clients like Hiddify
    profile_title_b64 = base64.b64encode(PROFILE_NAME.encode()).decode()
    headers = {
        "Profile-Title": f"base64:{profile_title_b64}",
        "Profile-Update-Interval": "1",
        "Subscription-Userinfo": "upload=0; download=0; total=0; expire=0"
    }
    return Response(content=global_sub, media_type='text/plain', headers=headers)

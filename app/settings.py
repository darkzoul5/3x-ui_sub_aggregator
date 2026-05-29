import os

from dotenv import load_dotenv


load_dotenv()


SUB_NAME = os.getenv('SUB_NAME', 'Aggregated')
CONFIG_DIR = os.getenv('CONFIG_DIR', '/app/configs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
path = os.getenv('URL', 'sub').strip('/')
clash_path = os.getenv('CLASH_URL', '/clash').strip('/')

if not path and not clash_path:
    raise RuntimeError("Both URL and CLASH_URL are empty. Configure at least one endpoint path.")

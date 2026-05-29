import os

from dotenv import load_dotenv


load_dotenv()


SUB_NAME = os.getenv('SUB_NAME', 'Aggregated')
CONFIG_DIR = os.getenv('CONFIG_DIR', '/app/configs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
path = os.getenv('URL', 'sub').strip('/')
clash_path = os.getenv('CLASH_URL', '/clash').strip('/')
VERSION_FILE = os.getenv('VERSION_FILE', '/app/VERSION')


def _read_version_file(file_path: str) -> str:
    try:
        with open(file_path, encoding='utf-8') as file:
            version = file.read().strip()
            return version or 'dev'
    except FileNotFoundError:
        return os.getenv('APP_VERSION', 'dev')


APP_VERSION = _read_version_file(VERSION_FILE)

if not path and not clash_path:
    raise RuntimeError("Both URL and CLASH_URL are empty. Configure at least one endpoint path.")

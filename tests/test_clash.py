import logging
import sys
import types
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch


fastapi_stub = types.ModuleType("fastapi")


class HTTPException(Exception):
    def __init__(self, status_code=500, detail=""):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


fastapi_stub.HTTPException = HTTPException
sys.modules.setdefault("fastapi", fastapi_stub)


httpx_stub = types.ModuleType("httpx")


class HTTPError(Exception):
    pass


httpx_stub.HTTPError = HTTPError
httpx_stub.AsyncClient = object
sys.modules.setdefault("httpx", httpx_stub)


yaml_stub = types.ModuleType("yaml")


class YAMLError(Exception):
    pass


yaml_stub.YAMLError = YAMLError
yaml_stub.safe_load = lambda payload: {}
yaml_stub.safe_dump = lambda data, **kwargs: ""
sys.modules.setdefault("yaml", yaml_stub)


dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)


logger_setup_stub = types.ModuleType("logger_setup")
logger_setup_stub.logger = logging.getLogger("tests")
sys.modules.setdefault("logger_setup", logger_setup_stub)


settings_stub = types.ModuleType("settings")
settings_stub.clash_path = "clash"
settings_stub.path = "sub"
sys.modules.setdefault("settings", settings_stub)


shared_stub = types.ModuleType("shared")
shared_stub._load_yaml_file = lambda file_path: {}
shared_stub._resolve_config_file = lambda *args, **kwargs: ""
sys.modules.setdefault("shared", shared_stub)


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


import clash  # noqa: E402


class DummyAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class ClashGroupTests(IsolatedAsyncioTestCase):
    def test_normalize_proxy_group_name(self):
        self.assertEqual(clash._normalize_proxy_group_name("sweden 1"), "sweden")
        self.assertEqual(clash._normalize_proxy_group_name("sweden 443"), "sweden")
        self.assertEqual(clash._normalize_proxy_group_name("latvia 1"), "latvia")
        self.assertEqual(clash._normalize_proxy_group_name("node"), "node")

    def test_generate_proxy_groups(self):
        proxies = [
            {"name": "sweden 1"},
            {"name": "sweden 2"},
            {"name": "sweden 443"},
            {"name": "latvia 1"},
        ]

        groups = clash._generate_proxy_groups(proxies)

        self.assertEqual(groups[0]["name"], "Proxy")
        self.assertEqual(groups[0]["proxies"], ["sweden", "latvia", "DIRECT"])

        by_name = {group["name"]: group for group in groups[1:]}
        self.assertEqual(by_name["sweden"]["proxies"], ["sweden 1", "sweden 2", "sweden 443"])
        self.assertEqual(by_name["latvia"]["proxies"], ["latvia 1"])

    async def test_merge_clash_uses_manual_groups_when_present(self):
        manual_groups = [
            {"name": "Manual", "type": "select", "proxies": ["DIRECT"]},
        ]

        async def fake_fetch_clash_subscription(client, clash_url):
            return [{"name": "sweden 1"}]

        with (
            patch("clash.httpx.AsyncClient", return_value=DummyAsyncClient()),
            patch.object(clash, "fetch_clash_subscription", side_effect=fake_fetch_clash_subscription),
            patch.object(clash, "_load_proxy_groups", return_value=manual_groups),
            patch.object(clash, "_load_rules", return_value=[]),
        ):
            result = await clash.merge_clash(["https://panel"], "user")

        self.assertEqual(result["proxy-groups"], manual_groups)

    async def test_merge_clash_auto_generates_groups_when_manual_missing(self):
        async def fake_fetch_clash_subscription(client, clash_url):
            if clash_url.startswith("https://one/"):
                return [{"name": "sweden 1"}, {"name": "latvia 1"}]
            return [{"name": "sweden 2"}, {"name": "sweden 443"}]

        with (
            patch("clash.httpx.AsyncClient", return_value=DummyAsyncClient()),
            patch.object(clash, "fetch_clash_subscription", side_effect=fake_fetch_clash_subscription),
            patch.object(clash, "_load_proxy_groups", return_value=None),
            patch.object(clash, "_load_rules", return_value=[]),
        ):
            result = await clash.merge_clash(["https://one", "https://two"], "user")

        group_names = [group["name"] for group in result["proxy-groups"]]
        self.assertEqual(group_names, ["Proxy", "sweden", "latvia"])
        self.assertEqual(result["proxy-groups"][1]["proxies"], ["sweden 1", "sweden 2", "sweden 443"])
        self.assertEqual(result["proxy-groups"][2]["proxies"], ["latvia 1"])

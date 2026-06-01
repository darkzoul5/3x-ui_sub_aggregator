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
settings_stub.CLASH_PATH = "clash"
settings_stub.SUB_PATH = "sub"
sys.modules.setdefault("settings", settings_stub)


shared_stub = types.ModuleType("shared")
shared_stub._load_yaml_file = lambda file_path: {}
shared_stub._resolve_config_file = lambda *args, **kwargs: ""
sys.modules.setdefault("shared", shared_stub)


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


import clash  # noqa: E402
import clash_from_vless  # noqa: E402


class DummyAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class ClashGroupTests(IsolatedAsyncioTestCase):
    def test_normalize_proxy_group_name(self):
        self.assertEqual(clash._normalize_proxy_group_name("LV-RAW"), "LV-RAW")
        self.assertEqual(clash._normalize_proxy_group_name("SW1-RAW-443"), "SW1-RAW-443")
        self.assertEqual(clash._normalize_proxy_group_name("Sweden 2"), "Sweden 2")
        self.assertEqual(clash._normalize_proxy_group_name("Sweden 2_2"), "Sweden 2")
        self.assertEqual(clash._normalize_proxy_group_name("node"), "node")

    def test_generate_proxy_groups(self):
        raw_proxies = [
            {"name": "LV-RAW-dark_zoul"},
            {"name": "LV-XHTTP-dark_zoul"},
            {"name": "SW1-RAW-dark_zoul"},
            {"name": "SW1-RAW-443-dark_zoul"},
            {"name": "SW1-XHTTP-dark_zoul"},
            {"name": "Sweden 2-1-dark_zoul"},
            {"name": "Sweden 2-2-dark_zoul"},
        ]

        proxies = clash._deduplicate_proxy_names(clash._strip_email_from_names(raw_proxies))
        groups = clash._generate_proxy_groups(proxies)

        self.assertEqual(groups[0]["name"], "Proxy")
        self.assertEqual(groups[0]["proxies"], ["LV", "SW1", "Sweden 2", "DIRECT"])

        by_name = {group["name"]: group for group in groups[1:]}
        self.assertEqual(by_name["LV"]["type"], "fallback")
        self.assertEqual(by_name["SW1"]["type"], "fallback")
        self.assertEqual(by_name["Sweden 2"]["type"], "fallback")
        self.assertEqual(by_name["LV"]["proxies"], ["LV", "LV_2"])
        self.assertEqual(by_name["SW1"]["proxies"], ["SW1", "SW1_2", "SW1_3"])
        self.assertEqual(by_name["Sweden 2"]["proxies"], ["Sweden 2", "Sweden 2_2"])

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
                return [{"name": "LV-RAW"}, {"name": "SW1-RAW"}]
            return [{"name": "LV-XHTTP"}, {"name": "SW1-RAW-443"}, {"name": "SW1-XHTTP"}, {"name": "Sweden 2"}, {"name": "Sweden 2_2"}]

        with (
            patch("clash.httpx.AsyncClient", return_value=DummyAsyncClient()),
            patch.object(clash, "fetch_clash_subscription", side_effect=fake_fetch_clash_subscription),
            patch.object(clash, "_load_proxy_groups", return_value=None),
            patch.object(clash, "_load_rules", return_value=[]),
        ):
            result = await clash.merge_clash(["https://one", "https://two"], "user")

        group_names = [group["name"] for group in result["proxy-groups"]]
        self.assertEqual(group_names, ["Proxy", "LV", "SW1", "Sweden 2"])
        self.assertEqual(result["proxy-groups"][0]["type"], "select")
        self.assertEqual(result["proxy-groups"][1]["type"], "fallback")
        self.assertEqual(result["proxy-groups"][2]["type"], "fallback")
        self.assertEqual(result["proxy-groups"][3]["type"], "fallback")
        self.assertEqual(result["proxy-groups"][1]["proxies"], ["LV", "LV_2"])
        self.assertEqual(result["proxy-groups"][2]["proxies"], ["SW1", "SW1_2", "SW1_3"])
        self.assertEqual(result["proxy-groups"][3]["proxies"], ["Sweden 2", "Sweden 2_2"])


class ClashFromVlessTests(IsolatedAsyncioTestCase):
    def test_parse_vless_line(self):
        proxy = clash_from_vless._parse_vless_line(
            "vless://12345678-1234-1234-1234-123456789abc@example.com:443?type=ws&security=tls&path=%2Fws&host=example.com&sni=example.com#sweden%201"
        )

        self.assertIsNotNone(proxy)
        self.assertEqual(proxy["name"], "sweden 1")
        self.assertEqual(proxy["type"], "vless")
        self.assertEqual(proxy["server"], "example.com")
        self.assertEqual(proxy["port"], 443)
        self.assertEqual(proxy["network"], "ws")
        self.assertEqual(proxy["tls"], True)
        self.assertEqual(proxy["ws-opts"]["path"], "/ws")
        self.assertEqual(proxy["ws-opts"]["headers"]["Host"], "example.com")

    async def test_merge_vless_to_clash(self):
        async def fake_merge_all(server_urls, sub_id):
            return (
                "vless://12345678-1234-1234-1234-123456789abc@example.com:443?type=ws&security=tls&path=%2Fws&host=example.com&sni=example.com#sweden%201\n"
                "vless://12345678-1234-1234-1234-123456789abd@example.com:443?type=ws&security=tls&path=%2Fws&host=example.com&sni=example.com#sweden%202\n"
            ).encode("utf-8")

        with patch.object(clash_from_vless, "merge_all", side_effect=fake_merge_all):
            result = await clash_from_vless.merge_vless_to_clash(["https://panel"], "user")

        self.assertEqual([proxy["name"] for proxy in result["proxies"]], ["sweden 1", "sweden 2"])
        self.assertEqual(result["proxy-groups"][0]["type"], "select")
        self.assertEqual(result["proxy-groups"][1]["type"], "fallback")
        self.assertEqual(result["proxy-groups"][1]["name"], "sweden 1")

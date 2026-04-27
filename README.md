# 3x-ui_sub_aggregator

<p align="center">
   <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.md"><b>ENG</b></a> |
   <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.ru.md"><b>RUS</b></a>
</p>

Aggregate multiple 3x-ui subscriptions into a single endpoint.

Supported output formats:
- VLESS/base64 subscription
- Clash/Mihomo YAML subscription

## What this service does

1. Reads a list of source panel base URLs from `config.txt`.
2. Builds source subscription URLs per requested `sub_id`:
    - `{server_url}/{URL}/{sub_id}` for VLESS/base64
    - `{server_url}/{CLASH_URL}/{sub_id}` for Clash
3. Fetches subscriptions from all sources in parallel.
4. Returns one merged subscription.

For Clash output, it also:
- merges all proxies,
- strips email-like suffix from proxy names,
- deduplicates proxy names,
- applies proxy groups and rules from template files.

## Requirements

- Docker and Docker Compose (recommended), or
- Python 3.11+ for local run

To aggregate subscriptions correctly, all source panels should use the same subscription ID (`sub_id`) for the same user.

## Quick start (Docker)

1. Clone the repository:

```bash
git clone https://github.com/darkzoul5/xray_config_aggregator.git
cd xray_config_aggregator
```

2. Prepare local config directory and source list:

```bash
mkdir -p configs
cp config.txt.example configs/config.txt
```

3. Edit `configs/config.txt` and put one source URL per line:

```txt
https://panel-1.example.com
https://panel-2.example.com:8443
```

4. Configure environment in `docker-compose.yml` (or your own `.env` file).

5. Start service:

```bash
docker compose up -d
```

Service default port is `8000`.

## Endpoints

The app dynamically creates routes based on `URL` and `CLASH_URL`.

- VLESS/base64:
   - `GET /{URL}`
   - `GET /{URL}/{sub_id}`
- Clash/Mihomo:
   - `GET /{CLASH_URL}`
   - `GET /{CLASH_URL}/{sub_id}`
- Health check:
   - `GET /health`

Examples (with `URL=sub` and `CLASH_URL=clash`):
- `http://localhost:8000/sub/my_sub_id`
- `http://localhost:8000/clash/my_sub_id`
- `http://localhost:8000/health`

If either `URL` or `CLASH_URL` is empty, that endpoint type is disabled.

## URL setup explained

The aggregator builds final source URLs using this formula:

- VLESS/base64 source URL: `{line_from_config.txt}/{URL}/{sub_id}`
- Clash source URL: `{line_from_config.txt}/{CLASH_URL}/{sub_id}`

So each line in `config.txt` should normally be only the server base URL:

```txt
https://server-1.example.com
https://server-2.example.com:8443
```

Then set shared path segments in env variables:

- `URL=sub`
- `CLASH_URL=clash`

With `sub_id=user123`, requests sent by aggregator will be:

- `https://server-1.example.com/sub/user123`
- `https://server-1.example.com/clash/user123`
- `https://server-2.example.com:8443/sub/user123`
- `https://server-2.example.com:8443/clash/user123`

And your aggregated links will be:

- `http://your-aggregator-host:8000/sub/user123`
- `http://your-aggregator-host:8000/clash/user123`

Notes:
- Source 3x-ui and aggregator URLs should use the same path structure (`/{URL}/{sub_id}` and `/{CLASH_URL}/{sub_id}`); only the domain/host part is different.
- `URL` and `CLASH_URL` are global for all sources.
- If a source uses a different path pattern, normalize it with a reverse proxy, or add that source with a full prefix path in `config.txt` only if the resulting final URL still matches the formula.

## Configuration reference

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOCAL_MODE` | No | `on` | `on`: read `config.txt` from `CONFIG_DIR`. Any other value: fetch from `CONFIG_URL`. |
| `CONFIG_DIR` | No | `/app/configs` | Directory with `config.txt` and Clash template files. |
| `CONFIG_URL` | Yes, if `LOCAL_MODE` is not `on` | - | Raw URL to remote config file. |
| `GITHUB_TOKEN` | Optional | - | Token for private GitHub raw file access. |
| `SUB_NAME` | No | `Aggregated` | Subscription display name used in response headers. |
| `PORT` | No | `8000` | Uvicorn listen port. |
| `URL` | No | `sub` | Path segment for VLESS/base64 endpoint. Empty disables VLESS. |
| `CLASH_URL` | No | `clash` | Path segment for Clash endpoint. Empty disables Clash. |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, ...). |

### Source list file

`config.txt` format:
- one URL per line,
- only lines starting with `http` or `https`  are used,
- trailing slash is removed automatically.

Example:

```txt
https://server-a.example.com
https://server-b-ip-address:2053
```

Example with prefix paths:

```txt
https://3x-ui.example.com/panelA
https://3x-ui.example.com/averyrandomstring
```

If `URL=sub` and `sub_id=user123`, aggregator will call:

```txt
https://3x-ui.example.com/panelA/sub/user123
https://3x-ui.example.com/averyrandomstring/sub/user123
```

### Clash template files

Read from `CONFIG_DIR`:

- `default-proxy-groups.yaml` (fallback groups)
- `default-rules.yaml` (fallback rules)
- `proxy-groups-{sub_id}.yaml` (optional per-user override)
- `rules-{sub_id}.yaml` (optional per-user override)

If a per-user file exists, it is used instead of default.

## Local run (without Docker)

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Set environment variables before running.

## Troubleshooting

- `404 Config file not found`:
   - check `CONFIG_URL`, token permissions, and whether the URL returns raw text.
- Empty or failed aggregation:
   - verify each source URL actually exposes configured `URL` and/or `CLASH_URL` paths.
   - verify `sub_id` exists on all source panels.
- No Clash groups/rules in output:
   - check template files in `CONFIG_DIR` and YAML syntax.

## Attribution and license

Based on: https://github.com/NoisyCake/vless_config_aggregator

This repository is independently maintained and licensed under MIT.
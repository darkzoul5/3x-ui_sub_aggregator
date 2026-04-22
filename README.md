<div align="center" markdown>

<p align="center">
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.md"><u><b>ENG</b></u></a> •
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.ru.md"><u><b>РУС</b></u></a>
</p>

# 3x-ui_sub_aggregator

An aggregator that combines multiple 3x-ui configurations into one endpoint.
It supports aggregation of:
classic base64 subscriptions
Clash/Mihomo YAML
</div>

## Prepare

> [!NOTE]
> This guide is relevant for Debian-based Linux distributions. Most testing was done with the sing-box client Hiddify

### Subscriptions

If you want aggregate not only direct links (`vless://`) but also subscription URLs, you'll need to enable Subscription on each panel in settings.  
All clients you want to merge must share the same **subscription ID**.

![Server 1](https://i.ibb.co/672ypTMt/image.png)

![Server 2](https://i.ibb.co/sSn9byZ/2025-03-18-153330.png)

### Configuration file

You need a `.txt` file with a list of 3x-ui server URLs available on GitHub or locally.

The app appends the path segments and subscription ID when fetching:
- For VLESS/base64 subscriptions: `{server_url}/{URL}/{subscription_id}`
- For Clash/Mihomo: `{server_url}/{CLASH_URL}/{subscription_id}`

Example:

```txt
https://example.org
https://ip_address:port
https://example.org:port
```

Note: Each server must support both endpoints with the configured `URL` and `CLASH_URL` paths.

---

## Installing & Setup

Download and install required tools:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install git curl

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

Download repo:

```bash
git clone https://github.com/darkzoul5/xray_config_aggregator.git
cd xray_config_aggregator
cp .env.example .env
```

### Environment variables

Edit the `.env` file with your own values:

|variable|description|example|
|:--:|:--|:--|
|LOCAL_MODE|If enabled, the file will be read from the local host. Otherwise, it will be fetched from a remote repository.|on|
|CONFIG_DIR|Directory that contains `config.txt` and Clash template files|/app/configs|
|CONFIG_URL|Link to the `.txt` configuration file hosted on GitHub|<https://api.github.com/.../file.txt>|
|GITHUB_TOKEN|GitHub token (required if the file is in a private repo)|ghp_dhoauigc7898374yduisdhSDHFHGf7|
|SUB_NAME|Display name for the subscription in clients. If empty, the subscription ID will be used in most cases|HFK|
|PORT|Port the service listens on|8000|
|URL|Path segment for VLESS/base64 endpoint. Leave empty to disable VLESS endpoint.|sub|
|CLASH_URL|Path segment for Clash/Mihomo endpoint. Leave empty to disable Clash endpoint.|/clash|

### Clash template files

The service reads Clash templates from `CONFIG_DIR`:

- `default-proxy-groups.yaml` (global default groups)
- `default-rules.yaml` (global default rules)
- `proxy-groups-{sub_id}.yaml` (optional per-ID groups override)
- `rules-{sub_id}.yaml` (optional per-ID rules override)

If per-ID files do not exist, defaults are used automatically.
`config.txt` is also read from the same directory.

---

## Docker Setup

This repository provides a ready to use image:
`ghcr.io/darkzoul5/3x-ui_sub_aggregator:latest`
or image by version tag:
`ghcr.io/darkzoul5/3x-ui_sub_aggregator:1.0.2`

### Quick Start

1. **Configure environment:**

   ```bash
   nano .env  # Edit with your values
   ```

2. **Run the service:**

   ```bash
   sudo docker compose up -d
   ```

### Accessing the service

The final aggregated link depends on your config:

- VLESS/base64: `https://{DOMAIN}/{URL}/subscription_id`
- Clash/Mihomo YAML: `https://{DOMAIN}/{CLASH_URL}/subscription_id`

For SSL/HTTPS, use Traefik or similar reverse proxy.

---

## License

MIT licensed — see LICENSE for details.

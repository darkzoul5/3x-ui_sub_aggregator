<div align="center" markdown>

<p align="center">
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.md"><u><b>ENG</b></u></a> •
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.ru.md"><u><b>РУС</b></u></a>
</p>

# 3x-ui_sub_aggregator

An aggregator that combines multiple VLESS configurations from various 3x-ui servers into a unified subscription link.
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

To get the service up and running, you will need a `.txt` file with 3x-ui configurations available on GitHub or locally.

Both subscription and direct VLESS links are supported:

1. Direct `vless://` links go into the file as-is.
2. For subscription links, you must strip out the subscription ID part. For example, `https://<domain>:<port>/<url>/<subscription_id>` -> `https://<domain>:<port>/<url>/` (make sure the is a trailing slash).

Example:

```txt
https://subscription_link_example:1/imy/
https://subscription_link_example:2/sub/
vless://...
vless://...
vless://...
```

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
|FILE_PATH|Absolute path to the `.txt` configuration file|/path/to/configs.txt|
|CONFIG_URL|Link to the `.txt` configuration file hosted on GitHub|<https://api.github.com/.../file.txt>|
|GITHUB_TOKEN|GitHub token (required if the file is in a private repo)|ghp_dhoauigc7898374yduisdhSDHFHGf7|
|SUB_NAME|Display name for the subscription in clients. If empty, the subscription ID will be used in most cases|HFK|
|PORT|Port the service listens on|8000|
|URL|Path segment used in the final subscription URL|sub|

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

- Direct links only: `https://{DOMAIN}/{URL}/{SUB_NAME}`
- With subscriptions: `https://{DOMAIN}/{URL}/subscription_id/{SUB_NAME}`

(Omit `/{SUB_NAME}` if the variable is empty)

For SSL/HTTPS, use Traefik or similar reverse proxy.

---

## License

MIT licensed — see LICENSE for details.

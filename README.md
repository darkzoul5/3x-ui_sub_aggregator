<div align="center" markdown>

<p align="center">
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.md"><u><b>ENG</b></u></a> •
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.ru.md"><u><b>РУС</b></u></a>
</p>

# vless_config_aggregator

A reverse proxy that aggregates multiple VLESS configurations from various 3x-ui servers into a unified subscription link.
</div>

## Prepare

> [!NOTE]
> This guide is relevant for Debian-based Linux distributions. Most testing was done with the sing-box client Hiddify

### Certificate

This service requires a valid SSL certificate, so you'll need to get it first.

Once your domain is set up, generate a certificate using the following (make sure ports 80 and/or 443 are open):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install certbot

sudo certbot certonly --standalone -d <domain> --register-unsafely-without-email
```

The certificates will be located in: "/etc/letsencrypt/live/<domain>/"

### Subscriptions

If you want aggregate not only direct links (`vless://`) but also subscription URLs, you'll need to enable Subscription on each panel in settings.  
All clients you want to merge must share the same **subscription ID**.

![Server 1](https://i.ibb.co/672ypTMt/image.png)

![Server 2](https://i.ibb.co/sSn9byZ/2025-03-18-153330.png)

### Configuration file

To get the service up and running, you'll also need a plain `.txt` file with your list configurations available on GitHub or locally.

As mentioned above, both subscription and direct VLESS links are supported:

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
git clone https://github.com/NoisyCake/vless_config_aggregator.git
cd vless_config_aggregator
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
|SERVER_NAME|Your server’s domain name|domain.or.subdomain|
|PORT|Port the service should run on|443|
|URL|Path segment used in the final subscription URL|sub|
|CERT_PATH|Absolute path to your SSL certificate directory|/etc/letsencrypt/live/domain.or.subdomain|

---

## Docker Setup

The application runs in a single Docker container combining FastAPI and Nginx. For detailed Docker configuration, build instructions, and troubleshooting, see [DOCKER_SETUP.md](DOCKER_SETUP.md).

### Quick Start

1. **Configure environment:**

   ```bash
   nano .env  # Edit with your values
   ```

2. **Get SSL certificates** (if not using LOCAL_MODE):

   ```bash
   sudo certbot certonly --standalone -d your-domain.com
   ```

3. **Run the service:**

   ```bash
   sudo docker compose up -d
   ```

4. **View logs:**

   ```bash
   docker compose logs -f
   ```

### Access the service

The final aggregated link depends on your config:

- Direct links only: `https://{SERVER_NAME}:{PORT}/{URL}/{SUB_NAME}`
- With subscriptions: `https://{SERVER_NAME}:{PORT}/{URL}/subscription_id/{SUB_NAME}`

(Omit `/{SUB_NAME}` if the variable is empty)

---

## License

MIT licensed — see LICENSE for details.

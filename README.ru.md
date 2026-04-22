<div align="center" markdown>

<p align="center">
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.md"><u><b>ENG</b></u></a> •
    <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.ru.md"><u><b>РУС</b></u></a>
</p>

# vless_config_aggregator

Агрегатор, который объединяет конфигурации 3x-ui в единую точку доступа.
Поддерживаются агрегация классических VLESS base64-подписок и Clash/Mihomo YAML.
</div>

## Подготовка

> [!NOTE]
> Инструкция актуальна для Debian-based дистрибутивов Linux. Тестирование проводились в основном с клиентом sing-box Hiddify

### Подписки

Если вы собираетесь использовать не только прямые ссылки на конфигурации (`vless://`), но и "подписочные" ссылки, то в каждой панели 3x-ui нужно настроить функцию подписки.  
Для клиентов, подписки которых вы хотите объединить, требуется установить одинаковый **subscription ID**.

![Сервер 1](https://i.ibb.co/672ypTMt/image.png)

![Сервер 2](https://i.ibb.co/sSn9byZ/2025-03-18-153330.png)

### Файл с конфигами

Необходимо создать текстовый файл со списком адресов серверов 3x-ui (доступны на GitHub или локально).

Приложение добавляет пути и ID подписки при получении конфигов:
- Для VLESS/base64 подписок: `{server_url}/{URL}/{subscription_id}`
- Для Clash/Mihomo: `{server_url}/{CLASH_URL}/{subscription_id}`

Пример:

```txt
https://example.org
https://ip_address:port
https://example.org:port
```

Примечание: Каждый сервер должен поддерживать оба endpoint с настроенными путями `URL` и `CLASH_URL`.

---

## Установка и настройка

Скачайте и установите необходимые инструменты:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install git curl

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

Скачайте репозиторий и перейдите в него:

```bash
git clone https://github.com/darkzoul5/xray_config_aggregator.git
cd xray_config_aggregator
cp .env.example .env
```

### Переменные окружения

В файле `.env` содержится несколько переменных, которые нужно настроить:

|variable|description|example|
|:--:|:--|:--|
|LOCAL_MODE|Если включено, ищет файл на хосте. Иначе пытается достать из удалённого репозитория|on|
|CONFIG_DIR|Директория с `config.txt` и шаблонами Clash|/app/configs|
|CONFIG_URL|Ссылка на `.txt` файл конфигураций|<https://api.github.com/.../file.txt>|
|GITHUB_TOKEN|Токен доступа GitHub (если файл находится в приватном репозитории)|ghp_dhoauigc7898374yduisdhSDHFHGf7|
|SUB_NAME|Имя подписки, которое будет отображаться в клиенте. Если не указано, им станет subscription ID из 3x-ui|HFK|
|PORT|Порт, на котором работает сервис|8000|
|URL|Часть пути VLESS/base64 endpoint. Оставьте пустым, чтобы отключить VLESS endpoint.|sub|
|CLASH_URL|Часть пути Clash/Mihomo endpoint. Оставьте пустым, чтобы отключить Clash endpoint.|/clash|

### Файлы шаблонов Clash

Сервис читает шаблоны Clash из `CONFIG_DIR`:

- `default-proxy-groups.yaml` (глобальные группы по умолчанию)
- `default-rules.yaml` (глобальные правила по умолчанию)
- `proxy-groups-{sub_id}.yaml` (опциональная подмена групп для конкретного ID)
- `rules-{sub_id}.yaml` (опциональная подмена правил для конкретного ID)

Если файлов для конкретного ID нет, автоматически используются default-файлы.
Файл `config.txt` также читается из этой же директории.

---

## Docker

### Быстрый старт

1. **Настройте переменные окружения:**

   ```bash
   nano .env  # Отредактируйте файл
   ```

2. **Запустите сервис:**

   ```bash
   sudo docker compose up -d
   ```

### Доступ к сервису

Итоговая ссылка на подписку зависит от вашей конфигурации:

- VLESS/base64: `https://{DOMAIN}/{URL}/subscription_id`
- Clash/Mihomo YAML: `https://{DOMAIN}/{CLASH_URL}/subscription_id`

---

## Лицензия

Проект распространяется под лицензией MIT. Подробности в файле `LICENSE`.

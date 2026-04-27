# 3x-ui_sub_aggregator

<p align="center">
   <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.md"><b>ENG</b></a> |
   <a href="https://github.com/darkzoul5/xray_config_aggregator/blob/main/README.ru.md"><b>RUS</b></a>
</p>

Объединяет несколько подписок 3x-ui в один endpoint.

Поддерживаемые форматы вывода:
- VLESS/base64-подписка
- Clash/Mihomo YAML-подписка

## Что делает сервис

1. Читает список базовых URL исходных панелей из `config.txt`.
2. Формирует URL исходных подписок для запрошенного `sub_id`:
    - `{server_url}/{URL}/{sub_id}` для VLESS/base64
    - `{server_url}/{CLASH_URL}/{sub_id}` для Clash
3. Параллельно получает подписки со всех источников.
4. Возвращает одну объединенную подписку.

Для Clash-вывода дополнительно:
- объединяет все прокси,
- удаляет email-подобный суффикс из имен прокси,
- устраняет дубликаты имен прокси,
- применяет группы прокси и правила из шаблонных файлов.

## Требования

- Docker и Docker Compose (рекомендуется), или
- Python 3.11+ для локального запуска

Чтобы агрегация работала корректно, все исходные панели должны использовать один и тот же subscription ID (`sub_id`) для одного и того же пользователя.

## Быстрый старт (Docker)

1. Клонируйте репозиторий:

```bash
git clone https://github.com/darkzoul5/xray_config_aggregator.git
cd xray_config_aggregator
```

2. Подготовьте локальную директорию конфигов и список источников:

```bash
mkdir -p configs
cp config.txt.example configs/config.txt
```

3. Отредактируйте `configs/config.txt` и укажите по одному URL источника на строку:

```txt
https://panel-1.example.com
https://panel-2.example.com:8443
```

4. Настройте переменные окружения в `docker-compose.yml` (или в своем `.env`-файле).

5. Запустите сервис:

```bash
docker compose up -d
```

Порт сервиса по умолчанию: `8000`.

## Эндпоинты

Приложение динамически создает маршруты на основе `URL` и `CLASH_URL`.

- VLESS/base64:
   - `GET /{URL}`
   - `GET /{URL}/{sub_id}`
- Clash/Mihomo:
   - `GET /{CLASH_URL}`
   - `GET /{CLASH_URL}/{sub_id}`
- Проверка состояния:
   - `GET /health`

Примеры (при `URL=sub` и `CLASH_URL=clash`):
- `http://localhost:8000/sub/my_sub_id`
- `http://localhost:8000/clash/my_sub_id`
- `http://localhost:8000/health`

Если `URL` или `CLASH_URL` пустые, соответствующий тип эндпоинта отключается.

## Объяснение настройки URL

Агрегатор формирует финальные URL источников по следующей формуле:

- URL источника VLESS/base64: `{line_from_config.txt}/{URL}/{sub_id}`
- URL источника Clash: `{line_from_config.txt}/{CLASH_URL}/{sub_id}`

Поэтому обычно каждая строка в `config.txt` должна содержать только базовый URL сервера:

```txt
https://server-1.example.com
https://server-2.example.com:8443
```

Затем задайте общие сегменты пути в переменных окружения:

- `URL=sub`
- `CLASH_URL=clash`

При `sub_id=user123` агрегатор будет отправлять запросы на:

- `https://server-1.example.com/sub/user123`
- `https://server-1.example.com/clash/user123`
- `https://server-2.example.com:8443/sub/user123`
- `https://server-2.example.com:8443/clash/user123`

А ваши агрегированные ссылки будут:

- `http://your-aggregator-host:8000/sub/user123`
- `http://your-aggregator-host:8000/clash/user123`

Примечания:
- URL источника 3x-ui и URL агрегатора должны иметь одинаковую структуру пути (`/{URL}/{sub_id}` и `/{CLASH_URL}/{sub_id}`); отличается только домен/хост.
- `URL` и `CLASH_URL` являются глобальными для всех источников.
- Если источник использует другую структуру пути, нормализуйте ее через обратный прокси (reverse proxy) или добавляйте источник с полным префиксом пути в `config.txt` только если итоговый URL все равно соответствует формуле.

## Справочник по конфигурации

### Переменные окружения

| Переменная | Обязательна | По умолчанию | Описание |
|---|---|---|---|
| `LOCAL_MODE` | Нет | `on` | `on`: читает `config.txt` из `CONFIG_DIR`. Любое другое значение: получает файл из `CONFIG_URL`. |
| `CONFIG_DIR` | Нет | `/app/configs` | Директория с `config.txt` и шаблонами Clash. |
| `CONFIG_URL` | Да, если `LOCAL_MODE` не `on` | - | Raw URL удаленного файла конфигурации. |
| `GITHUB_TOKEN` | Опционально | - | Токен для доступа к raw-файлу приватного GitHub-репозитория. |
| `SUB_NAME` | Нет | `Aggregated` | Отображаемое имя подписки в заголовках ответа. |
| `PORT` | Нет | `8000` | Порт прослушивания Uvicorn. |
| `URL` | Нет | `sub` | Сегмент пути для VLESS/base64 эндпоинта. Пустое значение отключает VLESS. |
| `CLASH_URL` | Нет | `clash` | Сегмент пути для Clash эндпоинта. Пустое значение отключает Clash. |
| `LOG_LEVEL` | Нет | `INFO` | Уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`, ...). |

### Файл списка источников

Формат `config.txt`:
- один URL в строке,
- используются только строки, начинающиеся с `http` или `https`,
- завершающий `/` удаляется автоматически.

Пример:

```txt
https://server-a.example.com
https://server-b-ip-address:2053
```

Пример с префиксами пути:

```txt
https://3x-ui.example.com/panelA
https://3x-ui.example.com/averyrandomstring
```

Если `URL=sub` и `sub_id=user123`, агрегатор вызовет:

```txt
https://3x-ui.example.com/panelA/sub/user123
https://3x-ui.example.com/averyrandomstring/sub/user123
```

### Файлы шаблонов Clash

Читаются из `CONFIG_DIR`:

- `default-proxy-groups.yaml` (резервные группы)
- `default-rules.yaml` (резервные правила)
- `proxy-groups-{sub_id}.yaml` (необязательное переопределение для конкретного пользователя)
- `rules-{sub_id}.yaml` (необязательное переопределение для конкретного пользователя)

Если файл для конкретного пользователя существует, используется он вместо default-файла.

## Локальный запуск (без Docker)

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Перед запуском задайте переменные окружения.

## Устранение неполадок

- `404 Config file not found`:
   - проверьте `CONFIG_URL`, права токена и то, что URL действительно возвращает raw-текст.
- Пустая или неуспешная агрегация:
   - проверьте, что каждый URL источника действительно отдает настроенные пути `URL` и/или `CLASH_URL`.
   - проверьте, что `sub_id` существует на всех исходных панелях.
- В Clash-выводе нет групп/правил:
   - проверьте шаблонные файлы в `CONFIG_DIR` и корректность YAML-синтаксиса.

## Указание авторства и лицензия

Основано на: https://github.com/NoisyCake/vless_config_aggregator

Этот репозиторий поддерживается независимо и распространяется по лицензии MIT.

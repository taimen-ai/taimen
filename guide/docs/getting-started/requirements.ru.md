# Требования

Статья перечисляет, что нужно машине, на которой поднимается платформа Taimen:
ресурсы, программное обеспечение, свободные порты и сетевые условия. Цифры
приведены для профилей `deploy/local/compose.yml`; для промышленного стенда смотрите также
[Ресурсы и масштабирование](../operations/capacity.md).

## Аппаратные ресурсы

Лимиты памяти контейнеров заданы в `deploy/local/compose.yml` (`mem_limit`, переопределяются
переменными `*_MEM_LIMIT`). Сумма лимитов — верхняя граница; фактическое
потребление ниже.

| Набор профилей | Контейнеров | Сумма `mem_limit` по умолчанию | Рекомендуемая машина |
|---|---|---|---|
| `core edge` (по умолчанию) | 9 | ≈ 2,8 ГБ (без Caddy, у него лимита нет) | 2 vCPU, 4 ГБ RAM |
| `+ notify` | +2 | +0,5 ГБ | по месту |

Ориентиры из практики:

- стек `core edge` в покое занимает около **0,7 ГБ RSS**;
- **первая сборка образов** занимает несколько минут (Python-зависимости,
  образ `memory-db` с Apache AGE и pgvector); повторная с кэшем — десятки
  секунд.

Диск: образы ядра — несколько гигабайт, плюс данные PostgreSQL в volumes.
Закладывайте **не меньше 20 ГБ** свободного места под Docker для `core edge`.

!!! note "Docker Desktop"
    На macOS и Windows ресурсы ограничены настройками Docker Desktop, а не
    машиной. Выделите VM не меньше 4 ГБ памяти для `core edge`, иначе
    контейнеры будут убиты по OOM без явной ошибки в `make up`.

## Программное обеспечение

| Инструмент | Версия | Зачем |
|---|---|---|
| **Docker Engine** или Docker Desktop | актуальная | контейнеры всех сервисов |
| **Docker Compose** | v2.24 или новее | `deploy/local/compose.yml` использует `env_file` с `required: false` и `--profile "*"` |
| **git** | любая свежая | суперпроект и сабмодули |
| **make** | GNU make или BSD make | цели `Makefile` |
| **Python 3** | 3.10+ | `tools/fill_secrets.py`, `tools/smoke.py`, `deploy/bootstrap.py` |
| **PyYAML**, **jsonschema** | — | только если uv не установлен: `deploy/bootstrap.py` читает и проверяет пакеты каталога (`packages/`); `make bootstrap` при установленном uv подключает их сам, без uv — берёт из системного Python, а без них bootstrap останавливается на шаге 5b |
| **openssl** | любая | `make secrets` генерирует RSA-ключ подписи IAM |
| **uv** | актуальная | установка CLI и MCP-сервера Control Plane, `make check`, сборка руководства; `make bootstrap` запускает через него скрипт с PyYAML и jsonschema |
| **curl**, **jq** | — | проверки и примеры из руководства (необязательно) |

Проверка:

```bash
docker compose version          # Docker Compose version v2.24+ (или новее)
openssl version
uv --version
# только если uv нет — зависимости bootstrap в системном Python:
python3 -c 'import yaml, jsonschema; print("ok")'
```

`make bootstrap` сам выбирает интерпретатор: при установленном uv —
`uv run --no-project --with pyyaml --with jsonschema python3`, иначе
системный `python3`.

### Операционная система

- **Linux** (x86_64) — основная целевая платформа, в том числе для
  промышленного стенда.
- **macOS** с Docker Desktop — поддерживается для локальной работы.
- **Windows** — через WSL 2 с Docker Desktop; команды руководства выполняются в
  shell WSL.

!!! warning "Права на файлы секретов в Linux"
    Контейнеры IAM и Control Plane работают под uid `10001`. Файлы, которые
    монтируются в них как секреты (`secrets/iam-signing.pem`), должны
    принадлежать этому uid, права оставьте `600`:

    ```bash
    sudo chown 10001:10001 secrets/*.pem
    ```

    Иначе IAM не прочитает ключ подписи и обмен токенов закончится `500`.
    На macOS с Docker Desktop это не требуется.

## Порты

Наружу публикуется только Caddy. Остальные сервисы слушают на `127.0.0.1` хоста
— это нужно для bootstrap, `make smoke` и локальной отладки.

| Порт хоста | Сервис | Переменная | Профиль |
|---|---|---|---|
| `80`, `443` | `caddy` | `EDGE_HTTP_PORT`, `EDGE_HTTPS_PORT` | `edge` |
| `127.0.0.1:18000` | `control-plane-api` | `CP_HOST_PORT` | `core` |
| `127.0.0.1:18001` | `memory-service` | `MEMORY_HOST_PORT` | `core` |
| `127.0.0.1:18010` | `iam-service` | `IAM_HOST_PORT` | `core` |
| `127.0.0.1:18045` | `notification-service` | `NOTIFY_HOST_PORT` | `notify` |

`make check` дополнительно поднимает тестовую базу на `5434` (Control Plane).

Проверка занятости:

```bash
# Linux
ss -ltnp | grep -E ':(80|443|18000|18001|18010)\b'
# macOS
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(80|443|18000|18001|18010) '
```

## Имя хоста для локального стенда

По умолчанию публичный адрес платформы — `http://taimen.localhost`
(`TAIMEN_PUBLIC_URL`). Из него же выводится issuer IAM
(`http://taimen.localhost/iam`).

- Chrome и Firefox резолвят `*.localhost` в `127.0.0.1` сами.
- Для `curl`, Safari и системных резолверов добавьте строку в `/etc/hosts`:

    ```text
    127.0.0.1 taimen.localhost
    ```

Внутри сети compose контейнеры ходят на тот же адрес через Caddy: у сервиса
`caddy` есть сетевой alias `${TAIMEN_PUBLIC_HOST}`, поэтому issuer совпадает и в
браузере, и в контейнерах.

!!! tip "Без Caddy и без /etc/hosts"
    Для работы с API достаточно портов на `127.0.0.1`: bootstrap, `curl` и CLI
    могут ходить прямо в `http://127.0.0.1:18010` (IAM) и
    `http://127.0.0.1:18000` (Control Plane). Issuer в токене определяется
    конфигурацией IAM, а не адресом, по которому к нему обратились, поэтому
    токены, полученные напрямую, принимаются Control Plane.

## Сеть

| Направление | Нужно для | Обязательно |
|---|---|---|
| Docker Hub, `ghcr.io` | базовые образы (`postgres`, `caddy`, `uv`, `minio`) | при сборке и первом запуске |
| PyPI, npm registry | зависимости при сборке образов | при сборке |
| OpenAI-совместимый LLM endpoint (`LLM_BASE_URL`) | эмбеддинги и реранк памяти, скиллы | нет: память работает офлайн (`MEMORY_EMBEDDING_PROVIDER=fake`, `MEMORY_LLM_PROVIDER=echo`) |
| Let's Encrypt (порт 80/443 извне) | TLS промышленного стенда через Caddy | только для промышленного стенда |

## См. также

- [Установка и первый запуск](quickstart.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [Ресурсы и масштабирование](../operations/capacity.md)
- [Установка и запуск — диагностика](../troubleshooting/startup.md)

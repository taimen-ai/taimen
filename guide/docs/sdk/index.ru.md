# SDK и интеграции

Раздел для разработчиков, которые пишут код поверх платформы: собственный
resource service, исполнителя (агента), скилл или код интеграции пакета. Здесь
описаны канонические библиотеки платформы и правила их подключения. Все
библиотеки — Python 3.12+. Сам пакет — вертикаль или интеграция — собирается
инструментом `package-sdk`, см. раздел [Пакеты](../packages/index.md).

## Библиотеки

| Библиотека | Пакет Python | Для чего | Зависимости |
|---|---|---|---|
| [platform-auth-sdk](platform-auth-sdk.md) | `platform_auth` | проверка токенов IAM и Policy Enforcement Point в resource service: identity → revocation → entitlement → policy → гейты сервиса | `pyjwt[crypto]`, `httpx` |
| [control-plane-client](clients.md#control-plane-client) | `control_plane_client` | клиент REST API Control Plane, разрешение credential, обмен PAT на access token | `httpx` |
| [platform-memory-client](clients.md#memory-client) | `platform_memory_client` | клиент memory-service (`/api/brain/*`, `/api/memory/*`) | `httpx`, `pydantic` |
| [skill-sdk](skill-sdk.md) | `skill_sdk` | написать скилл кодом, хостить его по `local`/`http`/`mcp` и выгрузить YAML для пакета каталога | `pydantic`, `jsonschema`, `pyyaml`; опционально `platform-auth-sdk`, `platform-llm` |
| [platform-llm](platform-llm.md) | `platform_llm` | единый LLM-клиент со structured output, ретраями и ротацией моделей | `httpx`, `pydantic` |
| [package-sdk](../packages/index.md) | `package_sdk` | инструмент автора пакетов (`check`, `test`, `lock`, `plan`, `apply`) и среда наблюдателя интеграции `package_sdk.connector` | `pyyaml`, `jsonschema`, `ruamel.yaml`; дополнения `sandbox`, `connector`, `skills`, `mcp` |

Вертикаль — это пакет каталога без своего runtime: работа, процессы и правила
исполняет ядро, действия во внешнем мире — скиллы на `skill-sdk`, факты из
внешнего мира пишет наблюдатель на `package_sdk.connector`. Свой сервис с базой
нужен, только если у домена есть собственные данные, и тогда он выставляет
наружу HTTP-скиллы (см. [Пакеты](../packages/index.md#vertical)).

## Правило канонических клиентов

Для логики, у которой в платформе уже есть канон, свой код **не пишется**
(обоснование — TAI-ADR-0030):

| Задача | Канон | Чего не делать |
|---|---|---|
| Проверить токен IAM в своём сервисе | `platform_auth.TokenVerifier` + `JwksCache` | разбирать JWT вручную, принимать audience «по вхождению» |
| Обменять PAT или client credentials на access token | `control_plane_client.IamCredential`, `platform_auth.ServiceTokenProvider` | хранить access token дольше его TTL, слать PAT как Bearer в сервис |
| Вызвать Control Plane | `control_plane_client.ControlPlaneClient` | писать свой HTTP-клиент по памяти о контракте |
| Прочитать или записать память из пакета: процесса, правила, скилла, наблюдателя, исполнителя | через ядро: шаги процесса `memory`, `recall`, `remember`; `ctx.knowledge` скилла; `ctx.snapshot` наблюдателя; контекст задачи и run'а | ходить в memory-service напрямую, заводить пакету свой грант на namespace |
| Прочитать или записать память из приложения со своим грантом на namespace | `platform_memory_client` | ходить в базу памяти напрямую |
| Вызвать LLM | `platform_llm.OpenAICompatibleClient` | копировать ретраи и разбор JSON в каждый сервис |

Клиенты лежат рядом с сервером в его репозитории (`services/control-plane/client`,
`services/memory-service/client`) и версионируются вместе с серверным контрактом.

### Память — только через ядро { #memory-through-core }

Код пакета — процесс, правило, скилл, наблюдатель, исполнитель задач — к
memory-service не обращается. Все его запросы к памяти идут в Control Plane, а ядро
само ходит в память от своего имени, проверяя права вызывающего на пространство
работы и включённые онтологии (TAI-ADR-0054):

| Кто | Как читает и пишет память |
|---|---|
| процесс | проекция дела `memory`, шаги `recall` и `remember`, контекст шагов ([Процессы и база знаний](../processes/knowledge.md)) |
| скилл | `ctx.knowledge`: `recall`, `query`, `preview` и `apply` снимка, `document` ([skill-sdk](skill-sdk.md#core-access)) |
| наблюдатель | `ctx.snapshot` — снимок внешней системы ([Интеграции](../packages/integrations.md#observer)) |
| исполнитель задачи | контекст задачи и run'а ([Контекст задачи и память](../control-plane/context.md)) |

Прямой клиент памяти `platform_memory_client` — для приложений со своим грантом
на namespace, а не для пакетов (см. [Клиенты сервисов](clients.md#memory-client)).

## Подключение {#connect}

Библиотеки подключаются **path-зависимостями соседними папками**. Раскладка
суперпроекта плоская: компоненты лежат в корне рядом друг с другом, и
потребитель ссылается на `../platform-auth-sdk`, `../control-plane/client` и
т. п.

=== "uv (`tool.uv.sources`)"

    ```toml
    [project]
    dependencies = [
        "platform-auth-sdk>=0.1.0",
        "control-plane-client",
        "platform-memory-client",
    ]

    [tool.uv.sources]
    platform-auth-sdk = { path = "../platform-auth-sdk", editable = true }
    control-plane-client = { path = "../control-plane/client", editable = true }
    platform-memory-client = { path = "../memory-service/client", editable = true }
    ```

=== "PEP 508 с `{root:uri}` (hatch)"

    ```toml
    [project]
    dependencies = [
        "platform-auth-sdk @ {root:uri}/../platform-auth-sdk",
        "control-plane-client @ {root:uri}/../control-plane/client",
        "platform-llm @ {root:uri}/../platform-llm",
    ]
    ```

!!! warning "Контекст сборки образа — корень суперпроекта"
    Из-за path-зависимостей образ сервиса нельзя собрать из его каталога:

    соседей там нет. Сервисы платформы, зависящие от SDK (control-plane,
    сервисы пакетов),
    собираются с контекстом `.` (корень) и `dockerfile: <компонент>/Dockerfile`; лишнее отсекает
    `.dockerignore` в корне. Делайте так же для своего сервиса:

    ```yaml
    my-service:
      build:
        context: .
        dockerfile: my-service/Dockerfile
    ```

    Runner-хост, который исполняет агентов в рабочих копиях, материализует
    соседей под теми же именами — поэтому раскладку нельзя менять.

## Токены: кто что предъявляет


```mermaid
flowchart LR
    subgraph Исполнитель
      PAT[Platform Access Token] ==>|"IamCredential"| X1[POST /iam/api/v1/platform-access-tokens:exchange]
    end
    subgraph Сервис
      CC[client_id + client_secret] ==>|"ServiceTokenProvider"| X2[POST /iam/api/v1/tokens/exchange]
    end
    X1 ==> AT1[access token audience control-plane]
    X2 ==> AT2[access token audience memory-service / …]
    AT1 ==> CP[Control Plane]
    AT2 ==> RS[Resource service]
    RS ==>|"TokenVerifier (platform-auth-sdk)"| V[проверка]
    CP ==>|"TokenVerifier"| V
```


| Кто | Credential | Как получает access token | Библиотека |
|---|---|---|---|
| Агент, харнесс, CLI | PAT (из локального хранилища, файла или переменной) | обмен PAT → токен одного audience | `control_plane_client.IamCredential` |
| Сервис платформы | client credentials service account'а | обмен client credentials → токен audience | `platform_auth.ServiceTokenProvider` |
| Человек в браузере | вход во внешний OIDC IdP | `federation:exchange` в IAM (веб-клиент) | — (см. [Федерация identity](../iam/federation.md)) |

Правило **«один токен — один audience»**: resource service принимает только
токен, выпущенный ровно для него. Если процессу нужны два сервиса, он делает
два обмена одного и того же PAT (см. [Токены, audiences, scopes](../iam/tokens.md)).

## Проверка и тесты

| Библиотека | Проверка |
|---|---|
| platform-auth-sdk | `uv run pytest`, `uv run ruff check .`, `uv run mypy` |
| skill-sdk | `uv run pytest -q` |
| platform-llm | `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .` |
| клиенты | тесты клиента запускаются вместе с тестами сервиса |

`platform_auth.testing` даёт генератор ключей, выпуск токенов с
произвольными claims и управляемые часы — используйте его в тестах своего
сервиса вместо самописных фикстур.

## См. также

- [platform-auth-sdk](platform-auth-sdk.md)
- [Клиенты сервисов](clients.md)
- [skill-sdk](skill-sdk.md)
- [platform-llm](platform-llm.md)
- [Пакеты](../packages/index.md) — вертикаль как пакет, инструмент `package-sdk`
- [Токены, audiences, scopes](../iam/tokens.md)

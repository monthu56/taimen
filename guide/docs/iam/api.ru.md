# API IAM

Полный справочник HTTP API `iam-service`: эндпоинты, способ аутентификации,
тела запросов и ответов, коды ошибок. Для интеграторов и администраторов.
Концепции описаны в соседних статьях раздела; здесь — контракт.

## Общие сведения

| | |
|---|---|
| Внутренний адрес | `http://iam-service:8010` (сеть compose) |
| Адрес на хосте | `http://127.0.0.1:${IAM_HOST_PORT:-18010}` |
| Публичный адрес | `${TAIMEN_PUBLIC_URL}/iam` (Caddy срезает префикс `/iam`) |
| Формат | JSON; SCIM — `application/scim+json` |
| OpenAPI | `GET /openapi.json`, интерактивно — `GET /docs` (стандартные для FastAPI) |

### Аутентификация

| Способ | Заголовок / тело | Где |
|---|---|---|
| Bootstrap | `X-IAM-Bootstrap-Token: <IAM_BOOTSTRAP_TOKEN>` | все административные эндпоинты (помечены **B**) |
| Предъявление PAT | поле `token` в теле | `platform-access-tokens:exchange`, `:introspect`, `:revoke-self` |
| Client credentials | поля `clientId`, `clientSecret` в теле | `tokens/exchange` |
| Upstream-токен IdP | поле `token` в теле | `federation:authenticate`, `federation:exchange` |
| Bearer access token audience `iam-scim` | `Authorization: Bearer …` | `/scim/v2/*` |
| Без аутентификации | — | `/healthz`, `/.well-known/jwks.json` |

Неверный или пустой bootstrap-заголовок — `401 {"detail":"unauthorized"}`.
Если `IAM_BOOTSTRAP_TOKEN` не задан, все административные эндпоинты закрыты.

### Формат ошибок

```json
{"detail": "scope_not_allowed"}
```

`detail` — стабильный машинный код. Ошибки валидации тела (лишнее поле,
неверный шаблон, пустая строка) — стандартный ответ FastAPI `422` со списком
в `detail`. SCIM возвращает ошибки в формате RFC 7644.

### Регистр полей

- Запросы принимают поля в camelCase (`displayName`, `allowedScopes`,
  `scopeCeiling`, `expiresInSeconds`).
- Ответы tenant, principal, audience, group, identity provider, external
  identity и журнала событий — в **snake_case** (`display_name`,
  `allowed_scopes`, `created_at`).
- Ответы PAT, обменов токенов, федерации, service account и authentication
  context — в **camelCase**.

## Сводная таблица

| Метод и путь | Auth | Назначение |
|---|---|---|
| `GET /healthz` | — | Живость |
| `GET /.well-known/jwks.json` | — | Публичный ключ подписи |
| `POST /api/v1/tenants` | B | Создать tenant |
| `GET /api/v1/events` | B | Журнал событий (outbox) |
| `POST /api/v1/tenants/{tenantId}/principals` | B | Создать principal |
| `GET /api/v1/tenants/{tenantId}/principals/{principalId}` | B | Прочитать principal |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}:disable` | B | Отключить principal и отозвать его PAT |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}/external-identities` | B | Привязать external identity |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}/authentication-contexts` | B | Записать вход человека |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}/platform-access-tokens` | B | Выпустить PAT |
| `GET /api/v1/tenants/{tenantId}/platform-access-tokens` | B | Список PAT |
| `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:revoke` | B | Отозвать PAT |
| `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:rotate` | B | Ротировать PAT |
| `POST /api/v1/tenants/{tenantId}/legacy-credentials:import` | B | Импорт ключа Control Plane |
| `POST /api/v1/platform-access-tokens:exchange` | PAT | PAT → access token |
| `POST /api/v1/platform-access-tokens:introspect` | PAT | Сведения о PAT |
| `POST /api/v1/platform-access-tokens:revoke-self` | PAT | Отзыв владельцем |
| `POST /api/v1/tenants/{tenantId}/audiences` | B | Создать audience |
| `GET /api/v1/tenants/{tenantId}/audiences` | B | Список audiences |
| `PATCH /api/v1/tenants/{tenantId}/audiences/{key}` | B | Заменить `allowedScopes` |
| `POST /api/v1/tenants/{tenantId}/service-accounts` | B | Создать service account |
| `POST /api/v1/tenants/{tenantId}/service-accounts/{clientId}:revoke` | B | Отозвать service account |
| `POST /api/v1/tokens/exchange` | client credentials | Client credentials → access token |
| `POST /api/v1/tenants/{tenantId}/groups` | B | Создать группу |
| `POST /api/v1/tenants/{tenantId}/groups/{groupId}/members` | B | Добавить участника |
| `POST /api/v1/tenants/{tenantId}/identity-providers` | B | Зарегистрировать IdP |
| `POST /api/v1/tenants/{tenantId}/federation:authenticate` | upstream | Подтвердить вход |
| `POST /api/v1/tenants/{tenantId}/federation:exchange` | upstream | Вход + access token |
| `POST /api/v1/tenants/{tenantId}/provisioning-sources` | B | Зарегистрировать источник SCIM/LDAP |
| `GET /api/v1/tenants/{tenantId}/provisioning-sources` | B | Источники и их устаревание |
| `GET`, `POST` `/scim/v2/Users`; `GET`, `PUT`, `PATCH`, `DELETE` `/scim/v2/Users/{id}` | SCIM | Пользователи |
| `GET`, `POST` `/scim/v2/Groups`; `GET`, `PUT`, `PATCH`, `DELETE` `/scim/v2/Groups/{id}` | SCIM | Группы |
| `GET /scim/v2/ServiceProviderConfig`, `/ResourceTypes`, `/Schemas` | SCIM | Discovery SCIM |

!!! danger "Административные эндпоинты доступны и через периметр"
    Поставляемые Caddyfile проксируют весь путь `/iam/*`, включая
    эндпоинты с bootstrap-заголовком. Их защищает только секрет. В
    промышленной инсталляции рассмотрите ограничение этих путей на периметре
    (разрешить снаружи только `/.well-known/jwks.json`, `:exchange`,
    `:introspect`, `:revoke-self`, `tokens/exchange`, `federation:*` и
    `/scim/v2`) — см. [Периметр и TLS](../operations/edge-and-tls.md).

## Служебные

### `GET /healthz`

```json
{"status": "ok"}
```

Не проверяет базу данных.

### `GET /.well-known/jwks.json`

```json
{"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "local-dev", "n": "…", "e": "AQAB"}]}
```

Один текущий ключ. Без настроенного ключа подписи — `500`. См.
[JWKS и ключ подписи](tokens.md).

## Tenants

### `POST /api/v1/tenants` — B

| Поле | Тип | Обязательно | Правила |
|---|---|---|---|
| `slug` | string | да | `^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$` |
| `name` | string | да | 1–200 |
| `id` | UUID | нет | явный идентификатор tenant |

`201` → `{id, slug, name, status, created_at}`.
Ошибки: `409 tenant_id_exists`, `409 tenant_slug_exists`.

## Principals

### `POST /api/v1/tenants/{tenantId}/principals` — B

```json
{"kind": "agent", "displayName": "Coding Runner"}
```

`kind` ∈ `human`, `agent`, `service_account`, `workload`; `displayName` 1–200.
`201` → `{id, kind, display_name, status, created_at}`.
Ошибки: `404 tenant_not_found`.

### `GET /api/v1/tenants/{tenantId}/principals/{principalId}` — B

`200` → principal. `404 principal_not_found`, если нет активного membership.

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}:disable` — B

Query: `reason` (≤ 200, по умолчанию `principal_disabled`).
`200` → `{"principalId", "status": "disabled", "revokedCredentials": <n>}`.
Ошибки: `404 principal_not_found`. Повторный вызов снова возвращает `200`
(`revokedCredentials: 0`).

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}/external-identities` — B

```json
{"issuer": "https://idp.example.com/realms/corp", "subject": "<sub>"}
```

`201` → `{id, principal_id, issuer, subject, status, created_at}`.
Ошибки: `404 principal_not_found`, `409 identity_provider_managed`,
`409 external_identity_exists`.

## Authentication contexts и PAT {#pat}

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}/authentication-contexts` — B

| Поле | Тип | Обязательно |
|---|---|---|
| `issuer` | string (1–500) | да |
| `acr` | string (≤ 200) | нет |
| `amr` | string[] | нет |
| `authTime` | datetime | нет |
| `externalIdentityId` | UUID | нет |

`201` → `{id, principalId, issuer, acr, amr, authTime, recordedAt, source: "bootstrap"}`.
Ошибки: `404 tenant_not_found`, `404 principal_not_found`,
`409 principal_not_active`, `422 human_principal_required`.

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}/platform-access-tokens` — B

Заголовок: `Idempotency-Key` (обязателен).

| Поле | Тип | Обязательно | Правила |
|---|---|---|---|
| `name` | string | да | 1–200 |
| `audiences` | string[] | да | ≥ 1, активные audiences tenant |
| `scopeCeiling` | string[] | нет | ⊆ объединения `allowedScopes` audiences |
| `expiresInSeconds` | int | нет | ≥ 60, ≤ `IAM_PAT_MAX_TTL_SECONDS` |

`201` → `{"credential": PlatformAccessTokenView, "token": "iam_pat_…"}`.
Повтор с тем же ключом: `201`, `token: null`, заголовок `Idempotency-Replayed: true`.

Ошибки: `400 idempotency_key_required`, `403 authentication_context_required`,
`403 authentication_context_expired`, `404 tenant_not_found`,
`404 principal_not_found`, `409 principal_not_active`,
`409 credential_conflict`, `422 principal_kind_not_allowed`,
`422 unknown_audience`, `422 invalid_scope_ceiling`, `422 expiry_too_long`.

**PlatformAccessTokenView:**

```json
{
  "id": "<credential-id>", "tenantId": "<tenant-id>", "principalId": "<principal-id>",
  "name": "harness-alice", "kind": "platform_access_token", "publicPrefix": "<prefix>",
  "audiences": ["control-plane"], "scopeCeiling": ["control-plane:read"],
  "createdAt": "…", "expiresAt": "…", "lastUsedAt": null,
  "revokedAt": null, "revokeReason": "", "rotatedFromId": null
}
```

### `GET /api/v1/tenants/{tenantId}/platform-access-tokens` — B

Query: `principalId` (UUID, необязательно), `includeRevoked` (bool, по
умолчанию `false`). `200` → `PlatformAccessTokenView[]`, по `createdAt`.

### `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:revoke` — B

Query: `reason` (≤ 200, по умолчанию `revoked`). `204`. Идемпотентно.
Ошибки: `404 credential_not_found`.

### `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:rotate` — B

Заголовок: `Idempotency-Key`. Тело: `{}` (любые поля запрещены).
`201` → `{"credential": …, "token": "iam_pat_…"}` — преемник с теми же
`audiences`, `scopeCeiling`, `expiresAt`; предшественник отозван с
`revokeReason: "rotated"`.
Ошибки: `400 idempotency_key_required`, `404 credential_not_found`,
`409 credential_not_active`, `404 tenant_not_found`, `404 principal_not_found`,
`409 principal_not_active`, `409 credential_conflict`.

### `POST /api/v1/tenants/{tenantId}/legacy-credentials:import` — B

| Поле | Правила |
|---|---|
| `principalId` | активный member tenant |
| `name` | 1–200 |
| `keyPrefix` | 12 hex-символов |
| `keyHash` | 64 hex-символа (SHA-256 полного ключа) |
| `audience` | активный audience |
| `scopeCeiling` | ⊆ `allowedScopes` audience |
| `expiresInSeconds` | ≥ 60, ≤ `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS` |

`201` → `PlatformAccessTokenView` (`kind: legacy_control_plane_api_key`).
Ошибки: `422 invalid_credential_material`, `422 compatibility_window_too_long`,
`422 unknown_audience`, `422 invalid_scope_ceiling`, `409 credential_exists`.

### `POST /api/v1/platform-access-tokens:exchange`

```json
{"token": "iam_pat_…", "audience": "control-plane", "scopes": ["control-plane:read"]}
```

`200` → `{accessToken, tokenType: "Bearer", expiresIn, audience, scope, sessionId}`.
Ошибки: `401 invalid_token`, `403 audience_not_allowed`, `403 scope_not_allowed`.

### `POST /api/v1/platform-access-tokens:introspect`

```json
{"token": "iam_pat_…"}
```

`200` → `{tenantId, principalId, principalKind, displayName, credentialId,
name, publicPrefix, audiences, scopeCeiling, expiresAt, issuedAt}`.
Ошибки: `401 invalid_token`.

### `POST /api/v1/platform-access-tokens:revoke-self`

```json
{"token": "iam_pat_…", "reason": "logout"}
```

`reason` ≤ 200, по умолчанию `logout`. `204`. Повтор — `401 invalid_token`.

## Audiences

### `POST /api/v1/tenants/{tenantId}/audiences` — B

```json
{"key": "reports", "allowedScopes": ["reports:read", "reports:write"]}
```

`key`: `^[a-z0-9][a-z0-9._-]{1,118}[a-z0-9]$`; scope — 1–120 символов.
`201` → `{id, tenant_id, key, allowed_scopes, status}`.
Ошибки: `404 tenant_not_found`, `409 audience_exists`, `422 invalid_scope`.

### `GET /api/v1/tenants/{tenantId}/audiences` — B

`200` → массив audiences, по `key`. `404 tenant_not_found`.

### `PATCH /api/v1/tenants/{tenantId}/audiences/{key}` — B

```json
{"allowedScopes": ["reports:read", "reports:write", "reports:admin"]}
```

Заменяет список целиком; без изменений — no-op. `200` → audience.
Ошибки: `404 audience_not_found`, `422 invalid_scope`.

## Service accounts {#service-accounts}

### `POST /api/v1/tenants/{tenantId}/service-accounts` — B

```json
{"displayName": "Reports Service", "audiences": ["memory-service"], "scopeCeiling": ["memory:read"]}
```

`201` → `{"principalId", "clientId": "iam_sa_…", "clientSecret"}` — секрет один раз.
Ошибки: `422 unknown_audience`.

### `POST /api/v1/tenants/{tenantId}/service-accounts/{clientId}:revoke` — B

`204`, идемпотентно. Ошибки: `404 service_account_not_found`.

### `POST /api/v1/tokens/exchange`

```json
{"clientId": "iam_sa_…", "clientSecret": "…", "audience": "memory-service", "scopes": ["memory:read"]}
```

`200` → `{accessToken, tokenType: "Bearer", expiresIn}`.
Ошибки: `401 invalid_client`, `403 audience_not_allowed`, `403 scope_not_allowed`.

## Группы

### `POST /api/v1/tenants/{tenantId}/groups` — B

```json
{"key": "operators", "name": "Операторы"}
```

`201` → `{id, tenant_id, key, name, status}`.
Ошибки: `404 tenant_not_found`, `409 group_exists`.

### `POST /api/v1/tenants/{tenantId}/groups/{groupId}/members` — B

```json
{"principalId": "<principal-id>"}
```

`201` → `{id, tenant_id, group_id, principal_id}`.
Ошибки: `404 group_not_found`, `409 group_is_federated`,
`404 principal_not_found`, `409 group_membership_exists`.

## Федерация {#federation}

### `POST /api/v1/tenants/{tenantId}/identity-providers` — B

Поля: `key`, `issuer`, `audience` (обязательные), `jwksUri`, `subjectClaim`,
`externalIdClaim`, `groupClaim`, `groupMappings`, `requiredAcrValues`,
`requiredAmrValues`, `lifecycleProfile` (`read_only`|`managed`),
`jwksCacheTtlSeconds`, `jwksStaleGraceSeconds` — см.
[Федерация identity](federation.md). Лишние поля запрещены.

`201` → `{id, tenant_id, key, issuer, audience, jwks_uri, subject_claim,
external_id_claim, group_claim, group_mappings, required_acr_values,
required_amr_values, lifecycle_profile, status}`.
Ошибки: `404 tenant_not_found`, `422 invalid_issuer`, `409 identity_provider_exists`.

### `POST /api/v1/tenants/{tenantId}/federation:authenticate`

```json
{"identityProvider": "corp-idp", "token": "<access token IdP>"}
```

`200` → `{principalId, identityProvider, groups, authenticationContext: {acr, amr, authTime}, identityProviderStale}`.

### `POST /api/v1/tenants/{tenantId}/federation:exchange`

```json
{"identityProvider": "corp-idp", "token": "<access token IdP>", "audience": "control-plane", "scopes": []}
```

`200` → `{accessToken, tokenType, expiresIn, audience, scope, sessionId,
principalId, identityProvider, groups, authenticationContext, identityProviderStale}`.

Ошибки обоих эндпоинтов — таблица в статье
[Федерация identity](federation.md#federation-errors); дополнительно для
`exchange`: `422 human_principal_required`, `403 audience_not_allowed`,
`403 scope_not_allowed`.

## Провижининг

### `POST /api/v1/tenants/{tenantId}/provisioning-sources` — B

Поля: `key`, `kind` (`scim`|`ldap`), `identityProvider`, `servicePrincipalId`,
`upstreamMode` (`off`|`scim`|`admin`|`auto`), `upstreamBaseUrl`,
`upstreamRealm`, `staleAfterSeconds` (60–2 592 000).

`201` → `{id, key, kind, identityProviderId, servicePrincipalId, upstreamMode,
status, staleAfterSeconds, lastSyncAt, stale}`.
Ошибки: `404 tenant_not_found`, `404 identity_provider_not_found`,
`409 population_managed_by_directory`, `404 principal_not_found`,
`422 service_account_required`, `422 service_principal_required`,
`409 provisioning_source_exists`.

### `GET /api/v1/tenants/{tenantId}/provisioning-sources` — B

`200` → массив источников с `stale`. Первое обнаружение устаревания
публикует `provisioning_source.stale`.

### SCIM 2.0: `/scim/v2/*`

Требует `Authorization: Bearer` с токеном audience `IAM_SCIM_AUDIENCE`,
`principal_type = service_account`, scope `IAM_SCIM_SCOPE` и активным
SCIM-источником для этого principal. Ответы — `application/scim+json`, с
`ETag`; мутации поддерживают `If-Match`. Поведение — в
[Федерация identity](federation.md).

| Код | Когда |
|---|---|
| 401 | нет Bearer-токена или он не для audience SCIM |
| 403 | не service account, нет scope, нет активного источника |
| 503 | population (identity provider) недоступна |
| 400 `invalidFilter`/`invalidSyntax`/`invalidPath`/`invalidValue`/`mutability` | ошибки запроса |
| 409 `uniqueness` | конфликт `externalId`/`userName`/группы |
| 502 | запись в upstream IdP невозможна |

## Журнал событий {#events}

### `GET /api/v1/events` — B

Query: `after` (sequence, по умолчанию 0), `limit` (1–500, по умолчанию 100).

```json
{
  "items": [
    {
      "sequence": 42,
      "id": "<event-id>",
      "tenant_id": "<tenant-id>",
      "type": "credential.revoked",
      "aggregate_type": "platform_access_token",
      "aggregate_id": "<credential-id>",
      "payload": {"credentialId": "…", "principalId": "…", "publicPrefix": "…",
                  "kind": "platform_access_token", "audiences": ["control-plane"],
                  "reason": "leaked"},
      "occurred_at": "…"
    }
  ],
  "next_after": null
}
```

- Порядок — по `sequence`; `next_after` не `null`, если есть ещё страницы:
  передайте его как `after`.
- Журнал общий для всех tenants инсталляции — фильтруйте по `tenant_id`.
- Payload содержит только идентификаторы и ограниченные метаданные.

Типы событий:

| Группа | Типы |
|---|---|
| Tenants и principals | `tenant.created`, `principal.created`, `principal.disabled` |
| Identities | `external_identity.linked`, `identity_provider.registered` |
| Группы | `group.created`, `group.deleted`, `group_membership.added`, `group_membership.removed` |
| Audiences | `audience.created`, `audience.updated` |
| Credentials | `platform_access_token.issued`, `platform_access_token.rotated`, `legacy_credential.imported`, `credential.revoked`, `service_account.created` |
| Провижининг | `provisioning_source.registered`, `provisioning_source.stale`, `scim_user.provisioned`, `scim_user.updated`, `scim_user.deprovisioned` |

Журнал читают потребители identity-событий (например, проекция
внешнего PDP) — это основа revocation-проекций на стороне сервисов.

## Audit

Помимо журнала событий IAM ведёт таблицу `audit_events` (действие, actor,
ресурс, `allowed`/`denied`, причина) — в том числе для отказов, которые
клиенту видны только как `invalid_token`. API чтения audit нет; audit
читается из базы IAM. Коды действий: `tenants.create`, `principals.create`,
`external_identities.link`, `identity_providers.create`, `audiences.update`,
`service_accounts.create`, `service_accounts.revoke`, `tokens.exchange`,
`authentication_contexts.record`, `platform_access_tokens.issue|rotate|revoke|exchange|introspect`,
`legacy_credentials.import`, `federation.authenticate`, `federation.exchange`,
`federation.identity_adopted`, `federation.subject_rotated`,
`provisioning_sources.register`, `provisioning_sources.stale_detected`,
`scim.users.*`, `scim.groups.*`.

## См. также

- [Tenants и principals](principals.md)
- [Credentials и PAT](credentials.md)
- [Токены, audiences, scopes](tokens.md)
- [Коды ошибок](../reference/errors.md)
- [Сервисы и порты](../reference/services-and-ports.md)

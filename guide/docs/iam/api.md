
# IAM API

The complete reference for the `iam-service` HTTP API: endpoints, the
authentication method, request and response bodies, and error codes. It is for
integrators and administrators. The concepts are described in the other
articles of this section; this page is the contract.

## General information

| | |
|---|---|
| Internal address | `http://iam-service:8010` (compose network) |
| Host address | `http://127.0.0.1:${IAM_HOST_PORT:-18010}` |
| Public address | `${TAIMEN_PUBLIC_URL}/iam` (Caddy strips the `/iam` prefix) |
| Format | JSON; SCIM uses `application/scim+json` |
| OpenAPI | `GET /openapi.json`, interactive at `GET /docs` (FastAPI defaults) |

### Authentication

| Method | Header / body | Where |
|---|---|---|
| Bootstrap | `X-IAM-Bootstrap-Token: <IAM_BOOTSTRAP_TOKEN>` | all administrative endpoints (marked **B**) |
| Presenting a PAT | `token` field in the body | `platform-access-tokens:exchange`, `:introspect`, `:revoke-self` |
| Client credentials | `clientId`, `clientSecret` fields in the body | `tokens/exchange` |
| IdP upstream token | `token` field in the body | `federation:authenticate`, `federation:exchange` |
| Bearer access token for audience `iam-scim` | `Authorization: Bearer …` | `/scim/v2/*` |
| No authentication | — | `/healthz`, `/.well-known/jwks.json` |

A wrong or empty bootstrap header returns `401 {"detail":"unauthorized"}`.
If `IAM_BOOTSTRAP_TOKEN` is not set, all administrative endpoints are closed.

### Error format

```json
{"detail": "scope_not_allowed"}
```

`detail` is a stable machine code. Body validation errors (extra field, wrong
pattern, empty string) are the standard FastAPI `422` response with a list in
`detail`. SCIM returns errors in the RFC 7644 format.

### Field case

- Requests accept fields in camelCase (`displayName`, `allowedScopes`,
  `scopeCeiling`, `expiresInSeconds`).
- Responses for tenant, principal, audience, group, identity provider,
  external identity, and the event log are in **snake_case** (`display_name`,
  `allowed_scopes`, `created_at`).
- Responses for PAT, token exchanges, federation, service account, and
  authentication context are in **camelCase**.

## Summary table

| Method and path | Auth | Purpose |
|---|---|---|
| `GET /healthz` | — | Liveness |
| `GET /.well-known/jwks.json` | — | Public signing key |
| `POST /api/v1/tenants` | B | Create a tenant |
| `GET /api/v1/events` | B | Event log (outbox) |
| `POST /api/v1/tenants/{tenantId}/principals` | B | Create a principal |
| `GET /api/v1/tenants/{tenantId}/principals/{principalId}` | B | Read a principal |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}:disable` | B | Disable a principal and revoke its PATs |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}/external-identities` | B | Link an external identity |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}/authentication-contexts` | B | Record a human sign-in |
| `POST /api/v1/tenants/{tenantId}/principals/{principalId}/platform-access-tokens` | B | Issue a PAT |
| `GET /api/v1/tenants/{tenantId}/platform-access-tokens` | B | List PATs |
| `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:revoke` | B | Revoke a PAT |
| `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:rotate` | B | Rotate a PAT |
| `POST /api/v1/tenants/{tenantId}/legacy-credentials:import` | B | Import a Control Plane key |
| `POST /api/v1/platform-access-tokens:exchange` | PAT | PAT → access token |
| `POST /api/v1/platform-access-tokens:introspect` | PAT | PAT details |
| `POST /api/v1/platform-access-tokens:revoke-self` | PAT | Revocation by the owner |
| `POST /api/v1/tenants/{tenantId}/audiences` | B | Create an audience |
| `GET /api/v1/tenants/{tenantId}/audiences` | B | List audiences |
| `PATCH /api/v1/tenants/{tenantId}/audiences/{key}` | B | Replace `allowedScopes` |
| `POST /api/v1/tenants/{tenantId}/service-accounts` | B | Create a service account |
| `POST /api/v1/tenants/{tenantId}/service-accounts/{clientId}:revoke` | B | Revoke a service account |
| `POST /api/v1/tokens/exchange` | client credentials | Client credentials → access token |
| `POST /api/v1/tenants/{tenantId}/groups` | B | Create a group |
| `POST /api/v1/tenants/{tenantId}/groups/{groupId}/members` | B | Add a member |
| `POST /api/v1/tenants/{tenantId}/identity-providers` | B | Register an IdP |
| `POST /api/v1/tenants/{tenantId}/federation:authenticate` | upstream | Confirm a sign-in |
| `POST /api/v1/tenants/{tenantId}/federation:exchange` | upstream | Sign-in + access token |
| `POST /api/v1/tenants/{tenantId}/provisioning-sources` | B | Register a SCIM/LDAP source |
| `GET /api/v1/tenants/{tenantId}/provisioning-sources` | B | Sources and their staleness |
| `GET`, `POST` `/scim/v2/Users`; `GET`, `PUT`, `PATCH`, `DELETE` `/scim/v2/Users/{id}` | SCIM | Users |
| `GET`, `POST` `/scim/v2/Groups`; `GET`, `PUT`, `PATCH`, `DELETE` `/scim/v2/Groups/{id}` | SCIM | Groups |
| `GET /scim/v2/ServiceProviderConfig`, `/ResourceTypes`, `/Schemas` | SCIM | SCIM discovery |

!!! danger "Administrative endpoints are also reachable through the edge"
    The shipped Caddyfiles proxy the whole `/iam/*` path, including the
    endpoints with the bootstrap header. Only the secret protects them. In a
    production installation, consider restricting these paths at the edge
    (allow from outside only `/.well-known/jwks.json`, `:exchange`,
    `:introspect`, `:revoke-self`, `tokens/exchange`, `federation:*`, and
    `/scim/v2`); see [Edge and TLS](../operations/edge-and-tls.md).

## Service endpoints

### `GET /healthz`

```json
{"status": "ok"}
```

Does not check the database.

### `GET /.well-known/jwks.json`

```json
{"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "local-dev", "n": "…", "e": "AQAB"}]}
```

A single current key. Without a configured signing key, `500`. See
[JWKS and the signing key](tokens.md).

## Tenants

### `POST /api/v1/tenants` — B

| Field | Type | Required | Rules |
|---|---|---|---|
| `slug` | string | yes | `^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$` |
| `name` | string | yes | 1–200 |
| `id` | UUID | no | explicit tenant identifier |

`201` → `{id, slug, name, status, created_at}`.
Errors: `409 tenant_id_exists`, `409 tenant_slug_exists`.

## Principals

### `POST /api/v1/tenants/{tenantId}/principals` — B

```json
{"kind": "agent", "displayName": "Coding Runner"}
```

`kind` ∈ `human`, `agent`, `service_account`, `workload`; `displayName` 1–200.
`201` → `{id, kind, display_name, status, created_at}`.
Errors: `404 tenant_not_found`.

### `GET /api/v1/tenants/{tenantId}/principals/{principalId}` — B

`200` → principal. `404 principal_not_found` if there is no active membership.

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}:disable` — B

Query: `reason` (≤ 200, `principal_disabled` by default).
`200` → `{"principalId", "status": "disabled", "revokedCredentials": <n>}`.
Errors: `404 principal_not_found`. A repeated call again returns `200`
(`revokedCredentials: 0`).

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}/external-identities` — B

```json
{"issuer": "https://idp.example.com/realms/corp", "subject": "<sub>"}
```

`201` → `{id, principal_id, issuer, subject, status, created_at}`.
Errors: `404 principal_not_found`, `409 identity_provider_managed`,
`409 external_identity_exists`.

## Authentication contexts and PAT {#pat}

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}/authentication-contexts` — B

| Field | Type | Required |
|---|---|---|
| `issuer` | string (1–500) | yes |
| `acr` | string (≤ 200) | no |
| `amr` | string[] | no |
| `authTime` | datetime | no |
| `externalIdentityId` | UUID | no |

`201` → `{id, principalId, issuer, acr, amr, authTime, recordedAt, source: "bootstrap"}`.
Errors: `404 tenant_not_found`, `404 principal_not_found`,
`409 principal_not_active`, `422 human_principal_required`.

### `POST /api/v1/tenants/{tenantId}/principals/{principalId}/platform-access-tokens` — B

Header: `Idempotency-Key` (required).

| Field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | yes | 1–200 |
| `audiences` | string[] | yes | ≥ 1, active audiences of the tenant |
| `scopeCeiling` | string[] | no | ⊆ the union of the audiences' `allowedScopes` |
| `expiresInSeconds` | int | no | ≥ 60, ≤ `IAM_PAT_MAX_TTL_SECONDS` |

`201` → `{"credential": PlatformAccessTokenView, "token": "iam_pat_…"}`.
Repeat with the same key: `201`, `token: null`, header `Idempotency-Replayed: true`.

Errors: `400 idempotency_key_required`, `403 authentication_context_required`,
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

Query: `principalId` (UUID, optional), `includeRevoked` (bool, `false` by
default). `200` → `PlatformAccessTokenView[]`, ordered by `createdAt`.

### `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:revoke` — B

Query: `reason` (≤ 200, `revoked` by default). `204`. Idempotent.
Errors: `404 credential_not_found`.

### `POST /api/v1/tenants/{tenantId}/platform-access-tokens/{credentialId}:rotate` — B

Header: `Idempotency-Key`. Body: `{}` (any fields are rejected).
`201` → `{"credential": …, "token": "iam_pat_…"}`: a successor with the same
`audiences`, `scopeCeiling`, and `expiresAt`; the predecessor is revoked with
`revokeReason: "rotated"`.
Errors: `400 idempotency_key_required`, `404 credential_not_found`,
`409 credential_not_active`, `404 tenant_not_found`, `404 principal_not_found`,
`409 principal_not_active`, `409 credential_conflict`.

### `POST /api/v1/tenants/{tenantId}/legacy-credentials:import` — B

| Field | Rules |
|---|---|
| `principalId` | active member of the tenant |
| `name` | 1–200 |
| `keyPrefix` | 12 hex characters |
| `keyHash` | 64 hex characters (SHA-256 of the full key) |
| `audience` | active audience |
| `scopeCeiling` | ⊆ the audience's `allowedScopes` |
| `expiresInSeconds` | ≥ 60, ≤ `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS` |

`201` → `PlatformAccessTokenView` (`kind: legacy_control_plane_api_key`).
Errors: `422 invalid_credential_material`, `422 compatibility_window_too_long`,
`422 unknown_audience`, `422 invalid_scope_ceiling`, `409 credential_exists`.

### `POST /api/v1/platform-access-tokens:exchange`

```json
{"token": "iam_pat_…", "audience": "control-plane", "scopes": ["control-plane:read"]}
```

`200` → `{accessToken, tokenType: "Bearer", expiresIn, audience, scope, sessionId}`.
Errors: `401 invalid_token`, `403 audience_not_allowed`, `403 scope_not_allowed`.

### `POST /api/v1/platform-access-tokens:introspect`

```json
{"token": "iam_pat_…"}
```

`200` → `{tenantId, principalId, principalKind, displayName, credentialId,
name, publicPrefix, audiences, scopeCeiling, expiresAt, issuedAt}`.
Errors: `401 invalid_token`.

### `POST /api/v1/platform-access-tokens:revoke-self`

```json
{"token": "iam_pat_…", "reason": "logout"}
```

`reason` ≤ 200, `logout` by default. `204`. A repeat gives `401 invalid_token`.

## Audiences

### `POST /api/v1/tenants/{tenantId}/audiences` — B

```json
{"key": "reports", "allowedScopes": ["reports:read", "reports:write"]}
```

`key`: `^[a-z0-9][a-z0-9._-]{1,118}[a-z0-9]$`; a scope is 1–120 characters.
`201` → `{id, tenant_id, key, allowed_scopes, status}`.
Errors: `404 tenant_not_found`, `409 audience_exists`, `422 invalid_scope`.

### `GET /api/v1/tenants/{tenantId}/audiences` — B

`200` → array of audiences, ordered by `key`. `404 tenant_not_found`.

### `PATCH /api/v1/tenants/{tenantId}/audiences/{key}` — B

```json
{"allowedScopes": ["reports:read", "reports:write", "reports:admin"]}
```

Replaces the list entirely; with no change, it is a no-op. `200` → audience.
Errors: `404 audience_not_found`, `422 invalid_scope`.

## Service accounts {#service-accounts}

### `POST /api/v1/tenants/{tenantId}/service-accounts` — B

```json
{"displayName": "Reports Service", "audiences": ["memory-service"], "scopeCeiling": ["memory:read"]}
```

`201` → `{"principalId", "clientId": "iam_sa_…", "clientSecret"}`; the secret is shown once.
Errors: `422 unknown_audience`.

### `POST /api/v1/tenants/{tenantId}/service-accounts/{clientId}:revoke` — B

`204`, idempotent. Errors: `404 service_account_not_found`.

### `POST /api/v1/tokens/exchange`

```json
{"clientId": "iam_sa_…", "clientSecret": "…", "audience": "memory-service", "scopes": ["memory:read"]}
```

`200` → `{accessToken, tokenType: "Bearer", expiresIn}`.
Errors: `401 invalid_client`, `403 audience_not_allowed`, `403 scope_not_allowed`.

## Groups

### `POST /api/v1/tenants/{tenantId}/groups` — B

```json
{"key": "operators", "name": "Operators"}
```

`201` → `{id, tenant_id, key, name, status}`.
Errors: `404 tenant_not_found`, `409 group_exists`.

### `POST /api/v1/tenants/{tenantId}/groups/{groupId}/members` — B

```json
{"principalId": "<principal-id>"}
```

`201` → `{id, tenant_id, group_id, principal_id}`.
Errors: `404 group_not_found`, `409 group_is_federated`,
`404 principal_not_found`, `409 group_membership_exists`.

## Federation {#federation}

### `POST /api/v1/tenants/{tenantId}/identity-providers` — B

Fields: `key`, `issuer`, `audience` (required), `jwksUri`, `subjectClaim`,
`externalIdClaim`, `groupClaim`, `groupMappings`, `requiredAcrValues`,
`requiredAmrValues`, `lifecycleProfile` (`read_only`|`managed`),
`jwksCacheTtlSeconds`, `jwksStaleGraceSeconds`; see
[Identity federation](federation.md). Extra fields are rejected.

`201` → `{id, tenant_id, key, issuer, audience, jwks_uri, subject_claim,
external_id_claim, group_claim, group_mappings, required_acr_values,
required_amr_values, lifecycle_profile, status}`.
Errors: `404 tenant_not_found`, `422 invalid_issuer`, `409 identity_provider_exists`.

### `POST /api/v1/tenants/{tenantId}/federation:authenticate`

```json
{"identityProvider": "corp-idp", "token": "<IdP access token>"}
```

`200` → `{principalId, identityProvider, groups, authenticationContext: {acr, amr, authTime}, identityProviderStale}`.

### `POST /api/v1/tenants/{tenantId}/federation:exchange`

```json
{"identityProvider": "corp-idp", "token": "<IdP access token>", "audience": "control-plane", "scopes": []}
```

`200` → `{accessToken, tokenType, expiresIn, audience, scope, sessionId,
principalId, identityProvider, groups, authenticationContext, identityProviderStale}`.

Errors for both endpoints are listed in the table in
[Identity federation](federation.md#federation-errors); in addition, for
`exchange`: `422 human_principal_required`, `403 audience_not_allowed`,
`403 scope_not_allowed`.

## Provisioning

### `POST /api/v1/tenants/{tenantId}/provisioning-sources` — B

Fields: `key`, `kind` (`scim`|`ldap`), `identityProvider`, `servicePrincipalId`,
`upstreamMode` (`off`|`scim`|`admin`|`auto`), `upstreamBaseUrl`,
`upstreamRealm`, `staleAfterSeconds` (60–2,592,000).

`201` → `{id, key, kind, identityProviderId, servicePrincipalId, upstreamMode,
status, staleAfterSeconds, lastSyncAt, stale}`.
Errors: `404 tenant_not_found`, `404 identity_provider_not_found`,
`409 population_managed_by_directory`, `404 principal_not_found`,
`422 service_account_required`, `422 service_principal_required`,
`409 provisioning_source_exists`.

### `GET /api/v1/tenants/{tenantId}/provisioning-sources` — B

`200` → array of sources with `stale`. The first detection of staleness
publishes `provisioning_source.stale`.

### SCIM 2.0: `/scim/v2/*`

Requires `Authorization: Bearer` with a token for audience `IAM_SCIM_AUDIENCE`,
`principal_type = service_account`, scope `IAM_SCIM_SCOPE`, and an active SCIM
source for this principal. Responses are `application/scim+json`, with an
`ETag`; mutations support `If-Match`. The behavior is described in
[Identity federation](federation.md).

| Code | When |
|---|---|
| 401 | no Bearer token, or it is not for the SCIM audience |
| 403 | not a service account, no scope, no active source |
| 503 | the population (identity provider) is unavailable |
| 400 `invalidFilter`/`invalidSyntax`/`invalidPath`/`invalidValue`/`mutability` | request errors |
| 409 `uniqueness` | `externalId`/`userName`/group conflict |
| 502 | writing to the upstream IdP is impossible |

## Event log {#events}

### `GET /api/v1/events` — B

Query: `after` (sequence, 0 by default), `limit` (1–500, 100 by default).

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

- Ordering is by `sequence`; `next_after` is not `null` if there are more
  pages: pass it as `after`.
- The log is shared by all tenants of the installation; filter by `tenant_id`.
- The payload contains only identifiers and limited metadata.

Event types:

| Group | Types |
|---|---|
| Tenants and principals | `tenant.created`, `principal.created`, `principal.disabled` |
| Identities | `external_identity.linked`, `identity_provider.registered` |
| Groups | `group.created`, `group.deleted`, `group_membership.added`, `group_membership.removed` |
| Audiences | `audience.created`, `audience.updated` |
| Credentials | `platform_access_token.issued`, `platform_access_token.rotated`, `legacy_credential.imported`, `credential.revoked`, `service_account.created` |
| Provisioning | `provisioning_source.registered`, `provisioning_source.stale`, `scim_user.provisioned`, `scim_user.updated`, `scim_user.deprovisioned` |

The log is read by consumers of identity events (for example, an external
PDP's projection); it is the basis of revocation projections on the service side.

## Audit

Besides the event log, IAM keeps the `audit_events` table (action, actor,
resource, `allowed`/`denied`, reason), including refusals that the client sees
only as `invalid_token`. There is no API to read the audit; it is read from
the IAM database. Action codes: `tenants.create`, `principals.create`,
`external_identities.link`, `identity_providers.create`, `audiences.update`,
`service_accounts.create`, `service_accounts.revoke`, `tokens.exchange`,
`authentication_contexts.record`, `platform_access_tokens.issue|rotate|revoke|exchange|introspect`,
`legacy_credentials.import`, `federation.authenticate`, `federation.exchange`,
`federation.identity_adopted`, `federation.subject_rotated`,
`provisioning_sources.register`, `provisioning_sources.stale_detected`,
`scim.users.*`, `scim.groups.*`.

## See also

- [Tenants and principals](principals.md)
- [Credentials and PAT](credentials.md)
- [Tokens, audiences, scopes](tokens.md)
- [Error codes](../reference/errors.md)
- [Services and ports](../reference/services-and-ports.md)

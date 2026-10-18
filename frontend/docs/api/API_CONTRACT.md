# KORA API Contract

_Backend state as of Milestone 8B plus the member lookup addition (2026-10-15). Sources: the mounted route tree, the generated OpenAPI schema, the route handlers and services, and their tests. This document describes implemented behavior only; where code and OpenAPI disagree, the code is described and the difference is listed in [§15](#15-known-discrepancies-and-observations)._

All 81 API operations are listed here. Every mounted route is in OpenAPI, apart from the documentation routes themselves (`/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`), which exist only in `local`/`test` (§1.7). Coverage is checked by `tests/test_release_readiness.py::test_openapi_documents_exactly_the_mounted_routes`.

**Contents**

1. [Conventions](#1-conventions)
2. [Authentication, sessions and CSRF](#2-authentication-sessions-and-csrf)
3. [Authorization model](#3-authorization-model)
4. [Enums](#4-enums)
5. [Health](#5-health)
6. [Auth and own access](#6-auth-and-own-access-apiv1auth-apiv1access)
7. [System Admin: permissions, overrides, effective access, grants](#7-system-admin-permissions-overrides-effective-access-grants-apiv1admin)
8. [Organization: units and Members](#8-organization)
9. [Tasks and weekly series](#9-tasks-and-weekly-series)
10. [Announcements](#10-announcements-apiv1announcements)
11. [Notifications](#11-notifications-apiv1notifications)
12. [Calendar](#12-calendar-apiv1calendar)
13. [Audit log](#13-audit-log-apiv1adminaudit-records)
14. [Cross-module integration rules](#14-cross-module-integration-rules)
15. [Known discrepancies and observations](#15-known-discrepancies-and-observations)
16. [Endpoint index](#16-endpoint-index)

---

## 1. Conventions

### 1.1 Base path and format
- Every API route is under `/api/v1`. Request and response bodies are JSON (`application/json`), except that `204` responses have no body.
- **IDs** are UUID strings.
- **Timestamps** are ISO 8601 date-times. Responses are always UTC. Inputs that carry a time (`due_at`, `first_due_at`, `ends_at`, `starts_at`, the calendar's `from`/`to`, `as_of`, and the audit time filters) **must include a UTC offset**; naive values are rejected with `422`. Inputs are converted to UTC.
- **Strings:** text fields marked "trimmed" have leading and trailing whitespace removed before the length is checked. A value that is blank after trimming fails `min_length` (422).
- **Partial updates** (`PATCH`): only the fields you send change. Sending `null` clears an optional field. Sending `null` for a required field is rejected (`422`).
- **Unknown JSON fields** are ignored (Pydantic default), with two exceptions: `OverrideRequest` rejects any unknown field (422), and a calendar event update rejects `scope_unit_id` (422).

### 1.2 Error format
All errors are `{"detail": ...}`.

| Status | When | `detail` |
|---|---|---|
| 401 | No session, or an unknown, revoked or expired session | `"Not authenticated."` |
| 401 | Sign-in failure (always the same, whatever the cause) | `"Invalid username or password."` |
| 403 | Unsafe method without a matching `X-CSRF-Token` | `"CSRF token missing or invalid."` |
| 403 | The account still has a temporary password | `"Password change required."` |
| 403 | A System Admin–only route, called by anyone else | `"System Admin authority required."` |
| 403 | A permission or visibility denial | `"Not permitted."` |
| 404 | The resource is not found (see each module for 403-vs-404 behavior) | a string, e.g. `"Not found."` |
| 405 | The method is not allowed on the path | `"Method Not Allowed"` |
| 409 | The resource's current state prevents the operation | a human-readable string |
| 422 | Request validation (schema) | a **list** of `{type, loc, msg, ctx?}`. Submitted values (`input`) are **never** echoed |
| 422 | A business-rule violation | a human-readable **string** |
| 429 | Sign-in locked out | `"Too many failed sign-in attempts. Try again later."`, with a `Retry-After: <seconds>` header |

There is no machine-readable error code; clients should branch on the status code. In OpenAPI, every error other than 422 uses the `ErrorResponse` schema, and every 422 uses `ValidationErrorResponse` (`detail`: a list of issues, or a string).

### 1.3 Pagination
Only the audit list (§13) is paginated: a cursor plus `limit`. **Every other list returns the full result set**, filtered to what the caller may see, in the documented order.

### 1.4 Visibility and denial semantics
- Lists **omit** items the caller cannot see; they never return 403 for them.
- Direct access to an item the caller cannot see returns **403 `"Not permitted."`**.
- Where an existing item is checked before permissions, an unknown ID returns 404. The exceptions are noted per module; organization units, for example, check permission first, so an unknown unit returns 403.

### 1.5 Methods
State changes use `POST`, `PUT` or `PATCH`. **No `DELETE` method is used anywhere.** Deletions and endings are `POST .../delete`, `.../end`, `.../remove`, `.../cancel`, `.../withdraw`, `.../archive` or `.../stop`, and they are soft or historical; nothing is hard-deleted.

### 1.6 CORS
No CORS middleware is configured. Browsers can call the API only from the same origin.

### 1.7 API docs
`/docs`, `/redoc` and `/openapi.json` exist only when `KORA_ENVIRONMENT` is `local` or `test`. They are always absent (404) in `staging` and `production`, and no setting changes that.

---

## 2. Authentication, sessions and CSRF

### 2.1 Cookies
A successful sign-in or password change sets two cookies (both `Secure`; HTTPS is required outside `localhost`). Both expire when the session reaches its absolute expiry.

| Cookie | Attributes | Purpose |
|---|---|---|
| `kora_session` | `HttpOnly; Secure; SameSite=Lax; Path=/api` | An opaque session token. It is **never** included in a response body. |
| `kora_csrf` | `Secure; SameSite=Strict; Path=/` (readable by JS) | The CSRF token. It is not a secret and is also returned as `csrf_token` in the body. |

Sessions are stored server-side; only SHA-256 hashes of the tokens are kept. A session ends after **8 hours idle** or **7 days** absolute. Password change, sign-out-all and account deactivation revoke sessions.

### 2.2 CSRF
Every authenticated request with an unsafe method (anything except `GET`, `HEAD` or `OPTIONS`) must send the header `X-CSRF-Token: <csrf_token>` matching the session. Sign-in is the only unsafe route that needs neither a session nor CSRF.

### 2.3 Route guards
| Guard | Used by | Requires |
|---|---|---|
| none | `GET /health`, `POST /auth/sign-in` | — |
| `AuthenticatedSession` | `POST /auth/sign-out`, `POST /auth/sign-out-all`, `GET /auth/me`, `POST /auth/change-password` | a live session (a temporary password is allowed) |
| `CurrentAccount` / `CurrentAccess` | every other non-admin route | a live session **and** a non-temporary password (otherwise 403 `"Password change required."`) |
| `SystemAdmin` | every route under `/api/v1/admin` | `CurrentAccount` plus an active System Admin grant (otherwise 403 `"System Admin authority required."`) |

Guard order: session (401), then CSRF on unsafe methods (403), then the temporary-password gate (403), then System Admin (403), then the handler's own permission checks (403).

### 2.4 Temporary passwords
Accounts created by bootstrap or provisioning, or reset by an admin, have a random temporary password that expires after **7 days**. While the password is temporary, only the `AuthenticatedSession` routes work. An expired temporary password cannot sign in (generic 401).

### 2.5 Sign-in throttle
5 failures for the same normalized username within 15 minutes lock that username for 15 minutes (`429` + `Retry-After`). This applies to unknown usernames too. Usernames are case-insensitive: they are trimmed and lowercased, and must match `[a-z0-9._-]{3,64}`. An invalid username simply fails sign-in (401).

---

## 3. Authorization model

### 3.1 Permissions catalog
`organization.manage`, `task.view`, `task.create`, `task.manage`, `announcement.publish`, `announcement.manage`, `calendar.create`, `calendar.manage`.

### 3.2 How a decision is made (per permission and unit)
1. The unit chain runs from the unit up to KORA (current structure, or historical with `as_of`).
2. Walking from the unit upward, the **first unit that has an override** for the account and permission decides: deny beats grant at the same unit.
3. Otherwise a **role default** applies if the account is an active Member whose open role grants the permission and whose role unit is on the chain. The role covers its unit and everything beneath it.
4. Otherwise the permission is denied.

A deactivated account gets nothing. **System Admin authority is never consulted** and grants no operational access (§3.4). Overrides apply to any active account, Member or not.

### 3.3 Seeded role defaults
| Permission | Roles |
|---|---|
| `organization.manage` | Event/Project Leader, Deputy Leader |
| `task.view`, `task.create`, `calendar.create` | every role |
| `task.manage`, `announcement.publish`, `announcement.manage`, `calendar.manage` | every role except PMO Member and Member |

Each default applies at the role's unit: KORA for the Event/Project Leader and Deputy Leader, the PMO for PMO roles, the Administration for an Administration Manager, and the current Team for Team Leaders and Members.

### 3.4 System Admin
System Admin is a separate grant, not a role. It authorizes only `/api/v1/admin/*`. It gives **no** access to units, tasks, announcements, events or notifications unless the admin gives an account (possibly their own) an explicit override. The final active System Admin can be neither deactivated nor revoked.

### 3.5 "Within scope" (Members)
A Member is within a unit's scope if their current Team placement **or** their role's unit is that unit or lies beneath it. This rule decides who is eligible as an assignee, recipient or invitee. **Exception (tasks only):** the Event Leader, Deputy and PMO Leader are never regular task assignees; they, or any active Member outside the scope, can be assigned only through "Other" (`external_assignee_member_ids`, or `external: true` on `POST /tasks/{id}/assignees`). Regular assignees that are top roles get **422** `"The Event Leader, Deputy and PMO Leader can only be assigned through 'Other'."`. External assignees stay assigned when the scope check runs.

---

## 4. Enums

| Enum | Values |
|---|---|
| `UnitKind` | `organization`, `pmo`, `administration`, `team` |
| `UnitStatus` | `active`, `archived` |
| `MemberStatus` | `active`, `deactivated` |
| `RoleKey` | `event_project_leader`, `deputy_leader`, `pmo_leader`, `pmo_member`, `administration_manager`, `team_leader`, `member` |
| `Permission` | see §3.1 |
| `OverrideEffect` | `grant`, `deny` |
| `DecisionSource` | `override_deny`, `override_grant`, `role_default`, `none` |
| `TaskStatus` | `new`, `in_progress`, `completed`, `cancelled` |
| `TaskPriority` | `low`, `normal`, `high`, `urgent` |
| `SeriesStatus` | `active`, `stopped` |
| Assignment end reason (history data) | `removed`, `member_inactive`, `out_of_scope`, `series_update` |
| `AnnouncementState` | `draft`, `published`, `withdrawn` |
| `NotificationCategory` | `task_assignment`, `task_update`, `task_comment`, `announcement_new`, `announcement_change`, `calendar_event` |
| `CalendarEventType` | `event`, `meeting` |
| `CalendarEventState` | `scheduled`, `cancelled` |

Fixed IDs: KORA `6b0a0000-0000-4000-8000-000000000001`; the PMO is also seeded with a fixed ID (`organization/constants.py`).

Role unit kinds: `event_project_leader` and `deputy_leader` belong to the organization (KORA); `pmo_leader` and `pmo_member` to the PMO; `administration_manager` to an Administration (`administration_id` required); `team_leader` and `member` to their Team.

---

## 5. Health

### `GET /api/v1/health`
No authentication and no database. **200** `{"status": "ok"}`.

---

## 6. Auth and own access (`/api/v1/auth`, `/api/v1/access`)

**Schemas**
- `AccountResponse`: `id` uuid, `username` string, `must_change_password` bool, `is_system_admin` bool, `member_id` uuid|null (the Member record linked to the account; **null for accounts that are not Members**, e.g. the bootstrap System Admin). Also present inside `SessionResponse.account`.
- `SessionResponse`: `account` AccountResponse, `csrf_token` string.

### `POST /api/v1/auth/sign-in` — public, no CSRF
Body `SignInRequest`: `username` string (1–256), `password` string (1–1024). The loose bounds are deliberate: format problems produce the generic 401, not a 422.
- **200** `SessionResponse`. It sets both cookies, clears the username's throttle, and rehashes the password if the hash parameters are outdated.
- **401** generic failure: unknown user, wrong password, deactivated account or expired temporary password. **429** when locked out. **422** when a field is missing or out of bounds.

### `POST /api/v1/auth/sign-out` — AuthenticatedSession + CSRF
**204**. Revokes the current session and clears both cookies.

### `POST /api/v1/auth/sign-out-all` — AuthenticatedSession + CSRF
**204**. Revokes every session of the account and clears the cookies.

### `GET /api/v1/auth/me` — AuthenticatedSession
**200** `AccountResponse`. Works with a temporary password.

### `POST /api/v1/auth/change-password` — AuthenticatedSession + CSRF
Body `ChangePasswordRequest`: `current_password` string (1–1024), `new_password` string (8–128; no composition rules).
- **200** `SessionResponse`. Clears the temporary flag, **revokes all sessions** (including the current one) and issues a fresh session with new cookies and a new `csrf_token`.
- **400** `"Current password is incorrect."` (also when the temporary password has expired). **422** policy or schema violation.

### `GET /api/v1/access/me` — CurrentAccount
**200** `EffectiveAccessResponse` for the caller, now (§7.4).

---

## 7. System Admin: permissions, overrides, effective access, grants (`/api/v1/admin`)

Every route here requires **SystemAdmin** (§2.3). A test asserts that every `/admin` route rejects non-admins.

### 7.1 Catalog and role defaults
- `PermissionResponse`: `key`, `description`.
- `RoleDefaultResponse`: `id`, `role_key`, `permission` (string), `valid_from`, `valid_to|null`, `created_by_account_id|null` (null for rows seeded by migration), `ended_by_account_id|null`.

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /admin/permissions` | — | 200 `PermissionResponse[]`, by key | — |
| `GET /admin/role-defaults` | — | 200 `RoleDefaultResponse[]`, by role then `valid_from`; includes ended rows | — |
| `POST /admin/role-defaults` | `{role_key: string, permission: Permission}` | 201 `RoleDefaultResponse` | 422 `"Unknown role."`; 409 `"That default is already in force."` |
| `POST /admin/role-defaults/{default_id}/end` | — | 200 `RoleDefaultResponse` (with `valid_to` set) | 404; 409 `"The default has already ended."` |

Defaults are history rows: ending one closes it, and nothing is deleted.

### 7.2 Overrides
- `OverrideResponse`: `id`, `account_id`, `permission`, `unit_id`, `effect`, `reason`, `valid_from`, `valid_to|null`, `created_by_account_id`, `ended_by_account_id|null`.

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /admin/accounts/{account_id}/overrides` | — | 200 `OverrideResponse[]` (all, by `valid_from`) | 404 account |
| `POST /admin/accounts/{account_id}/overrides` | `OverrideRequest`: `permission` Permission, `unit_id` uuid, `effect` OverrideEffect, `reason` string (trimmed, 1–1000) | 201 | 404 account; 409 `"The account is not active."`; 422 `"Unit not found or not active."`; 409 `"An identical override is already in force."` |
| `POST /admin/overrides/{override_id}/end` | — | 200 | 404; 409 `"The override has already ended."` |

Overrides have no expiry: `OverrideRequest` forbids unknown fields, so sending e.g. `valid_to` returns 422. Any active account can be the target, including the caller's own; this is how the first structure is set up.

### 7.3 System Admin grants
- `SystemAdminResponse`: `account_id`, `username`, `granted_at`, `granted_by_account_id|null` (null for the bootstrap grant).

| Method & path | Success | Errors |
|---|---|---|
| `GET /admin/system-admins` | 200 `SystemAdminResponse[]` (active grants, by username) | — |
| `POST /admin/accounts/{account_id}/system-admin` | 201 `SystemAdminResponse` | 404 `"Account not found."`; 409 `"The account is not active."` / `"Already a System Admin."` |
| `POST /admin/accounts/{account_id}/system-admin/revoke` | 204 | 404 `"Not a System Admin."`; 409 `"The final System Admin cannot be revoked."` |

There is **no HTTP bootstrap**. The first System Admin is created only with the CLI `python -m kora_api.access.bootstrap <username>`, which runs once ever.

### 7.4 Effective access
`GET /admin/accounts/{account_id}/effective-access?as_of=<datetime with offset>`
- `as_of` is optional (default now). When given, the decision uses the account status, structure, assignments, defaults and overrides **valid at that time**. A naive `as_of` returns 422 `"as_of must include a time zone offset."`; an unknown account returns 404.
- **200** `EffectiveAccessResponse`: `account_id`, `at`, `permissions[]`. Each item is `{permission, units[]}`, where every unit is `UnitDecisionResponse {unit_id, name, kind, allowed, source: DecisionSource, decided_at_unit_id|null}`. The list covers every catalog permission × every unit, ordered by depth then name.

---

## 8. Organization

### 8.1 Units (`/api/v1/organization/units`) — CurrentAccess, `organization.manage`
`UnitResponse`: `id`, `kind` UnitKind, `name`, `status` UnitStatus, `parent_id|null` (the current parent), `archived_at|null`.

| Method & path | Body | Permission | Success |
|---|---|---|---|
| `GET /organization/units` | — | lists only the units where the caller has `organization.manage` | 200 `UnitResponse[]` (by kind, then name) |
| `GET /organization/units/{unit_id}` | — | `organization.manage` on the unit | 200 |
| `POST /organization/units` | `CreateUnitRequest`: `kind` UnitKind, `name` string (trimmed, 1–200), `parent_id` uuid | `organization.manage` on the parent | 201 |
| `POST /organization/units/{unit_id}/move` | `MoveTeamRequest`: `administration_id` uuid | `organization.manage` on the Team **and** the destination | 200 |
| `POST /organization/units/{unit_id}/archive` | — | `organization.manage` on the unit | 200 |

Rules (422 = structure violation, 409 = state conflict):
- **Create.** An `administration` must sit directly under KORA. A `team` must sit under an **active** Administration. Other kinds cannot be created (422).
- **Move.** Only Teams can move (422), only to an active Administration (422), and not to the Administration they are already in (422). An archived Team returns 409. Placement history is kept, and Members of the moved Team are re-evaluated for task eligibility (§14).
- **Archive.** KORA and the PMO cannot be archived (422). An already-archived unit returns 409. The unit must not still contain active sub-units, active Members, or open role assignments scoped to it (409 `"Cannot archive: ..."`).
- Permission is checked **before** existence, so an unknown `unit_id` returns **403**, not 404.

### 8.1a Member lookup (`GET /api/v1/organization/members`) — CurrentAccess
The lookup for pickers and names (assignees, recipients, invitees, task creators). **200** `DirectoryMemberResponse[]` ordered by `full_name`: `id` (the Member id used everywhere else), `full_name`, `team_id|null`, `role_key|null`. **No contact or academic data.** `?scope=all` (callers who can create tasks) lists every active Member for "Other".
- **Who is listed:** active Members (Member and account both active) whose Team or role unit is within the scope of **any unit where the caller holds one of `task.view`, `task.create`, `task.manage`, `announcement.publish`, `announcement.manage`, `calendar.create`, `calendar.manage`, `organization.manage`**, plus the caller's own Member record. The normal role defaults therefore show a Team Member their own Team, an Administration Manager their Administration, and the Event/Project Leader everyone; overrides expand or restrict it like any other scoped permission.
- **Not listed:** deactivated Members and Members outside the caller's scope. A Member id seen elsewhere (e.g. a former assignee in task history) may therefore be missing from the lookup; clients must show a neutral placeholder rather than fail.
- The list is unpaginated. It is not the System Admin list (`/admin/members`), which keeps all profile data.

### 8.2 Members (`/api/v1/admin/members`) — SystemAdmin only
- `MemberResponse`: `id`, `account_id`, `username`, `full_name`, `university_id|null`, `phone|null`, `email|null`, `major|null`, `academic_year|null`, `status` MemberStatus, `team_id|null`, `role_key` RoleKey|null, `role_unit_id|null`. The last three are null when deactivated.
- `MemberProfileFields`: `full_name` (trimmed, 1–200); the optional fields `university_id` (≤64), `phone` (≤32), `email` (≤254, must be an email address: a single `@`, no whitespace, and a dot in the domain; otherwise 422), `major` (≤200) and `academic_year` (≤32), all trimmed. Blank, null and omitted values are all stored as null.
- `RoleFields`: `role_key` RoleKey, plus `administration_id` uuid|null (required for `administration_manager` only, and rejected for the other roles).

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /admin/members` | — | 200 `MemberResponse[]` (by `full_name`) | — |
| `GET /admin/members/{member_id}` | — | 200 | 404 |
| `POST /admin/members` | `CreateMemberRequest` = profile + RoleFields + `username` (1–256) + `team_id` (optional; required only for Team Leader and Member roles, `422 "A Team is required for this role."`) | 201 `{member: MemberResponse, temporary_password: string}` | 422 invalid username or invalid team/role; 409 `"That username is already in use."` |
| `PUT /admin/members/{member_id}` | `MemberProfileFields` (**full replacement** of the profile; omitted optional fields become null) | 200 | 404 |
| `POST /admin/members/{member_id}/team` | `{team_id}` | 200 | 404; 409 deactivated; 422 inactive or unknown Team, or the same Team |
| `POST /admin/members/{member_id}/role` | `RoleFields` | 200 | 404; 409 deactivated; 422 invalid role or unit, or the same role |
| `POST /admin/members/{member_id}/deactivate` | — | 200 | 404; 409 already deactivated; 409 `"The final active System Admin cannot be deactivated."` |
| `POST /admin/members/{member_id}/reactivate` | `ReactivateMemberRequest` = RoleFields + `team_id` (optional, same rule) | 200 | 404; 409 already active; 422 invalid team or role |
| `POST /admin/members/{member_id}/reset-password` | — | 200 `{temporary_password}` | 404; 409 deactivated |

Behavior:
- **Provisioning** creates the account (with a 7-day temporary password, **returned only once in the response**), the Member, the Team placement and the role.
- **Team Leader and Member roles** are always held at the Member's current Team. A Team change moves the role with the Member. Other roles keep their unit.
- **Deactivation** (one transaction) ends the placement and role, deactivates the account and revokes all its sessions. **Reactivation** needs a new Team and role.
- **Password reset** issues a new temporary password and revokes all sessions.
- Team changes, role changes, deactivation and Team moves trigger the task-assignee re-evaluation (§14).

---

## 9. Tasks and weekly series

### 9.1 Task access rules (scope = the task's unit)
- **View:** `task.view` at the scope, **or** `task.manage` there, **or** being the task's creator or a current assignee. An explicit `task.view` **deny override** deciding the scope hides the task even from them.
- **Create:** an **active Member** with `task.create` at the scope (accounts that are not Members get 403). Subtasks need `task.create` at the parent's scope.
- **Administer** (edit, cancel, reopen, manage assignees, move): the creator, if they are an active Member, or anyone with `task.manage` at the scope.
- **Comment:** the creator, a current assignee or a scoped manager.
- **Assignees:** one or more distinct active Members within the scope (§3.5).

### 9.2 Schemas
- `TaskResponse`: `id`, `title`, `description|null`, `priority|null`, `due_at|null`, `status`, `scope_unit_id`, `parent_id|null`, `series_id|null`, `created_by_account_id`, `created_by_member_id`, `created_at`, `updated_at`, `started_at|null` (set at the first move to `in_progress` or `completed`), `assignee_member_ids` (sorted).
- Task fields: `title` (trimmed, 1–300), `description` (≤10000, not trimmed), `priority` TaskPriority|null, `due_at` (with an offset)|null.
- `CommentResponse`: `id`, `task_id`, `author_account_id`, `body|null` (null once deleted), `created_at`, `edited_at|null`, `deleted_at|null`. A comment `body` is trimmed, 1–5000.
- `TaskEventResponse` (history): `kind` (`created`, `updated`, `status_changed`, `assignee_added`, `assignee_removed`, `assignee_not_added`, `scope_changed`, `subtask_created`, `comment_added`, `comment_edited`, `comment_deleted`), `actor_account_id|null`, `data` object, `created_at`.

### 9.3 Endpoints (`/api/v1/tasks`) — CurrentAccess
| Method & path | Body | Rule | Success | Errors |
|---|---|---|---|---|
| `GET /tasks?status=&scope_unit_id=` | — | visible **top-level** tasks only | 200 `TaskResponse[]` (by `due_at`, nulls last, then `created_at`) | 422 bad filter |
| `POST /tasks` | `CreateTaskRequest`: task fields + `assignee_member_ids` (≥1) + `scope_unit_id` | create | 201 | 403; 422 inactive scope, bad assignees or duplicates |
| `GET /tasks/{task_id}` | — | view | 200 | 404; 403 |
| `PATCH /tasks/{task_id}` | `UpdateTaskRequest` (partial; `title` cannot be null) | administer | 200 (no change means no write) | 404; 403; 422 |
| `POST /tasks/{task_id}/status` | `{status: TaskStatus}` | see transitions below | 200 | 404; 403; 409 invalid transition |
| `POST /tasks/{task_id}/assignees` | `{member_id}` | administer | 200 | 404; 403; 409 `"Already an assignee."`; 422 ineligible |
| `POST /tasks/{task_id}/assignees/{member_id}/remove` | — | administer | 200 | 404 (task, or not an assignee); 403; 422 last assignee |
| `POST /tasks/{task_id}/move` | `{scope_unit_id}` | creator with `task.create` at the destination, or `task.manage` at source **and** destination | 200 | 404; 403; 422 subtask, same scope or inactive destination |
| `GET /tasks/{task_id}/subtasks` | — | view the parent; subtasks filtered by visibility | 200 `TaskResponse[]` | 404; 403 |
| `POST /tasks/{task_id}/subtasks` | `CreateSubtaskRequest`: task fields + `assignee_member_ids` | view the parent + `task.create` at its scope | 201 | 404; 403; 422 parent is a subtask, or bad assignees |
| `GET /tasks/{task_id}/history` | — | view | 200 `TaskEventResponse[]` (insertion order) | 404; 403 |
| `GET /tasks/{task_id}/comments` | — | view | 200 `CommentResponse[]` (by `created_at`; deleted ones listed with `body: null`) | 404; 403 |
| `POST /tasks/{task_id}/comments` | `{body}` | comment | 201 | 404; 403 |
| `PATCH /tasks/{task_id}/comments/{comment_id}` | `{body}` | author only | 200 | 404 (comment not on this task); 403 not the author; 409 deleted |
| `POST /tasks/{task_id}/comments/{comment_id}/delete` | — | author only | 200 (soft delete) | 404; 403; 409 already deleted |

**Status transitions** (any other is 409 `"Cannot change status from X to Y."`):

| From | Allowed targets | Who |
|---|---|---|
| `new` | `in_progress`, `completed` | an assignee or a scoped manager |
| `new` | `cancelled` | administer (creator or manager) |
| `in_progress` | `completed` | an assignee or a scoped manager |
| `in_progress` | `cancelled` | administer |
| `completed`, `cancelled` | `new` (reopen) | administer |

Other rules:
- Subtasks are one level deep, inherit the parent's scope, have their own status, and **move with the parent**. A move removes assignees who are no longer within scope (reason `out_of_scope`) and keeps the scope history.
- Manual removal cannot remove the last assignee. Automatic removals (§14) may leave a task with none; it stays open.
- Tasks and comments are never hard-deleted.
- **History `data`** records each change: `updated` holds `changes: {field: [old, new]}`; `status_changed` holds `previous` and `status`; assignee events hold `member_id` and `reason`; `scope_changed` holds `previous` and `scope_unit_id`; comment events hold `comment_id`, and `comment_edited` also holds `previous_body`. **Once a comment is deleted, its text is removed from every history response**: `previous_body` is dropped, and `content_removed: true` is added to that comment's events that held text. The kind, actor, time and `comment_id` are kept, and the stored events are not modified.

### 9.4 Weekly series (`/api/v1/task-series`) — CurrentAccess
`SeriesResponse`:
- fields: `id`, `scope_unit_id`, `title`, `description|null`, `priority|null`, `assignee_member_ids`, `first_due_at`, `ends_at`, `status` SeriesStatus (`active`/`stopped`), `created_by_account_id`, `stopped_at|null`;
- `subtask_templates`: objects `{key, title, description, priority, assignee_member_ids}`;
- `occurrence_ids`: top-level occurrences, by due time.

| Method & path | Body | Rule | Success |
|---|---|---|---|
| `POST /task-series` | `CreateSeriesRequest`: `scope_unit_id`, `title`, `description?`, `priority?`, `first_due_at`, `ends_at`, `assignee_member_ids` (≥1), `subtasks?` `[{title, description?, priority?, assignee_member_ids}]` | same as task create | 201 |
| `GET /task-series/{series_id}` | — | the creator or `task.view` at the series scope | 200 |
| `PATCH /task-series/{series_id}` | `UpdateSeriesRequest` (partial): `title`, `description`, `priority`, `assignee_member_ids`, `subtasks` (the **complete** new template list; send an existing `key` to update a template, omit it to add one). `title`, `assignee_member_ids` and `subtasks` cannot be null. | the creator or `task.manage` at the scope; series active | 200 |
| `POST /task-series/{series_id}/move` | `{scope_unit_id}` | the creator with `task.create` at the destination, or `task.manage` at the destination **and every affected source** | 200 |
| `POST /task-series/{series_id}/stop` | — | the creator or `task.manage`; series active | 200 |

Errors: 404 unknown series; 403; 409 `"The series has been stopped."`; 422 for these rule violations:
- `ends_at` before `first_due_at`;
- more than **104** weekly occurrences (an intentional anti-abuse cap);
- ineligible assignees;
- an unknown or repeated template `key`;
- moving to the same or an inactive scope.

Behavior:
- **Creation** generates every occurrence up front, each with its template subtasks. There is no scheduler. Occurrences are ordinary tasks (with `series_id`) and use the task endpoints.
- **Edit, move and stop** affect only **future, unstarted occurrences** (status `new`, never started, `due_at` in the future) and their direct subtasks. Past, started, completed and cancelled occurrences never change.
- On edit, removed templates **cancel** the matching unstarted subtasks. Move trims the series' template assignees to those still eligible. Stop cancels future unstarted occurrences and their unstarted subtasks.

---

## 10. Announcements (`/api/v1/announcements`)

All routes use CurrentAccess. `AnnouncementResponse`:
- identity and lifecycle: `id`, `scope_unit_id`, `state`, `current_version`, `created_by_account_id`, `created_at`, `updated_at`, `published_at|null`, `published_by_account_id|null`, `withdrawn_at|null`, `withdrawn_by_account_id|null`;
- content: `title|null`, `body|null`, `content_hidden` (true, with null content, when a recipient views a withdrawn announcement);
- read state: `my_read_version|null`, `my_read_current|null`. These are set **only for recipients**.

Fields: `title` (trimmed, 1–300), `body` (trimmed, 1–20000).

**Visibility**
- **A draft** is visible to its creator and to current `announcement.manage` holders at the scope.
- **Published or withdrawn** announcements are visible to the publisher, to current scoped managers, and to direct recipients, who keep access even after moving scope.
- **Recipients of a withdrawn announcement** see the record without its content.

| Method & path | Body | Rule | Success | Errors |
|---|---|---|---|---|
| `GET /announcements?state=` | — | visible only | 200 `AnnouncementResponse[]` (by `updated_at` desc) | 422 bad state |
| `POST /announcements` | `{scope_unit_id, title, body}` | `announcement.publish` at the scope | 201 (draft, version 1) | 403; 422 inactive scope |
| `GET /announcements/{id}` | — | visible | 200. **Side effect:** a recipient opening a *published* announcement marks its current version as read | 404; 403 |
| `PATCH /announcements/{id}` | `{title?, body?}` | drafts: the creator or managers; published: the publisher or managers | 200. An actual change appends an immutable version, and recipients of a published announcement are notified. No change means no version. | 404; 403; 409 withdrawn |
| `POST /announcements/{id}/publish` | `{recipient_member_ids: uuid[] (≥1, distinct)}` | visible + `announcement.publish` at the scope | 200 (immediately `published`) | 404; 403; 409 not a draft; 422 recipients not distinct, or not active Members within the scope |
| `POST /announcements/{id}/withdraw` | — | the publisher or a scoped manager | 200 | 404; 403; 409 not published |
| `GET /announcements/{id}/versions` | — | drafts: the creator or managers; published or withdrawn: the publisher or managers | 200 `VersionResponse[]` `{version, title, body, created_by_account_id, created_at}` | 404; 403 |
| `GET /announcements/{id}/recipients` | — | the publisher or managers; not for drafts | 200 `RecipientStatusResponse[]` `{member_id, account_id, read_version|null, read_current}` (by `added_at`, then `member_id`) | 404; 403 |

Recipients are fixed at publication and never change. Read state is tracked per version: after an edit, a recipient has not read the announcement until they open it again. Nothing is hard-deleted.

---

## 11. Notifications (`/api/v1/notifications`)

All routes use CurrentAccess, and each user acts only on their own records. `NotificationResponse`: `id`, `category`, `kind`, `source_type`, `source_id`, `summary|null`, `redacted` bool, `actor_account_id|null`, `created_at`, `read_at|null`.

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `GET /notifications?unread_only=false` | — | 200 `NotificationResponse[]` (own, not deleted, newest first) | 422 |
| `GET /notifications/{id}` | — | 200 | 404 (missing, someone else's or deleted) |
| `POST /notifications/{id}/read` | — | 200 (idempotent) | 404 |
| `POST /notifications/read-all` | — | 204 | — |
| `POST /notifications/{id}/delete` | — | 204 (soft delete from the reader's own list) | 404 |
| `POST /notifications/delete-all` | — | 204 | — |
| `GET /notifications/preferences` | — | 200 `{<NotificationCategory>: bool}`, covering every category (default `true`) | — |
| `PUT /notifications/preferences` | `{<NotificationCategory>: bool, ...}` (a partial map) | 200 the full map | 422 unknown category or non-boolean |

**Redaction.** On every read, access to the source is re-checked. If the reader can no longer see the source, `summary` is null and `redacted` is true. The source route still returns 403.

**Generation rules**
- Notifications are in-app only.
- They are written in the same transaction as the change that causes them.
- The actor is **never** notified.
- A disabled category suppresses creation.
- `summary` is at most 300 characters.

| `source_type` | `kind` | Category | Recipients |
|---|---|---|---|
| `task` | `assigned`, `unassigned` | `task_assignment` | the affected assignee |
| `task` | `updated`, `status_changed`, `moved` | `task_update` | the creator and current assignees |
| `task` | `commented` | `task_comment` | the creator and current assignees |
| `task_series` | `series_assigned`, `series_unassigned`, `series_assignment_changed` | `task_assignment` | the affected Members, **once per series operation** |
| `task_series` | `series_updated` | `task_update` | the series creator and currently eligible series and template assignees, excluding Members removed in the same operation |
| `announcement` | `published` | `announcement_new` | direct recipients |
| `announcement` | `edited` | `announcement_change` | direct recipients (published announcements only) |
| `announcement` | `withdrawn` | `announcement_change` | direct recipients; `summary` is null |
| `calendar_event` | `invited` | `calendar_event` | each new invitee |
| `calendar_event` | `updated`, `cancelled` | `calendar_event` | current invitees |

A series operation never sends per-occurrence notifications. Removing a calendar invitee is silent.

---

## 12. Calendar (`/api/v1/calendar`)

All routes use CurrentAccess. Each item is a single entity of `type` `event` or `meeting`.

`EventResponse`:
- details: `id`, `type`, `title`, `description|null`, `starts_at`, `ends_at`, `location_text|null`, `online_url|null`, `scope_unit_id`;
- organizer and lifecycle: `organizer_account_id`, `organizer_member_id`, `state`, `created_at`, `updated_at`, `cancelled_at|null`;
- invitations: `invitee_member_ids|null` (**only** for the organizer and scoped managers, otherwise null), and `my_invitation|null` `{member_id, invited_at}` (the caller's own current invitation).

Fields:
- `title` is trimmed, 1–300; `description` ≤10000.
- `starts_at` and `ends_at` need offsets, and `ends_at` must be after `starts_at`.
- `location_text` (trimmed, 1–500) and `online_url` (http/https URL, ≤2000) are **mutually exclusive**.

**Access rules**
- **View:** the organizer (an active Member), current invitees (who keep access after moving scope), and current `calendar.manage` holders at the scope.
- **Create:** an active Member with `calendar.create` at the scope.
- **Administer** (edit, cancel, invitations): the organizer or a scoped manager.
- A **cancelled event is read-only** (409 on any change). The scope never changes.

| Method & path | Body | Rule | Success | Errors |
|---|---|---|---|---|
| `GET /calendar?from=&to=` (both required) | — | — | 200 `MyCalendarResponse` | 422: `from`/`to` missing (validation list); naive time, `to` ≤ `from`, or range > 366 days (string) |
| `GET /calendar/events` | — | visible only | 200 `EventResponse[]` (by `starts_at`) | — |
| `POST /calendar/events` | `CreateEventRequest`: event fields + `scope_unit_id` + `invitee_member_ids` (≥1, distinct, active Members within the scope) | create | 201 | 403; 422 |
| `GET /calendar/events/{event_id}` | — | view | 200 | 404; 403 |
| `PATCH /calendar/events/{event_id}` | `UpdateEventRequest` (partial; `type`, `title`, `starts_at`, `ends_at` cannot be null; **sending `scope_unit_id` → 422**) | administer | 200 (no change means no write and no notification) | 404; 403; 409 cancelled; 422 |
| `POST /calendar/events/{event_id}/cancel` | — | administer | 200 | 404; 403; 409 already cancelled |
| `POST /calendar/events/{event_id}/invitees` | `{member_id}` | administer | 200 | 404; 403; 409 `"Already invited."` / cancelled; 422 ineligible |
| `POST /calendar/events/{event_id}/invitees/{member_id}/remove` | — | administer | 200 | 404 not invited; 403; 409 cancelled; 422 last invitee |
| `GET /calendar/events/{event_id}/invitations` | — | administer | 200 `InvitationResponse[]` `{member_id, valid_from, valid_to|null, created_by_account_id, ended_by_account_id|null}` (current and removed) | 404; 403 |
| `GET /calendar/events/{event_id}/history` | — | view | 200 `HistoryResponse[]` `{kind, actor_account_id|null, data, created_at}`, with kinds `created`, `updated`, `cancelled`, `invitee_added`, `invitee_removed` | 404; 403 |

**`MyCalendarResponse`** returns `{starts_at, ends_at, events, task_due_dates}`:
- `events` are `EventItem`s: an `EventResponse` plus `item_type: "event"`, for accessible events overlapping `[from, to)`.
- `task_due_dates` are `TaskDueItem`s `{item_type: "task_due", task_id, title, due_at, status, scope_unit_id}`. They cover tasks with status `new` or `in_progress` that the caller **created or is assigned to** (no other tasks are included), with a due time in range, re-checked for task visibility.
- Task data is read live and is never stored or editable through calendar routes.

Recurrence, RSVP, attendance, attachments and comments are not implemented.

---

## 13. Audit log (`/api/v1/admin/audit-records`)

**SystemAdmin only** (non-admins get 403). This is the one explicit exception to "System Admin has no implicit operational access", and it is **read-only**: there are no `POST`, `PUT`, `PATCH` or `DELETE` methods (405) and no export. Reading records grants no access to the tasks, announcements, events or Members they describe. Responses contain only the stored metadata; nothing is reloaded from the source.

`AuditRecordResponse`: `id`, `sequence` (int, insertion order), `occurred_at`, `action`, `actor_account_id|null`, `resource_type`, `resource_id`, `scope_unit_id|null`, `before` object|null, `after` object|null.

### `GET /api/v1/admin/audit-records`
Query parameters (all optional):

| Parameter | Type | Meaning |
|---|---|---|
| `occurred_from` | datetime with offset | `occurred_at >= value` |
| `occurred_to` | datetime with offset | `occurred_at < value` |
| `action` | string ≤64 | exact match |
| `actor_account_id`, `resource_id`, `scope_unit_id` | uuid | exact match |
| `resource_type` | string ≤64 | exact match |
| `limit` | int 1–200, default 50 | page size |
| `cursor` | int ≥1 | the previous page's `next_cursor` |

**200** `{items: AuditRecordResponse[], next_cursor: int|null}`, newest first (by `sequence` descending); `next_cursor` is null on the last page. A naive time returns 422 `"Times must include a time zone offset."`, as does an out-of-range `limit` or `cursor`.

### `GET /api/v1/admin/audit-records/{record_id}`
**200** `AuditRecordResponse`; **404** `"Audit record not found."`.

### Recorded actions (`action` → `resource_type`)
| Area | Actions (resource type) |
|---|---|
| access | `account.bootstrapped`, `account.password_changed`, `account.password_reset`, `account.locked_out` (existing accounts only), `system_admin.granted`, `system_admin.revoked` (`user_account`); `role_default.created`, `role_default.ended` (`role_permission_default`); `permission_override.created`, `permission_override.ended` (`permission_override`) |
| organization | `org_unit.created`, `org_unit.moved`, `org_unit.archived` (`org_unit`); `member.provisioned`, `member.profile_updated` (changed field names only), `member.team_changed`, `member.role_changed`, `member.deactivated`, `member.reactivated` (`member`) |
| tasks | `task.created`, `task.updated`, `task.status_changed`, `task.cancelled`, `task.reopened`, `task.moved`, `task.assignee_added`, `task.assignee_removed` (`task`); `task_comment.created`, `task_comment.edited`, `task_comment.deleted` (`task_comment`); `task_series.created`, `task_series.updated`, `task_series.moved`, `task_series.stopped`, `task_series.assignees_removed` (`task_series`) |
| announcements | `announcement.draft_created`, `announcement.published`, `announcement.edited`, `announcement.withdrawn` (`announcement`) |
| notifications | `notification_preferences.updated` (`notification_preferences`; resource = the account) |
| calendar | `calendar_event.created`, `calendar_event.updated`, `calendar_event.cancelled`, `calendar_event.invitee_added`, `calendar_event.invitee_removed` (`calendar_event`) |

**What is recorded**
- There is one record per successful logical change, committed atomically with that change. Series-wide operations produce one record, not one per occurrence.
- `before` and `after` hold only allowlisted IDs, states, counts, timestamps, titles (≤120 characters) and names of changed fields.
- Never stored: passwords, hashes, tokens, descriptions, comment or announcement bodies, event locations and URLs, override reasons, Member profile values.

**What is not recorded:** reads, sign-in success, sign-out, notification read and delete. Records start at migration `6b1e9c4d2a7f` (no backfill), and there is no request or correlation ID.

---

## 14. Cross-module integration rules

- **Membership changes re-evaluate assignees.** These triggers run inside the same transaction:
  - triggers: a Team change, role change, deactivation or Team move;
  - effect: assignees of **open** tasks are removed only if they are inactive (`member_inactive`) or no longer within the task's scope (`out_of_scope`). A role or Team change alone never removes anyone.
  - Removals notify the affected Member. For series occurrences, Members get one notification per series instead.
- **Task moves** remove assignees who are ineligible at the destination.
- **Notifications** re-check access to their source on every read (§11). Each source module registers a checker for its `source_type` (`task`, `task_series`, `announcement`, `calendar_event`).
- **Calendar ↔ tasks:** the calendar reads task due dates through the tasks service only (§12). Tasks never read calendar data.
- **Audit:** every module writes its own audit records in the change's transaction (§13). If the audit write fails, the whole change rolls back.
- **Recruitment & Selection** is a separate platform; there is no integration API.

---

## 15. Known discrepancies and observations

These items are reported, not resolved, because the code is the source of truth.

Resolved in Milestone 8B (2026-10-12):
- **Error statuses.** OpenAPI now documents every error status each operation can return. Errors other than 422 use `ErrorResponse {detail: string}`.
- **422 format.** Every 422 now refers to `ValidationErrorResponse`, whose `detail` is either a list of `ValidationIssue {type, loc, msg, ctx?}` (no `input`) or a string.
- **Calendar `from`/`to`.** Both are required, in the schema and in the handler.
- **`scope_unit_id` on event updates.** It is no longer advertised in the schema; sending it still returns 422.
- **Precise response types:**
  - `SeriesResponse.status` is `SeriesStatus`, and `subtask_templates` are `SubtaskTemplateResponse`;
  - `MemberResponse` has no input constraints, and its `role_key` is `RoleKey`;
  - task history `kind` is `EventKind`; calendar history `kind` is an enum;
  - `permission` and `key` fields are `Permission`.
- **Member `email`** is validated as an email address.
- **Deleted comments.** Their text, including earlier edited versions, is removed from task history.

A test-suite check (`tests/response_contract.py`) fails the run if any response observed by the tests has a status or error shape that OpenAPI does not document.

Remaining (unchanged on purpose, or awaiting a decision):
1. **`GET /announcements/{id}` has a side effect.** It records a read for recipients, so a safe method writes data. This is approved behavior.
2. **Unknown organization unit IDs** return 403, not 404, because permission is checked before existence. This is approved behavior.
3. **Unpaginated lists.** No list except the audit list is paginated. This is an unresolved decision in `PROJECT_STATE.md`.
4. **`GET /calendar/events` has no range filter**, although the service supports overlap filtering. It is left unchanged because the route's intended filter behavior is not established:
   - must `from` and `to` be given together, or may one side be open;
   - is the 366-day cap from `GET /calendar` also required here;
   - is overlap or containment the right semantics?

   The range query remains available through `GET /calendar`.
5. **Plain-string fields.** These stay plain strings so modules don't import each other:
   - `NotificationResponse.kind` and `source_type` (values in §11): `notifications` must not import its source modules;
   - `UnitDecisionResponse.kind` and `RoleDefaultRequest.role_key`: `access` must not import `organization`. An unknown role still returns 422 `"Unknown role."`.
6. **Profile email validation** is a syntax check only: a single `@`, no whitespace, and a dot in the domain. Deliverability is not verified.
---

## 16. Endpoint index

| # | Method | Path | Guard |
|---|---|---|---|
| 1 | GET | `/api/v1/health` | none |
| 2 | POST | `/api/v1/auth/sign-in` | none |
| 3 | POST | `/api/v1/auth/sign-out` | session + CSRF |
| 4 | POST | `/api/v1/auth/sign-out-all` | session + CSRF |
| 5 | GET | `/api/v1/auth/me` | session |
| 6 | POST | `/api/v1/auth/change-password` | session + CSRF |
| 7 | GET | `/api/v1/access/me` | account |
| 8 | GET | `/api/v1/organization/units` | access |
| 9 | POST | `/api/v1/organization/units` | access |
| 10 | GET | `/api/v1/organization/units/{unit_id}` | access |
| 10a | GET | `/api/v1/organization/members` | access |
| 11 | POST | `/api/v1/organization/units/{unit_id}/move` | access |
| 12 | POST | `/api/v1/organization/units/{unit_id}/archive` | access |
| 13 | GET | `/api/v1/admin/members` | admin |
| 14 | POST | `/api/v1/admin/members` | admin |
| 15 | GET | `/api/v1/admin/members/{member_id}` | admin |
| 16 | PUT | `/api/v1/admin/members/{member_id}` | admin |
| 17 | POST | `/api/v1/admin/members/{member_id}/team` | admin |
| 18 | POST | `/api/v1/admin/members/{member_id}/role` | admin |
| 19 | POST | `/api/v1/admin/members/{member_id}/deactivate` | admin |
| 20 | POST | `/api/v1/admin/members/{member_id}/reactivate` | admin |
| 21 | POST | `/api/v1/admin/members/{member_id}/reset-password` | admin |
| 22 | GET | `/api/v1/admin/permissions` | admin |
| 23 | GET | `/api/v1/admin/role-defaults` | admin |
| 24 | POST | `/api/v1/admin/role-defaults` | admin |
| 25 | POST | `/api/v1/admin/role-defaults/{default_id}/end` | admin |
| 26 | GET | `/api/v1/admin/accounts/{account_id}/overrides` | admin |
| 27 | POST | `/api/v1/admin/accounts/{account_id}/overrides` | admin |
| 28 | POST | `/api/v1/admin/overrides/{override_id}/end` | admin |
| 29 | GET | `/api/v1/admin/accounts/{account_id}/effective-access` | admin |
| 30 | GET | `/api/v1/admin/system-admins` | admin |
| 31 | POST | `/api/v1/admin/accounts/{account_id}/system-admin` | admin |
| 32 | POST | `/api/v1/admin/accounts/{account_id}/system-admin/revoke` | admin |
| 33 | GET | `/api/v1/admin/audit-records` | admin |
| 34 | GET | `/api/v1/admin/audit-records/{record_id}` | admin |
| 35 | GET | `/api/v1/tasks` | access |
| 36 | POST | `/api/v1/tasks` | access |
| 37 | GET | `/api/v1/tasks/{task_id}` | access |
| 38 | PATCH | `/api/v1/tasks/{task_id}` | access |
| 39 | POST | `/api/v1/tasks/{task_id}/status` | access |
| 40 | POST | `/api/v1/tasks/{task_id}/assignees` | access |
| 41 | POST | `/api/v1/tasks/{task_id}/assignees/{member_id}/remove` | access |
| 42 | POST | `/api/v1/tasks/{task_id}/move` | access |
| 43 | GET | `/api/v1/tasks/{task_id}/subtasks` | access |
| 44 | POST | `/api/v1/tasks/{task_id}/subtasks` | access |
| 45 | GET | `/api/v1/tasks/{task_id}/history` | access |
| 46 | GET | `/api/v1/tasks/{task_id}/comments` | access |
| 47 | POST | `/api/v1/tasks/{task_id}/comments` | access |
| 48 | PATCH | `/api/v1/tasks/{task_id}/comments/{comment_id}` | access |
| 49 | POST | `/api/v1/tasks/{task_id}/comments/{comment_id}/delete` | access |
| 50 | POST | `/api/v1/task-series` | access |
| 51 | GET | `/api/v1/task-series/{series_id}` | access |
| 52 | PATCH | `/api/v1/task-series/{series_id}` | access |
| 53 | POST | `/api/v1/task-series/{series_id}/move` | access |
| 54 | POST | `/api/v1/task-series/{series_id}/stop` | access |
| 55 | GET | `/api/v1/announcements` | access |
| 56 | POST | `/api/v1/announcements` | access |
| 57 | GET | `/api/v1/announcements/{announcement_id}` | access |
| 58 | PATCH | `/api/v1/announcements/{announcement_id}` | access |
| 59 | POST | `/api/v1/announcements/{announcement_id}/publish` | access |
| 60 | POST | `/api/v1/announcements/{announcement_id}/withdraw` | access |
| 61 | GET | `/api/v1/announcements/{announcement_id}/versions` | access |
| 62 | GET | `/api/v1/announcements/{announcement_id}/recipients` | access |
| 63 | GET | `/api/v1/notifications` | access |
| 64 | GET | `/api/v1/notifications/preferences` | access |
| 65 | PUT | `/api/v1/notifications/preferences` | access |
| 66 | POST | `/api/v1/notifications/read-all` | access |
| 67 | POST | `/api/v1/notifications/delete-all` | access |
| 68 | GET | `/api/v1/notifications/{notification_id}` | access |
| 69 | POST | `/api/v1/notifications/{notification_id}/read` | access |
| 70 | POST | `/api/v1/notifications/{notification_id}/delete` | access |
| 71 | GET | `/api/v1/calendar` | access |
| 72 | GET | `/api/v1/calendar/events` | access |
| 73 | POST | `/api/v1/calendar/events` | access |
| 74 | GET | `/api/v1/calendar/events/{event_id}` | access |
| 75 | PATCH | `/api/v1/calendar/events/{event_id}` | access |
| 76 | POST | `/api/v1/calendar/events/{event_id}/cancel` | access |
| 77 | POST | `/api/v1/calendar/events/{event_id}/invitees` | access |
| 78 | POST | `/api/v1/calendar/events/{event_id}/invitees/{member_id}/remove` | access |
| 79 | GET | `/api/v1/calendar/events/{event_id}/invitations` | access |
| 80 | GET | `/api/v1/calendar/events/{event_id}/history` | access |

Guards: **session** = AuthenticatedSession (a temporary password is allowed); **account** = CurrentAccount; **access** = CurrentAccess (the account plus its permission snapshot; the handler checks permissions); **admin** = SystemAdmin. Unsafe methods always also require CSRF (§2.2), except sign-in.


## Addendum 2026-10-18
- `task.create` is no longer a default of Member and PMO Member (only Team Leader, Administration Manager and the leadership roles; a System Admin can grant it).
- `CreateTaskRequest`/`CreateSubtaskRequest`: `assignee_member_ids` (default `[]`) + `external_assignee_member_ids` (default `[]`); at least one assignee overall. `TaskResponse` adds `external_assignees: [{id, full_name}]` and `from_outside: boolean` (creator was not the Team Leader / Administration Manager of the scope; snapshot at creation).
- New permissions `calendar.view_administration` (default: Team Leader, Administration Manager) and `calendar.view_all` (default: Event Leader, Deputy, PMO Leader, PMO Member), grantable by overrides.
- `GET /calendar/administration?from&to` and `GET /calendar/all?from&to` (403 without the permission): `{starts_at, ends_at, tasks: [{task_id, title, due_at, status, scope_unit_id, unit_name, administration_id|null, administration_name|null, from_outside}]}`. The first covers the Administration containing each unit where the caller holds the permission; the second every unit.
- Arabic names: قائد الحدث، نائب قائد الحدث، مدير المشروع (PMO Leader)، مسؤول متابعة (PMO Member)، مدير الإدارة، قائد الفريق؛ the PMO unit is named «مكتب إدارة المشروع (PMO)».

## Addendum 2026-10-19
- New permission `task.follow` (default: PMO Leader, PMO Member; grantable): read access to every task, held at any unit. `GET /tasks/follow?status=` (403 without it) returns `FollowTaskResponse[]` = `TaskResponse` + `unit_name`, `administration_id|null`, `administration_name|null`, `assignee_names: string[]`. Followers can open tasks but cannot edit, change status or comment; the normal `GET /tasks` list is unchanged (the PMO's own tasks only).
- Deleting a team is the existing archive operation (`POST /organization/units/{id}/archive`), presented as «حذف»; archived units are hidden from the UI and their history is kept (audit records reference units, so a physical delete is not possible).

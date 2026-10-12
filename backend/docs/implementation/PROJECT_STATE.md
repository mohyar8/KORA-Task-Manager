# KORA Internal Operations Platform — Backend Project State

_Last updated: 2026-10-12 (Milestone 7)_

## Current phase

Governance foundation. Authentication, the organization structure, Members, roles, scope-aware authorization, scoped tasks, announcements, in-app notifications, calendar events and meetings, and a central append-only audit log are implemented. There is no chat, file, reminder or email/push module.

## Repository baseline

- Git root: `KORA-Task-Manager/`, branch `main`. The backend lives in `backend/`.
- Implemented: package `kora_api` (`src/` layout) with an app factory, settings, versioned router composition, and `GET /api/v1/health` (no DB).
- Persistence: `core/database.py` provides the shared `Base` (with a constraint naming convention), a lazy async engine, a session factory on `app.state`, and an injectable `get_db_session` dependency. Alembic (async) lives in `migrations/` and reads `KORA_DATABASE_URL` (or an explicit `sqlalchemy.url`). `compose.yaml` defines a local PostgreSQL 17.
- Migrations:
  - `8335857d616c`, access foundation: `user_accounts`, `auth_sessions`, `login_throttles`, `system_admin_grants`.
  - `b89a71a2b1d0`, organization and authorization schema.
  - `c4d2e8f1a7b3`, seed data: KORA, the PMO, the 7 roles, the permission catalog and role defaults.
  - `b11106c7034d`, `account_deactivations` history (with backfill) and optional Member profile columns.
  - `7eb2d45fba99`, tasks schema.
  - `d7e3a1c9b5f2`, seeds the task permissions and their role defaults.
  - `f2de4d1ebabc`, adds `tasks.series_template_key`, which links series subtasks to their template.
  - `01947ff726ab`, announcements and notifications schema.
  - `e8a4b2d6c1f3`, seeds the announcement permissions and their role defaults.
  - `9ddea54afcb3`, calendar schema plus the `calendar_event` notification category. The downgrade rebuilds the enum.
  - `a3c7e5f9d2b4`, seeds the calendar permissions and their role defaults.
  - `6b1e9c4d2a7f`, `audit_records` plus a trigger that rejects UPDATE, DELETE and TRUNCATE. No backfill.
- `kora_api.access`:
  - Endpoints under `/api/v1/auth`: sign-in, sign-out, sign-out-all, me, change-password.
  - Argon2id hashing, server-side sessions, CSRF protection, a per-username login throttle, and the temporary-password gate (`CurrentAccount`).
  - A one-time bootstrap command for the first System Admin.
  - A final-System-Admin guard on account deactivation and System Admin revocation.
  - Authorization:
    - The permission catalog (`permissions.py`), role defaults and overrides (`models.py`), and a pure evaluator (`evaluation.py`).
    - Snapshot loading and administration services (`authorization.py`).
    - Route dependencies: `SystemAdmin`, `CurrentAccess` and `require_permission`.
    - System Admin routes under `/api/v1/admin`: permissions, role defaults, overrides, effective-access inspection, System Admin grants. Signed-in users read their own access at `/api/v1/access/me`.
  - `access` reads organization data only through the `OrganizationFacts` interface (`org_facts.py`). It never imports `organization`.
- `kora_api.organization`:
  - Tables: `org_units`, `org_unit_placements` (append-only history), `org_roles`, `members`, `member_team_placements`, `role_assignments`.
  - Permission-scoped unit routes `/api/v1/organization/units`: list, get, create, move a Team, archive.
  - System Admin–only member routes `/api/v1/admin/members`: create (returns a temporary password), update profile, change Team, change role, deactivate, reactivate, reset password.
  - `facts.py` implements `OrganizationFacts`. `main.create_app` installs it on `app.state`.
  - `queries.py` is the public read interface for other domains (Member positions, the current unit tree, scope membership).
  - `events.py` provides membership-change listeners. They are called on Team or role changes, deactivation and Team moves, inside the same transaction.
- `kora_api.tasks`:
  - Tables: `tasks`, `task_scope_history`, `task_assignments`, `task_comments`, `task_events` (task-local history) and `task_series`.
  - Routes: `/api/v1/tasks`, covering list, create, get, edit, status, assignees, move, subtasks, comments and history; and `/api/v1/task-series`, covering create, get, edit, move and stop.
- `kora_api.announcements`:
  - Tables: `announcements`, `announcement_versions`, `announcement_recipients` and `announcement_reads`.
  - Routes `/api/v1/announcements`: list, create draft, get (opening marks the current version read for a recipient), edit, publish, withdraw, versions, and recipient read status.
- `kora_api.notifications`:
  - A generic in-app module with `notifications` and `notification_preferences` tables.
  - Routes `/api/v1/notifications`: list (`unread_only`), get, read, read-all, delete, delete-all, and get/set preferences.
  - Source modules register access checkers in `create_app` (`app.state.notification_sources`).
- `kora_api.calendar`:
  - Tables: `calendar_events`, `calendar_invitations` and `calendar_event_history`.
  - `/api/v1/calendar` is the merged "my calendar" for a time range (`from`/`to`, with a time zone, at most 366 days).
  - `/api/v1/calendar/events`: list, create, get, edit, cancel, add or remove invitees, invitation history and event history.
- `kora_api.audit`:
  - Table `audit_records` (append-only, enforced by a DB trigger): UTC time, action key, optional actor account, resource type and id, optional scope unit, `before`/`after` metadata, and an insertion `sequence`.
  - `audit.service.record(...)` adds a record to the caller's transaction (no flush or commit). Each domain declares its actions in its own `audit_actions.py`.
  - Reading lives in `access/audit_router.py`: `GET /api/v1/admin/audit-records` (paged, filtered) and `GET /api/v1/admin/audit-records/{id}`. System Admin only.

## Confirmed technical decisions

- Python 3.13; FastAPI; `uv` for project and dependency management; `src/` layout; package `kora_api`.
- Architecture: a modular monolith with domain-first vertical slices.
- Configuration: `pydantic-settings`, using env vars prefixed `KORA_`. Optional `.env`; `.env.example` is committed.
- Tests: pytest + HTTPX (`AsyncClient` + `ASGITransport`, via anyio's pytest plugin).
- Quality: Ruff for lint and format; Pyright in strict mode.
- Data: PostgreSQL (production), SQLAlchemy 2 async with asyncpg, and Alembic. The engine connects lazily, so the app starts without a DB. Migrations are run manually and never on startup.
- Local infrastructure: Docker Compose, for local PostgreSQL only.
- API docs: enabled only when `KORA_ENVIRONMENT` is `local` or `test`, and disabled in `staging` and `production`. There is no override.
- Staging/production settings refuse the committed local database URL (an explicit `KORA_DATABASE_URL` is required) and `KORA_DEBUG=true`. No CORS middleware: the API is same-origin only.
- `.serena/` is git-ignored at the repo root.
- Runtime server: uvicorn.
- Tables: UUID primary keys and timezone-aware UTC timestamps. Time comes from `core/clock.py`.
- Tests: a separate `kora_test` database on the compose server, migrated to head once per run. Each test runs in a rolled-back transaction.
- Accounts:
  - User Account is separate from Member.
  - Usernames: case-insensitive (stored lowercase), `[a-z0-9._-]`, 3–64 characters.
  - Passwords: Argon2id via `argon2-cffi`, 8–128 characters, no composition rules.
  - Temporary passwords: random, expire after 7 days, and force a password change.
- Sessions:
  - Opaque 256-bit tokens; only SHA-256 hashes are stored.
  - Cookie `kora_session`: HttpOnly, Secure (in every environment; browsers accept it on `localhost`), SameSite=Lax, Path=/api. The token is never returned in a response body.
  - CSRF uses a session-bound, non-secret token in the `kora_csrf` cookie (readable, Secure, SameSite=Strict, Path=/), echoed in the `X-CSRF-Token` header. Every authenticated unsafe request requires it; sign-in does not.
  - 8-hour idle timeout and 7-day absolute lifetime. Password change and sign-out-all revoke all sessions.
- No secret disclosure: 422 responses never echo submitted values, and the DB engine uses `hide_parameters=True` so SQL logs and errors omit bound values.
- Sign-in throttle: 5 failures per normalized username within 15 minutes locks it for 15 minutes (429 with `Retry-After`). This also applies to usernames that don't exist. Credential failures return the same generic 401.
- System Admin:
  - An append-only grant, separate from organizational roles, with no implicit operational-data access.
  - Bootstrap only through the CLI, and only if no grant ever existed.
  - The final active System Admin cannot be deactivated or revoked.
- Organization:
  - A single fixed KORA organization; not multi-tenant, with no concurrent events or projects.
  - The KORA root and the single PMO are seeded with fixed ids and cannot be archived.
  - Administrations sit directly under KORA, Teams under an active Administration, and the PMO contains no Teams.
  - Teams move between Administrations by closing one placement row and opening another, so earlier placements are kept.
  - Archiving a unit is refused while it has active units under it, active Members in it, or open role assignments scoped to it.
- Members:
  - Required: account link (the only unique field), full name and status.
  - Optional: university/student ID, phone, email, major/specialization and academic year. Blank values are stored as null.
  - An active Member has exactly one open Team placement and one open role (partial unique indexes).
  - Team Leader and Member roles always use the Member's current Team, so a Team change moves the role with the Member. A Team may have several Team Leaders.
  - Deactivation, in one transaction, ends the Team placement and role, deactivates the account and revokes its sessions. Reactivation requires a new placement and role.
  - Provisioning, profile edits, Team and role changes, password resets and deactivation/reactivation are all System Admin only.
- Authorization:
  - Catalog: `organization.manage`, `task.view`, `task.create` and `task.manage`.
  - `organization.manage` is a default for the Event/Project Leader and Deputy Leader, at KORA.
  - `task.view` and `task.create` are defaults for every role, at its assigned unit.
  - `task.manage` is a default for the Event/Project Leader and Deputy Leader (KORA), the PMO Leader (PMO), the Administration Manager (its Administration) and the Team Leader (its Team). The PMO Member and Member don't get it.
  - `announcement.publish` and `announcement.manage` follow the same pattern as `task.manage`: the Event/Project Leader, Deputy Leader, PMO Leader, Administration Manager and Team Leader get both at their assigned unit; the PMO Member and Member don't.
  - `calendar.create` is a default for every role at its assigned unit. `calendar.manage` follows the `task.manage` pattern; the PMO Member and Member don't get it.
  - Role defaults apply only through an active Member's open role assignment, covering the role's unit and everything beneath it.
  - Overrides (grant/deny per account, permission and unit) apply to any active account, Member or not. A reason is required; there is no expiry, and a System Admin ends them.
  - Precedence: the most specific unit on the chain that has an override decides; deny beats grant at the same unit; otherwise role defaults apply.
  - Evaluation can be done as of a past time (`as_of` on the inspection route, with a time zone), using the account status (`account_deactivations` history), placements, assignments, defaults and overrides valid then.
  - A deactivated account can't authenticate and gets no current access, but its access at a time it was active can still be reconstructed.
  - System Admin gives no implicit operational access, but may explicitly grant access to any account, including its own. That is how the first structure gets set up.
  - Unauthorized direct access returns 403 `{"detail": "Not permitted."}`. Lists omit units the caller can't manage.
  - Organization services check the caller's access snapshot themselves.
- Tasks:
  - Fields: a required title; optional description, priority (`low`/`normal`/`high`/`urgent`) and due time (sent with an offset, stored in UTC); plus status (`new`, `in_progress`, `completed`, `cancelled`), creator and scope unit. Tasks are never hard-deleted.
  - Visibility:
    - Anyone with `task.view` or `task.manage` at the task's scope, plus the task's creator and assignees, can see it.
    - An explicit `task.view` deny override hides it even from them.
    - Lists omit invisible tasks, and direct access returns 403.
  - Creating: only an active Member with `task.create` at the scope.
  - Assignees:
    - A task has one or more equal assignees, all active Members within its scope.
    - A Member is within a scope if their Team placement or their role's unit lies in it; this is what lets PMO Members be assigned PMO tasks.
    - After any role change, Team change, Team move, deactivation or task move, eligibility is re-evaluated. An assignee is removed only if their Member or account is inactive (`member_inactive`) or they are no longer within the task's current scope (`out_of_scope`); a role or Team change alone never removes them.
    - Manual removal can't remove the last assignee. Automatic removals can leave a task with none; the task stays open and the reason is recorded.
  - Who can do what:
    - Assignees: `new`/`in_progress` → `in_progress`/`completed`.
    - The active creator, or anyone with `task.manage` at the scope: edit, cancel, reopen (back to `new`), manage assignees and move. Managers can also make any valid status change.
  - Moving:
    - The creator needs `task.create` at the destination; a manager needs `task.manage` at both the source and destination.
    - Scope history is kept, subtasks move with the task, and assignees outside the destination are removed.
  - Subtasks: one level only. A subtask inherits its parent's scope and has its own independent status. Creating one needs `task.create` at the parent's scope.
  - Comments:
    - Plain text, no attachments. The creator, assignees and scoped managers may comment.
    - Authors can edit their own comments; the earlier text is kept in the history.
    - Deletion is soft: the comment stays listed with no body and a `deleted_at` time.
  - History: task-local `task_events` (lifecycle, assignment, scope, comment), separate from the central audit log.
  - Weekly series:
    - Requires a first due time and an end time.
    - Capped at 104 occurrences. This is an intentional anti-abuse limit: occurrences are generated up front, so an unbounded end time could create an unbounded number of tasks.
    - All occurrences, with duplicated subtask templates, are generated immediately, with no scheduler.
    - Editing, moving or stopping a series affects only future occurrences that haven't started, plus their direct subtasks; past, started, completed and cancelled occurrences never change.
    - Editing covers title, description, priority, assignees and subtask templates. Each template has a `key`: future subtasks are created, updated or, for removed templates, cancelled (soft-removed) to match. Subtasks that have already started are left alone.
    - Moving a series follows the task-move rules: the creator needs `task.create` at the destination; a manager needs `task.manage` at the destination and every affected source. It keeps each occurrence's scope history, removes only assignees ineligible at the destination, and trims the series' template assignees to those still eligible.
    - Stopping cancels future unstarted occurrences along with their unstarted subtasks.
    - Assignees who become invalid are removed from future occurrences, with the reason recorded.
  - Dependency direction is `access` ← `organization` ← `tasks`, enforced by a test.
- Announcements:
  - Fields: required title and body, creator, scope and state (`draft`/`published`/`withdrawn`). Every edit appends an immutable version. Nothing is hard-deleted.
  - Drafts:
    - Created by holders of `announcement.publish` at the scope.
    - Visible to their creator and to current `announcement.manage` holders at the scope, who can also edit them.
  - Publishing:
    - Immediate only, and needs `announcement.publish` at the scope.
    - The recipients are one or more active Members within the scope (by Team or role unit), fixed at publication.
  - Who can see a published announcement:
    - Direct recipients, even after they move to another scope.
    - The publisher.
    - Current `announcement.manage` holders at the scope.
  - Edit and withdraw: the publisher or a scoped manager. An edit adds a version.
  - Read state:
    - Read state is tracked per version. Opening (`GET`) a published announcement as a recipient marks its current version read; after an edit, a recipient hasn't read it until they open it again.
    - Recipients see only their own read state. The publisher and managers see every recipient's state (`/recipients`) and the version history (`/versions`).
  - Withdrawal: recipients still see the record (state and dates) but not its content; the publisher and managers keep the full content and history.
- Notifications:
  - In-app only. A notification references its source by `source_type`/`source_id` and is written in the same transaction as the change that caused it.
  - Categories: `task_assignment`, `task_update`, `task_comment`, `announcement_new` and `announcement_change`. All are enabled by default and can be turned off per user.
  - Who gets notified (never the actor):
    - Task assignment or removal: the affected assignee.
    - Task edit, status change or move: the creator and current assignees.
    - Task comment: the creator and current assignees.
    - Announcement publish, edit or withdraw: its direct recipients.
    - Weekly series: a series operation (create, edit, move, stop, or Members leaving its occurrences) never sends per-occurrence notifications. Each recipient gets at most one notification per category, pointing to the series (`source_type` `task_series`); the summary names the series and its weekly end date.
      - `task_assignment` covers affected assignees, with kind `series_assigned`, `series_unassigned` or `series_assignment_changed`.
      - `task_update` covers content, priority, template, scope or stop changes, with kind `series_updated`. It goes to the series creator and currently eligible series and subtask-template assignees, excluding the actor and anyone removed in the same operation, who get only the removal notification.
    - Actions on a single occurrence still notify per task.
  - Listing and opening re-check access to the source. Notifications whose source the reader can no longer see are redacted (`summary` null, `redacted` true); the source route still returns 403.
  - Read and delete apply only to the reader's own records. Deletion is soft.
- Calendar:
  - One entity with type `event` or `meeting`. Fields: title; start and end times (sent with an offset, stored in UTC, end after start); organizer; fixed scope; state (`scheduled` or `cancelled`); optional description; at most one location method (`location_text` or an http(s) `online_url`).
  - Not included: recurrence, drafts, RSVP, attendance, attachments, comments or hard deletion.
  - Creating: an active Member with `calendar.create` at the scope. One or more invitees, each an active Member within the scope (Team or role unit).
  - Who can see an event: the active organizer, current invitees (who keep access after moving scope), and current `calendar.manage` holders at the scope. Lists omit events the caller can't see, and direct access returns 403.
  - Edit, cancel and manage invitations: the organizer or a scoped manager. An edit that includes `scope_unit_id` is rejected (422); the scope can't change.
  - Invitation privacy: only the organizer and scoped managers get the full current invitee list (`invitee_member_ids`) and the invitation history. Invitees see the event details and only their own invitation (`my_invitation`); `invitee_member_ids` is null for them.
  - Removing an invitee ends their invitation row (revoking access) while keeping it in the invitation history. A new invitee must be within the scope at that time, and the last invitee can't be removed.
  - Cancelling keeps everything and makes the event read-only.
  - History: event-local `calendar_event_history` (created, updated, cancelled, invitee added or removed).
  - "My calendar" merges accessible events overlapping the range with due dates of `new` and `in_progress` tasks the caller created or is assigned to. Task access is re-checked; the due dates are derived through `tasks.service.due_tasks` and never stored or edited in calendar.
  - Notifications (`calendar_event` category, enabled by default):
    - creating: one `invited` per invitee, not the organizer;
    - adding an invitee: `invited` to that invitee;
    - editing: one `updated` to current invitees, not the actor;
    - cancelling: one `cancelled` to current invitees, not the actor;
    - removing an invitee: silent.
- Audit log:
  - One record per successful logical change, written in the same transaction as the change, so both commit or roll back together. Rejected or failed operations write nothing. Multi-row operations (series create/edit/move/stop, Member deactivation) write one record, not one per row.
  - Audited actions:
    - access: `account.bootstrapped`, `account.password_changed`, `account.password_reset`, `account.locked_out` (existing accounts only; unknown usernames are never logged), `system_admin.granted`/`revoked`, `role_default.created`/`ended`, `permission_override.created`/`ended`;
    - organization: `org_unit.created`/`moved`/`archived`, `member.provisioned`, `member.profile_updated` (changed field names only), `member.team_changed`, `member.role_changed`, `member.deactivated`/`reactivated` (cover the account and sessions too);
    - tasks: `task.created`/`updated`/`status_changed`/`cancelled`/`reopened`/`moved`, `task.assignee_added`/`assignee_removed` (also automatic removals after a membership change), `task_comment.created`/`edited`/`deleted`, `task_series.created`/`updated`/`moved`/`stopped`/`assignees_removed`;
    - announcements: `announcement.draft_created`/`published`/`edited`/`withdrawn`;
    - notifications: `notification_preferences.updated` only (reads and deletes are not audited);
    - calendar: `calendar_event.created`/`updated`/`cancelled`/`invitee_added`/`invitee_removed`.
  - Not audited: reads and listings, sign-in success, normal sign-out and sign-out-all, notification read/delete, opening an announcement.
  - Privacy: metadata keys are allowlisted per action, and keys that look like secrets, content or contact data are refused at definition time. Only IDs, states, counts, timestamps, titles (cut to 120 characters) and names of changed fields are stored. Never stored: passwords, hashes, tokens, credentials, task/series/event descriptions, comment and announcement bodies, event locations and URLs, override reasons, Member profile values.
  - Reading: System Admin only (an explicit audit-only exception to "no implicit operational access"); it returns only stored metadata and grants nothing on the source resources. Newest first by `sequence`, `limit` 1–200 (default 50), `cursor` = the previous page's `next_cursor`; filters for a time range (`occurred_from` inclusive, `occurred_to` exclusive, with offsets), action, actor, resource type/id and scope. No edit, delete, export or bulk API.
  - No request/correlation id exists in current conventions, so none is stored. No IP or user-agent tracking.
  - History boundary: the log starts when migration `6b1e9c4d2a7f` is applied. Earlier changes are not backfilled; domain history tables (`task_events`, placements, etc.) remain the record for that period.
- Dependency direction: `access` ← `organization` ← `tasks` / `announcements` / `calendar` → `notifications` → `access`. `calendar` reads `tasks` (due dates) only. `notifications` imports no source module. Every domain may import `audit`; `audit` imports no domain.

## Functional scope

Five internal domains:

1. Access & accounts
2. Organization & members
3. Tasks, workspaces & analytics
4. Communication & reminders
5. Governance & audit

**Platform boundary:** Recruitment & Selection is a separate platform with its own entry point. It is not one of these domains.

## Critical rules affecting backend foundations

- **Authorization** = role defaults + organizational scope + per-user overrides.
- **System Admin alone** manages permissions and member administration.
- **Preserve historical meaning.** Prefer archival or deactivation over destructive deletion.
- **Recruitment & Selection stays separate.** Do not invent an integration contract with it.

## Unresolved technical decisions (do not guess; get explicit approval)

- Further permissions and their defaults for later domains
- Pagination and filtering conventions for task lists, as volume grows
- Provisioning of non-Member accounts other than through bootstrap
- Audit retention, export and correlation ids (the central log itself is decided: M6A)
- Background jobs and scheduling for reminders; notification delivery channels
- API conventions (error format, pagination, IDs, timestamps/timezones)
- Archival column conventions for future domain tables
- Cleanup and retention for expired sessions and stale throttle rows
- Deployment target, containerization, and CI

## Milestone status

| Milestone | Status |
|---|---|
| M0: Repository baseline and state record | Done |
| M1: FastAPI foundation (uv, config, health endpoint, tooling, tests) | Done |
| M2: Persistence foundation (SQLAlchemy async, Alembic, local PostgreSQL, docs toggle) | Done (verified against live PostgreSQL in M3B) |
| M3A: Identity & access plan | Done |
| M3B: Authentication & account-security foundation | Done |
| M4A: Organization structure, Members, roles and scoped access | Done |
| M5A: Task-management foundation (tasks, subtasks, comments, history, weekly series) | Done |
| M5B: Announcements and in-app notifications | Done |
| M5C: Calendar events and meetings, merged calendar with task due dates | Done |
| M6A: Central append-only audit log with System Admin read API | Done |
| M7: Backend release-readiness and integration verification | Done |

## Release readiness (M7)

Verified (2026-10-12):
- From an empty, disposable database: all 12 migrations apply, a full downgrade to base and a re-upgrade work, `alembic check` is clean, the bootstrap CLI creates the first System Admin once, and a second run is refused. The database was then dropped.
- Fixed: the bootstrap CLI failed on every database since M6A, because run alone it did not load the organization models that `audit_records` references. It now loads all models; a clean-interpreter test guards this.
- `tests/test_end_to_end.py`: bootstrap → explicit grant → first Administration and Team → provisioned Members → task (assignment, status, comment) → announcement (recipients, read state) → calendar invitations → notifications and redaction → audit inspection without operational access. No secrets or content reach the audit log or the logs.
- `tests/test_release_readiness.py`: over the whole mounted route tree, every unsafe route needs a session, a CSRF token and a usable password. Exceptions: sign-in (public), plus sign-out, sign-out-all and change-password (allowed with a temporary password). OpenAPI matches the mounted routes exactly. Staging/production configuration is validated, and production cookies are Secure.

Not verified (deployment prerequisites): hosting target, HTTPS/TLS termination and reverse proxy (needed for the Secure cookies), same-origin frontend serving, production PostgreSQL provisioning, backups and secret management, process supervision and worker count, log collection, CI, and cleanup of expired sessions and throttle rows.

Deferred scope (not implemented): files, chat and direct messages, email/push notifications, RSVP and attendance, recurring calendar events, reminders, external integrations, and Recruitment & Selection (a separate platform).

## Next intended work

To be scoped. Candidates include reminders, task workspaces and analytics, and the member directory. Each needs approved business rules first.

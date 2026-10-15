# KORA Frontend — Implementation Roadmap

> Companion: [`frontend_PROJECT_STATE.md`](./frontend_PROJECT_STATE.md) records what is *actually* built and where to resume. If the two documents ever disagree with the code, **the code wins** — fix the documents.
> Sources of truth: `../api/API_CONTRACT.md` (backend Milestone 8B, 2026-10-12) for every endpoint/field/enum; `../specification/KORA_Internal_Operations_Platform_Spec_v3.md` for product behavior (its **Implementation Alignment Addendum**, last section, says what the backend really supports); `../هوية كورة/KORA_Frontend_Design_Language_Master_v2.md` for brand/UI.

## 0. How to use this file (new AI session)

1. Read `frontend_PROJECT_STATE.md` → find "Next milestone".
2. Read that milestone below. Read only the spec/contract sections it names (don't re-read whole docs).
3. Work **one milestone at a time**; verify (`npm run check` + manual/browser checks listed); then update both docs; then continue.
4. Never invent endpoints, fields, or business rules. Unsupported things are shown as honest "not available yet" states or omitted, and tracked in §4 (Gaps).

## 1. Architecture (decided)

Simple feature-based React. Three top-level directories under `src/`:

```
src/
  main.tsx                 entry
  app/                     app setup only: providers, router, layout/shell, route guards, global styles
  features/<feature>/      one folder per major feature (auth, access, organization, members, tasks, ...)
      api.ts               ALL HTTP calls + TanStack Query hooks for the feature (no fetch in components)
      types.ts             types copied 1:1 from API_CONTRACT (only if the feature needs them)
      components/ , pages/ created only when the feature has more than ~3 files
  shared/
      api/                 http client (cookies, CSRF, errors), query client
      ui/                  reusable presentational components (Button, Field, Modal, Table, Chip, states...)
      i18n/                tiny dictionary-based translations (ar default, en)
      lib/                 small helpers (dates, permissions, classnames)
      brand/ , assets      official logos/patterns
public/fonts/              Ghroob OTFs
```

Rules: `features/*` may import `shared/*` and (sparingly) other features' public `api.ts`/types; `shared/*` never imports `features/*` or `app/*`; `app/*` wires features together. No barrel files, no generic "services/repositories/stores" layers, no global state library (server state = TanStack Query; local UI state = React state; session/permissions = one React context in `features/auth`).

**Stack:** React + TypeScript (strict) + Vite; `react-router`; `@tanstack/react-query`; CSS Modules + one global tokens file (no CSS framework); `lucide-react` icons; Vitest + React Testing Library for tests; ESLint + Prettier-free (ESLint only). Add libraries only when a milestone genuinely needs one (e.g. a form lib is NOT planned: plain controlled forms).

**Dev/prod networking:** the backend has **no CORS** and cookies are `Secure; SameSite`. The app must call the API same-origin as `/api/v1/...`. Dev: Vite proxy `/api` → `http://127.0.0.1:8000`; open the app on `http://localhost:5173` (localhost counts as secure for `Secure` cookies). Prod: serve the built app and `/api` from the same origin (reverse proxy) — deployment itself is out of scope here.

**Auth model in the client:** `kora_session` is HttpOnly (JS can't see it); CSRF = read the `kora_csrf` cookie (or the `csrf_token` from sign-in/change-password) and send `X-CSRF-Token` on every non-GET request. 401 anywhere (except sign-in) ⇒ session-expired flow. 403 `"Password change required."` ⇒ forced password-change screen. No tokens in localStorage.

**i18n/RTL:** Arabic is the default and first-class (`<html dir="rtl" lang="ar">`), English available via a language switch (`dir` flips). Use CSS logical properties everywhere (`margin-inline-start`, etc.). Dictionary-based `t('key')`; no i18n library. Dates via `Intl.DateTimeFormat` using the active locale; **outgoing datetimes always carry a UTC offset** (use `Date#toISOString()`).

**Branding (Level 1 "Utility" intensity for the app; the sign-in page may use Level 2):** navy `#2D3B70` anchors nav/primary actions; fuchsia/coral/green are selective accents; Ghroob font from the supplied OTFs; official logo files only (never `*old*`); patterns only in empty states / sign-in / page-header moments, never behind forms or tables. Permission semantics: role words are never used to decide UI — **only** `GET /access/me` decisions and `is_system_admin`.

## 2. Milestone overview

| # | Milestone | Status |
|---|---|---|
| M1 | Foundation: scaffold, design system, API client, router/shell skeleton, i18n, test tooling | **Completed** 2026-10-15 |
| M2 | Authentication & Access: sign-in, lockout, forced password change, session bootstrap, permission-aware navigation, My Account | **Completed** 2026-10-15 (verified with automated tests on contract-shaped fakes + browser layout; **live-backend smoke test still owed** — see state doc) |
| M3 | System Admin — Access: role defaults, overrides, effective-access viewer, System Admin grants | **Completed** 2026-10-15 (mock-verified; not yet seen live/in browser with data) |
| M4 | Organization & Members: units (create/move/archive/tree) + Admin member lifecycle (one-time temp password) | **Completed** 2026-10-15 (mock-verified) |
| M5 | Tasks: list/filters, create, detail, edit, status, assignees, move, subtasks, comments, history; Home & My Tasks | **Completed** 2026-10-15 (tests + live backend) |
| M6 | Weekly task series | **Completed** 2026-10-15 (tests + live backend) |
| M7 | Announcements & Notifications (incl. bell, preferences, deep links, redaction) | **Completed** 2026-10-15 (tests + live backend) |
| M8 | Calendar (events, meetings, invitees, unified calendar) | **Completed** 2026-10-15 (tests + live backend) |
| M9 | Admin audit log (read-only, cursor pagination) | **Completed** 2026-10-15 (tests + live backend) |
| M10 | Hardening: responsive/RTL/a11y pass, gap page, recruitment link, performance, end-to-end smoke vs real backend | **Completed** 2026-10-15 (recruitment link deliberately not added: no URL, G9) |

Order rationale: the very first System Admin has *no* operational access until they grant themselves an override (contract §3.4) → access admin (M3) must precede organization (M4: needs `organization.manage`), which must precede tasks (M5: needs units and Members).

---

## 3. Milestones in detail

### M1 — Foundation  · Status: Completed (2026-10-15) — see state doc for what was built; `@/` alias = `src/`
**Scope**
- Scaffold Vite + React + TS (strict) in `frontend/`; ESLint; Vitest + RTL; scripts `dev`, `build`, `lint`, `typecheck`, `test`, `check` (= lint+typecheck+test+build).
- `public/fonts/` ← five Ghroob OTFs; `@font-face` (weights 300/400/500/700/800). Copy only the needed official brand assets into `src/shared/brand/` (nav lockup, white lockup, English wordmark SVG, ball mark, `pattern-9.svg`, `pattern-8.svg`; **not** `old` files, **not** the 6 MB `mesh-0.png` yet).
- `app/styles/tokens.css`: brand tokens, neutral UI tokens, spacing, radius, type scale (from Design Language §3, §9, §10, §30); global reset; focus-visible ring; `prefers-reduced-motion`.
- `shared/api/http.ts`: `fetch` wrapper (`credentials: 'same-origin'`, JSON, CSRF header from `kora_csrf` cookie on non-GET), typed `ApiError {status, detail, retryAfter?}` normalizing the contract's two `detail` shapes (string | validation-issue list), 204 handling. Global hooks for 401 (session expired) and 403 `"Password change required."`.
- `shared/api/queryClient.ts` (no retry on 4xx; sensible stale time).
- `shared/i18n`: `ar` + `en` dictionaries, `useT()`, language switch state persisted in `localStorage`, sets `<html lang dir>`.
- `shared/ui`: Button (variants, loading), Field/TextInput/Select/Textarea (label, hint, error association), Modal/ConfirmDialog (focus trap, Esc), Chip, Spinner/Skeleton, `EmptyState`, `ErrorState` (retry), `PageHeader`, Table wrapper (overflow strategy), `Toast` (live region).
- `app/`: providers, router with placeholder routes, `AppShell` (navy side nav on desktop → bottom nav + "More" on mobile; header with account slot and notification slot), `NotFound`, `AccessDenied`, `ConnectionFailure`, `SessionExpired` pages.
- Vite dev proxy `/api` → `127.0.0.1:8000`; `.env.example`; `frontend/README.md` (how to run/check; how the backend must run).
- `.gitignore` for `node_modules`, `dist`.
**Dependencies:** none.
**Approach:** build shell with *placeholder* nav entries; real permission-aware nav arrives in M2.
**Acceptance:** `npm run check` passes; dev server renders shell in RTL and LTR; fonts load; unit tests for `http.ts` (CSRF header, error normalization, 204) and i18n pass; no horizontal overflow at 375 px and 1440 px (browser check).

### M2 — Authentication & Access  · Status: Completed (mock-verified; live smoke owed)
**Scope** (Spec §1 §9–§11, §17–§21, §26; Contract §2, §6)
- `features/auth`: `SessionProvider` (loads `GET /auth/me`, then `GET /access/me` when `must_change_password` is false); `useSession()`; `useCan(permission, unitId?)` and `useVisibleUnits(permission)` built **only** from `EffectiveAccessResponse` (a unit "allowed" if `permissions[p].units[u].allowed`); `is_system_admin` only gates `/admin` UI.
- Sign-in page (username, password; generic 401 message "The username or password is incorrect."; **429** → lockout message with `Retry-After` countdown; 422 handling); "Forgot password?" → informational text telling the user to contact the System Admin (no self-service).
- Forced password-change screen when `must_change_password` (blocks everything else; only change/sign-out allowed). After change, response carries a **new** session + CSRF → refetch session.
- Route guards: `RequireAuth`, `RequirePermission`, `RequireAdmin`; 401 → SessionExpired then sign-in with return-to; direct links preserved across sign-in.
- Permission-aware navigation: groups/items shown only if the user can reach them; empty groups hidden. Initial nav map (items link to M3+ routes, shown only if the route exists/implemented to avoid dead links): Home, My Tasks/Tasks, Calendar, Announcements, Organization (needs `organization.manage` somewhere), Admin (`is_system_admin`).
- My Account page: username, system-admin flag, change password, sign out, sign out of all devices (with confirm). Note: the contract has **no** member-profile/role endpoint for non-admins — show only what `/auth/me` returns; do not fake role/scope text (Gap G3).
**Dependencies:** M1. **Test against:** local backend (README: bootstrap CLI prints the first admin's temp password).
**Acceptance:** unit tests for `useCan`, guard behavior, lockout countdown; manual browser flow vs. real backend: bootstrap admin → sign in → forced change → shell → sign out all → session-expired path; refresh keeps session; deep link survives sign-in.

### M3 — System Admin: Access  · Status: Completed (mock-verified)
**Scope** (Spec Addendum A, C2; Contract §7)
- `/admin/access` area (RequireAdmin) with sections: **Role defaults** (list incl. ended, add `{role_key, permission}`, end), **Permission catalog** (read-only, 8 keys), **Overrides** per account (list, create with required `reason` 1–1000, unit picker, effect grant/deny, end — no expiry field; handle 409 duplicates), **Effective access** viewer (`as_of` optional with offset; table permission × unit with source and deciding unit), **System Admins** (list, grant, revoke; handle "final admin" 409).
- Account/unit pickers: accounts from `GET /admin/members` (needs M4 for the full member UI, but the list call + `lookup` hook lives in `features/members/api.ts` and is created here); units from `GET /access/me` unit list (names/kinds/ids for all units — the only unit lookup non-managers have) with `GET /organization/units` as enrichment (parent_id/status) when the admin holds `organization.manage`.
- Prominent **"Grant yourself an operational override"** affordance/explainer (System Admin ≠ operational access; first-structure bootstrap path).
- Confirmation dialogs describing effects (Spec §15).
**Dependencies:** M2.
**Acceptance:** all 11 admin access endpoints exercised; confirm dialogs on end/revoke; real-backend manual run: admin grants self `organization.manage` at KORA → nav "Organization" appears after refetch of `/access/me`.

### M4 — Organization & Members  · Status: Completed (mock-verified)
**Scope** (Spec §2 Org & Members; Contract §8)
- `features/organization`: unit tree (built from `GET /organization/units`; handles that this lists only units where caller has `organization.manage`); create Administration (under KORA) / Team (under active Administration); move Team (to another active Administration); archive (with 409 message surfacing "Cannot archive: …"); note 403-for-unknown-unit behavior. No rename/unarchive (Gap G6).
- `features/members` (Admin only): list with client-side search/filter (name, username, status, team); detail; **provision** (profile fields, username, team, role incl. `administration_id` rule) → **one-time temporary-password panel** (copy button, warning it's never shown again, not stored); `PUT` profile as **full replacement** (form pre-filled with all fields so omitted ≠ accidentally null); change team; change role; deactivate (confirm; "final System Admin" 409); reactivate (team+role); reset password (one-time display). Email validation mirrors contract. 
- Excel import is **not** built (Gap G5) — show nothing, or a disabled "not available" note in the gap list only.
**Dependencies:** M3 (override to get `organization.manage`).
**Acceptance:** all 5 unit + 9 member endpoints wired; unit tests for role/administration_id form rule and temp-password panel; real-backend run: create Administration → Team → provision Member → sign in as that Member (forced password change) → deactivate.

### M5 — Tasks (+ Home, My Tasks)  · Status: Completed (live-verified). "My Tasks" = the `?mine=1` filter on /tasks
**Scope** (Spec §3 selectively, Addendum C4; Contract §9.1–9.3, §14)
- `features/tasks`: list (`GET /tasks` filters `status`, `scope_unit_id` in the URL query), grouped/sortable client-side; create (title, description, priority, due_at with offset, scope unit, ≥1 assignees); detail with edit (`PATCH` partial; only changed fields), status actions strictly per transition table (show only legal next states; surface 409/403), assignee add/remove (422 last assignee), move (not for subtasks), subtasks (one level), comments (add/edit/delete own; deleted placeholder; never reconstruct text), history timeline (render each `kind`; honor `content_removed`).
- Priority labels: explicit mapping low/normal/high/urgent → localized labels shown 1:1 (no "Important" invented). Status labels 1:1; no "Not Completed".
- Home: derived summary clearly labelled "from tasks visible to you" (no analytics API — Gap G7) + due-soon + unread notifications slot (filled in M7) ; My Tasks = visible tasks where the user is creator/assignee (filter client-side by member id — requires own member id, see G1).
- Member name resolution: names via `GET /admin/members` **only for System Admins**; others see the member-id placeholder "Member" (G1). Don't call admin endpoints for non-admins.
**Dependencies:** M4. **Blocker/decision (G1):** non-admin accounts cannot learn their own `member_id`, nor list assignable Members → they cannot create tasks or filter "my tasks" reliably. Raised with the user; implement admin-complete path + graceful degraded path, keep wiring ready for a backend change.
**Acceptance:** all 15 task endpoints wired; unit tests for transition matrix and permission-based action visibility; real-backend run through create → in_progress → subtask → comment → completed → reopen.

### M6 — Weekly task series  · Status: Completed (live-verified)
**Scope** (Contract §9.4): create (first_due_at, ends_at, ≤104 occurrences client hint, subtask templates), detail (occurrence list linking to tasks), edit (complete template list with `key` semantics), move, stop (confirm; explain only future unstarted occurrences are affected). Occurrence tasks show a series badge in M5 views.
**Dependencies:** M5. **Acceptance:** 5 endpoints wired; tests for template-key handling; real-backend run.

### M7 — Announcements & Notifications  · Status: Completed (live-verified)
**Scope** (Spec §4 only as the addendum allows; Contract §10, §11)
- Announcements: list (state filter), draft create/edit, publish with recipient picker (needs member lookup, G1), withdraw (confirm), detail (note: opening marks read for recipients; withdrawn → `content_hidden` placeholder), versions, recipient read-status. **No** scheduled publishing, no DMs/inbox/replies (G4).
- Notifications: header bell + unread count, list, read / read-all / delete / delete-all, preferences (6 categories), deep-link by `source_type`/`source_id` to the right page (task, task_series, announcement, calendar_event); `redacted` → neutral text; source 403 → AccessDenied page.
- Fill Home's notification slot.
**Dependencies:** M5 (+M6 for series links). **Acceptance:** 8 + 8 endpoints wired; redaction test; polling interval for unread count (simple `refetchInterval`, no websockets).

### M8 — Calendar  · Status: Completed (live-verified). UI is a month agenda grouped by day (not a month grid)
**Scope** (Contract §12; Addendum C5): month/agenda view driven by `GET /calendar?from&to` (offsets, ≤366 days), personal task due dates (labelled "your tasks"), events/meetings create/edit/cancel, invitees add/remove, invitations + history, online URL vs location mutual exclusivity. No RSVP/recurrence.
**Dependencies:** M5. **Acceptance:** 10 endpoints wired; date-range & offset unit tests; real-backend run.

### M9 — Admin audit log  · Status: Completed (live-verified)
**Scope** (Contract §13): filterable, cursor-paginated ("load more") list (newest first), record detail drawer with `before`/`after`, action catalog labels; read-only; no export (G8).
**Dependencies:** M3. **Acceptance:** 2 endpoints wired; filter→query-param tests.

### M10 — Hardening & release readiness  · Status: Completed (see state doc for what was and was not covered)
**Scope:** full responsive + RTL + keyboard/a11y pass (Design Language §37 checklist) on every page; "Not yet available" gap page for product gaps G1–G9 (Addendum D.2); Recruitment & Selection nav link **only once a verified URL is supplied** (G9); optimize brand assets (SVG; WebP/AVIF derivative of mesh if used), route-level code splitting; error-boundary; consistent confirm/empty/loading/error states audit; end-to-end smoke script vs a real backend run; update docs.
**Acceptance:** `npm run check` green; Lighthouse-style sanity (no layout overflow at 375/768/1440); checklist in state doc ticked with evidence.

---

## 4. Gaps, risks, decisions

| ID | Item | Status |
|---|---|---|
| G1 | **Non-admin accounts have no member lookup**: `AccountResponse` lacks `member_id`; `GET /admin/members` is admin-only; tasks/announcements/calendar expose only member UUIDs. ⇒ non-admins can't resolve names, pick assignees/recipients/invitees, or identify "me". Needs a backend decision (e.g. `member_id` on `/auth/me` + a scoped member lookup). Frontend must not guess. | **Resolved 2026-10-15**: backend now returns `member_id` on the account response and exposes `GET /organization/members` (contract §6, §8.1a; backend tests in `tests/organization/test_directory.py`). Limitation: deactivated/out-of-scope Members can't be named by id → UI shows "Member (not visible to you)". |
| G2 | Unit names for non-managers come only from `GET /access/me` (all units × permissions). Used as the unit lookup. | Decided |
| G3 | No endpoint exposing the caller's role/Team/scope text → My Account cannot show role/affiliation. | Open (backend) |
| G4 | No Inbox/DM/reply/scheduled broadcast/reminders API. | Not built (honest gap) |
| G5 | No Member Excel import API. | Not built |
| G6 | No unit rename/unarchive endpoint. | Not built |
| G7 | No analytics/dashboard API; no task archive/restore; no team-wide assignment. Home shows only summaries derived from visible tasks, labelled as such. | Not built |
| G8 | No audit export. | Not built |
| G9 | Recruitment & Selection URL not supplied; no integration API. | Open (needs URL) |
| G10 | Pagination absent except audit → lists load fully; revisit if lists get large. | Accepted |
| G11 | Ghroob OTF web-serving licence unconfirmed (Design Language §44.4). Ship OTF now; replace with official WOFF2 when available. | Open (owner) |
| G12 | `GET /calendar/events` has no range filter; use `GET /calendar` for ranges. | Decided |
| R1 | Cookies are `Secure`; app must be opened on `localhost`/HTTPS and same-origin to `/api`. | Handled via Vite proxy |
| R3 | RESOLVED for M1–M5 on 2026-10-15 (backend + Postgres run locally; sign-in, forced change, access override, units, members, tasks all exercised live). Original note: no live backend was available when M1–M2 were built (Docker daemon not running). Every milestone so far is verified against fakes only. A live smoke run (bootstrap admin → sign in → forced change → shell) must happen as soon as the backend is up; add findings to the state doc. | Open |
| R2 | Contract is "Milestone 8B" — verify against the running backend; trust the backend if they differ and record it. | Ongoing |

## 5. Definition of done (every milestone)
`npm run check` green · new logic has tests · manual verification against the real backend where the milestone says so · all four UI states (loading/empty/error/success) present · RTL and mobile (375 px) checked · no dead links/fake buttons · both docs updated (status table above + state file "Next milestone").

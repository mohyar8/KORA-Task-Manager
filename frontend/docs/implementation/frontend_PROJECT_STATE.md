# KORA Frontend — Project State

_Last updated: 2026-10-15. Describes what is **actually in the repo**. Plan and milestone detail: [`FRONTEND_ROADMAP.md`](./FRONTEND_ROADMAP.md). If this file disagrees with the code, trust the code and fix this file._

## Where to resume
**All ten planned milestones (M1–M10) are complete.** Nothing is queued. Remaining work is the open items at the bottom (Recruitment URL, font licence, a deeper accessibility audit, optional polish) and any new product decisions.

## Milestone status
| # | Milestone | Status |
|---|---|---|
| M1 | Foundation | **Completed** (2026-10-15) |
| M2 | Authentication & Access | **Completed** (2026-10-15; mock-verified, live smoke owed) |
| M3 | System Admin: Access | **Completed** (2026-10-15; mock-verified) |
| M4 | Organization & Members | **Completed** (2026-10-15; mock-verified) |
| M5 | Tasks (+ Home, My Tasks) | **Completed** (2026-10-15; live-verified) |
| M6 | Weekly task series | **Completed** (2026-10-15; live-verified) |
| M7 | Announcements & Notifications | **Completed** (2026-10-15; live-verified) |
| M8 | Calendar | **Completed** (2026-10-15; live-verified) |
| M9 | Admin audit log | **Completed** (2026-10-15; live-verified) |
| M10 | Hardening | **Completed** (2026-10-15) |

## What exists (end of M1)
Project lives in `frontend/` (no frontend code existed before M1; `docs/` pre-existed). Toolchain: Vite 8, React 19, TypeScript (strict, `@/` → `src/`), react-router 8 (`createBrowserRouter`), TanStack Query 5, lucide-react, Vitest 5 + Testing Library, ESLint 10. CSS Modules + `src/app/styles/global.css` (tokens, Ghroob `@font-face`, reset, focus ring, reduced-motion).

```
src/main.tsx                      entry (Providers + RouterProvider)
src/app/Providers.tsx             I18nProvider > QueryClientProvider > ToastProvider
src/app/router.tsx                `routes` array (exported for tests) + `router`; shell wraps all routes
src/app/AppShell.tsx (+css)       navy sidebar (≥900px) / navy mobile header + bottom nav with "More" modal (>4 items); language switch in header; skip link
src/app/nav.ts                    navItems (only Home so far) — M2 filters by permissions, each milestone appends
src/app/HomePage.tsx              placeholder; SystemPages.tsx = NotFound / AccessDenied / ConnectionFailure / SessionExpired (routes /access-denied, /connection-failure, /session-expired)
src/shared/api/http.ts            ONLY fetch caller: same-origin, JSON, X-CSRF-Token from `kora_csrf` cookie on non-GET (fallback `setCsrfToken`), ApiError{status,detail,retryAfter} (status 0 = network failure), fieldErrors(), setApiHandlers({onUnauthorized,onPasswordChangeRequired}); `http.get/post/put/patch`; sign-in must pass `{isSignIn:true}` so its 401 isn't treated as expiry
src/shared/api/queryClient.ts     no retry on 4xx
src/shared/i18n/                  messages.en.ts (key set) / messages.ar.ts (must match; test enforces) / translate.ts / i18n.tsx (I18nProvider, useI18n, useT; default Arabic RTL; persisted in localStorage `kora.locale`; sets <html lang dir>)
src/shared/ui/                    Button, Field (TextField/TextAreaField/SelectField), Modal + ConfirmDialog (native <dialog>), Feedback (Chip, Skeleton, StateBlock, EmptyState, ErrorState, ToastProvider/useToast), Layout (PageHeader, TableWrap, Card)
src/shared/brand/                 kora-nav-lockup.png, kora-lockup-ball.png, kora-lockup-white.png, kora-english.svg, kora-main-tight.svg, pattern-9.svg (official; copied from docs/هوية كورة)
public/fonts/                     5 Ghroob OTFs; public/favicon.png (ball mark)
vite.config.ts                    `/api` proxy → KORA_API_URL (default http://127.0.0.1:8000); vitest jsdom config
../.claude/launch.json            (repo root) preview server config "kora-frontend" (`npm --prefix frontend run dev`)
```
Tests (12, all pass): `http.test.ts` (CSRF, query string, 204, error normalization, 401/403 handlers, network failure), `i18n.test.tsx` (key parity, default RTL + switch), `app.test.tsx` (shell render, not-found).

## What exists (added in M2)
```
src/features/auth/types.ts          Account, SessionResponse, Permission, UnitDecision, PermissionAccess, EffectiveAccess (contract §3.1/§6/§7.4)
src/features/auth/api.ts            fetchMe (401 → null), fetchAccess, signIn, signOut, signOutAll, changePassword; query keys meKey/accessKey
src/features/auth/session.ts        SessionContext + useSession(): {status: loading|anonymous|passwordChange|ready|error, account, access, expired, error, retry, applySession, endSession}
src/features/auth/SessionProvider.tsx   me + access queries; installs http handlers (401 after being signed in ⇒ expired + drop all non-session cache; 403 "Password change required." ⇒ refetch me); applySession stores csrf; access refetches on window focus (admin may change it)
src/features/auth/permissions.ts    allowedUnits / canAt / canAnywhere / allUnits — decisions ONLY from /access/me; allUnits = the unit-name lookup for everyone (G2)
src/features/auth/guards.tsx        RequireAuth (layout route; redirects to /sign-in with {from}, or /change-password), RequirePermission (any-unit), RequireAdmin (is_system_admin)
src/features/auth/SignInPage.tsx    generic 401 text, 429 lockout countdown from Retry-After (form disabled), "Forgot password?" = contact System Admin, session-ended notice
src/features/auth/ChangePasswordForm.tsx / ForcedPasswordPage.tsx / AccountPage.tsx   (account page: username, System Admin chip, change password, sign out, sign out of all devices with confirm; NO role/scope text — G3)
src/features/auth/AuthLayout.tsx    standalone layout: quiet form + one cropped pattern-9 composition (desktop), navy lockup bar (mobile)
src/app/nav.ts                      NavItem {permission?, adminOnly?} + visibleNavItems(access, isAdmin); no groups yet (flat list; add groups when >~6 items)
src/app/router.tsx                  /sign-in, /change-password (public); everything else under RequireAuth > AppShell
src/shared/ui/Button.tsx            + LinkButton;  Feedback.tsx + AccessDenied
src/test/fakeApi.ts                 installFakeApi(routeTable) fetch stub, `account`, `accessFor(['perm@unit'])` — use for all feature tests
```
http.ts: option renamed `expectUnauthorized` (was isSignIn): pass it for calls where a 401 is an expected answer (sign-in, boot-time /auth/me).
vite test config has `globals: true` (needed for RTL auto-cleanup).
Tests now: 25 (http 7, i18n 3, permissions 4, app 4, auth flow 7).

## What exists (added in M3)
```
src/features/access/types.ts        RoleKey/ROLE_KEYS, PERMISSIONS, Override, RoleDefault, SystemAdmin, KORA_UNIT_ID (contract §4, §7)
src/features/access/api.ts          query/mutation hooks for all 11 admin-access endpoints (+ keys); every access mutation invalidates ['admin'] AND /access/me so the admin's own nav updates
src/features/access/labels.ts       permissionLabel/roleLabel/unitKindLabel/decisionLabel(t, value) — unknown values shown raw
src/features/access/accounts.ts     useAccountOptions(): own account + Members + System Admins (no account-list endpoint exists; first admin isn't a Member)
src/features/access/AdminAccessPage.tsx   /admin/access, tabs in URL (?tab=accounts|roles|admins, &account=<id>): AccountAccessTab (picker, bootstrap banner "grant myself organization management" prefilled organization.manage@KORA, overrides table + add modal with required reason, end with confirm, EffectiveAccessView matrix with optional as_of), RoleDefaultsTab, SystemAdminsTab (grant/revoke, 409 final-admin message inline)
src/features/members/{types,api}.ts Member type + useMembers (admin-only GET /admin/members); M4 extends
src/shared/ui/Tabs.tsx, Feedback.InlineError (server detail shown as-is), src/shared/lib/format.ts (formatDate/formatDateTime: Latin digits + Gregorian in ar; localInputToIso → ISO with Z)
nav: "Administration" (adminOnly) → /admin/access, route wrapped in RequireAdmin
```
Tests now 34 (+ access.test.tsx 7, format 2).
**M3 verification gap:** pages were verified by RTL tests with a fake API; they were NOT looked at in a browser with real data (no backend/session). Visual check of tables on a 375 px screen is owed.

## What exists (added in M4)
```
src/features/organization/api.ts          Unit type; useUnits(enabled) (GET /organization/units), useCreateUnit, useMoveTeam, useArchiveUnit (invalidate units, /access/me and members)
src/features/organization/directory.ts    useUnitDirectory(): id→{name,kind,status?,parentId?}, nameOf, teams[], administrations[] — names from /access/me (everyone), status/parent from /organization/units when the caller manages
src/features/organization/OrganizationPage.tsx   /organization (RequirePermission organization.manage; nav item has permission: 'organization.manage'): tree from parent_id; Add administration (on KORA) / Add team (on administrations) / Move (teams; destinations = other active administrations the caller manages) / Archive (administrations+teams, never KORA/PMO; confirm explains effect; server 409 text shown inline); team Member counts only for System Admins
src/features/members/api.ts + types.ts    all 9 admin member endpoints (list/get/provision/PUT profile/team/role/deactivate/reactivate/reset-password); helpers draftToProfile (blank→null), roleFieldsFor (administration_id only for administration_manager), validateProfile, isValidEmail, USERNAME_PATTERN
src/features/members/fields.tsx           ProfileFields, RoleFieldsInput (shows Administration select only for administration_manager), TeamSelect
src/features/members/MembersPage.tsx      /admin/members (RequireAdmin): client-side search (name/username/university id) + status/team/role filters; "Add member" modal → POST → TemporaryPasswordDialog
src/features/members/MemberDetailPage.tsx /admin/members/:memberId: profile form = full replacement (prefilled; cleared fields sent as null), team/role change modals, reset password (confirm → one-time password dialog), deactivate (confirm explaining effects), reactivate (team+role)
src/features/members/TemporaryPasswordDialog.tsx   shows password once, copy button; value lives only in component state (never in query cache/storage)
nav: Organization (permission), Members (adminOnly), Administration (adminOnly)
```
Tests now 49 (+ organization 5, members 10).
**M4 verification gaps:** same as M3 (fakes only; no live backend; visuals not checked with data). Not built (documented gaps): Excel import (G5), unit rename/unarchive (G6), member directory for non-admins (G1).

## What exists (added in M5) + backend change
Backend (done by this project, tests in `backend/tests/organization/test_directory.py`): `AccountResponse.member_id` and `GET /api/v1/organization/members`. Frontend contract copy updated (81 operations).
```
src/features/auth/types.ts       Account.member_id
src/features/members/directory.ts useMemberDirectory (GET /organization/members) + useMemberNames(): nameOf(id) never fails ("Member (not visible to you)"), members[] = assignable; System Admins also get names from /admin/members
src/features/tasks/{types,api}.ts all 15 task endpoints as hooks; every key starts with ['tasks'] and every mutation invalidates it
src/features/tasks/rules.ts      Viewer {memberId, accountId, access}; canAdminister/canWork/canComment/canCreateSubtask/allowedTransitions (contract §9.1/§9.3 table), isOverdue, summarize (Home counts), changedFields (PATCH only changed), isoToLocalInput
src/features/tasks/history.ts    describeEvent: one line per event kind; never prints previous_body; content_removed marked
src/features/tasks/TasksPage.tsx /tasks: filters in URL (?status=&scope=&mine=1&q=), create modal (TaskFormModal: unit from task.create units, assignee checklist), non-Member note
src/features/tasks/TaskDetailPage.tsx (+AssigneesCard, SubtasksCard, CommentsCard, HistoryCard)  /tasks/:id: legal status buttons only (cancel/reopen confirm), edit, move (not subtasks), assignees add/remove, subtasks, comments (own edit/delete, deleted placeholder), history
src/features/tasks/HomeSummary.tsx  Home block: open / assigned-to-you / overdue + due-in-7-days, labelled "from tasks you can see"
nav: Tasks (permission task.view)
```
Tests now 63. Eligibility of assignees is NOT pre-filtered client-side (no unit parent info on the client); the server's 422 is shown inline.
Dev note: the Vite dev server on OneDrive paths sometimes serves a stale module after edits (seen with nav.ts) — restart the preview server if the UI disagrees with the source.

## What exists (added in M6)
```
src/features/tasks/seriesApi.ts     Series types, hooks for the 5 series endpoints (all invalidate ['tasks']), MAX_OCCURRENCES=104, occurrenceCount, seriesChanges (only changed fields; templates = complete list, existing keys kept, new ones keyless)
src/features/tasks/SeriesForm.tsx   create/edit modal: unit, first due/ends (create only; "N weekly occurrences" hint and 104-cap/ordering validation), assignees, subtask-template editor
src/features/tasks/SeriesPage.tsx   /task-series/:id: facts, templates, occurrences (resolved from GET /tasks — hidden ones are simply not listed), edit / move / stop (confirm explains "future unstarted only"), nothing offered once stopped
src/features/tasks/AssigneePicker.tsx  shared checklist (used by TaskForm, SeriesForm)
TasksPage: "New weekly series" button; series chip links to the series; task detail chip links too.
```
Tests now 70. Live: created a 3-occurrence series through the UI against the real backend and opened its page.

## What exists (added in M7)
```
src/features/announcements/api.ts   Announcement types + hooks (list/get/create/patch/publish/withdraw; versions & recipients are lazy — only publisher/managers may read them); announcementActions(a, viewer) = which buttons to offer
src/features/announcements/AnnouncementsPage.tsx (+ReadChip) /announcements: state filter in URL, create draft (units where announcement.publish)
src/features/announcements/AnnouncementDetailPage.tsx /announcements/:id: opening marks read for recipients (server side effect; list/notification caches are invalidated), withdrawn → "content hidden" placeholder, edit (only changed fields; published edit warns it notifies recipients), publish (recipient checklist, ≥1, fixed forever), withdraw (confirm), versions/recipients on demand
src/features/notifications/api.ts   hooks for all 8 notification endpoints; polling every 60 s (useUnreadCount for the bell); sourceLink(source_type→route): task, task_series, announcement, calendar_event→/calendar/:id
src/features/notifications/NotificationsPage.tsx /notifications (?tab=preferences): list (unread-only filter), open (marks read + navigates), redacted items show a neutral text and no link, mark read, delete, read-all, delete-all (confirm), preferences (6 categories, partial PUT)
src/features/notifications/NotificationBell.tsx in the shell header (badge + count in aria-label); Home shows the unread count card
nav: Announcements (no permission gate: recipients need it without any permission)
```
Tests now 82. Live: created a draft, published to a Member, signed in as that Member: bell showed unread, opening the notification navigated to the announcement and marked it read.
Announcement/notification summaries are shown exactly as the server returns them (English text from the backend; not translated).

## What exists (added in M8)
```
src/features/calendar/api.ts       Event/TaskDueItem/MyCalendar types, hooks for the 10 calendar endpoints (invitations/history lazy), pure helpers: monthRange (local month → ISO with offset), shiftMonth, groupByDay (clamps into range, time-sorted), eventChanges (only changed; location/online are mutually exclusive so switching sends the other as null), isHttpUrl
src/features/calendar/CalendarPage.tsx  /calendar?m=YYYY-MM month agenda: events (type chip, cancelled struck through) + the caller's OWN task due dates (labelled); prev/next/this month; "New event" for members with calendar.create
src/features/calendar/EventForm.tsx     create/edit modal (type, title, description, start/end with order validation, place: none | location | online link validated http(s), unit + invitees on create only; scope is never sent on edit)
src/features/calendar/EventDetailPage.tsx /calendar/:eventId: facts, invitees (null list ⇒ "you are invited" note), add/remove invitee (remove confirm: silent, ≥1 invitee), edit, cancel (confirm), invitation history + event history on demand, read-only once cancelled
nav: Calendar
```
Tests now 90 (test-setup raises Testing Library async timeout to 5 s; whole-suite runs were flaky at 1 s). Live: created an online event through the UI, saw it and the Member's task due dates in the agenda, opened the detail and history.

## What exists (added in M9 + M10)
```
src/features/audit/{api,AuditPage}   /admin/audit (RequireAdmin): filters in URL (from/to as datetimes with offset, action, resource type, actor, unit, resource id validated as UUID), useInfiniteQuery on the cursor ("load older"), record detail modal with before/after JSON. Read-only, no export (G8).
src/app/router.tsx                   feature pages are lazy route chunks (page() helper; guards applied around the lazy page); errorElement RouteError (recoverable screen for render errors / failed chunk load)
src/app/GapsPage.tsx                 /not-available — honest list of product-plan items the backend lacks (messaging, scheduling, reminders, Excel import, task archive, team-wide assignment, analytics, rename/unarchive, audit export, recruitment link); linked from My Account
Fixes found in the hardening pass: absolutely-positioned visually-hidden table header caused horizontal page overflow in RTL (TableWrap is now position: relative); audit filter grid uses minmax(0,1fr); Home cards spaced.
```
Tests now 96. Build: main chunk ≈255 kB (80 kB gz) + one shared chunk ≈210 kB (react-query/router/ui) + a chunk per feature page.
**M10 verification done:** all 11 main routes checked at 375 px in the browser: no horizontal overflow (after the fix); mobile "More" menu works; RTL default and LTR switch work; live smoke of every feature against the real backend (see below).
**M10 NOT done / honest limits:** no automated accessibility tooling (axe/Lighthouse) was run — keyboard/labels/focus rely on semantic markup, native <dialog>, and the Tabs arrow-key handler, but a manual screen-reader and contrast audit is still owed; English strings for server-provided text (notification summaries, business-rule error `detail`) are shown as the backend sends them; the Recruitment & Selection link is not added (no URL); Ghroob OTF licence unconfirmed; no end-to-end browser test suite (live smoke was manual).

## Live-backend recipe (for the next session)
`cd backend && docker compose up -d postgres && uv run alembic upgrade head && uv run uvicorn kora_api.main:app --port 8000`; `cd frontend && npm run dev` and open the printed `localhost` URL. The dev DB already contains: System Admin `root` (password set during testing: local-dev-pass-1), Administration "Operations", Team A, Members tl.sara (Team Leader), omar, nora (passwords set during testing: sara-dev-pass-1, omar-dev-pass-1; nora still has her temporary password). These are local dev data only.
Backend verification: `uv run pytest` (348 tests incl. the new directory tests), ruff and pyright all passed after the member_id/lookup change.

## UI redesign (2026-10-15, user request) — supersedes the earlier "utility" look
The user found the first UI repetitive and boring and said to **drop the Design Language Master's layout/pattern/gradient restrictions and design freely — keeping only the brand colours** (navy `#2D3B70`, fuchsia `#944399`, coral `#F26557`, green `#4EA649`, white, plus tints/shades derived from them). Ghroob is still the font. Semantic mapping now: navy = info/new, fuchsia = in motion, green = done, coral = needs attention/danger.
What changed: tokens in `src/app/styles/global.css` (gradients `--grad-brand/warm/cool`, soft shadows, 20–28 px radii, rise/pop animations, tinted page background); pill buttons with gradient primary; frosted header with a **Ctrl/⌘+K command palette** (`app/CommandPalette.tsx`); desktop sidebar is a **slim rail that expands on hover/keyboard focus**; mobile has a floating pill nav; Home is a gradient hero + quick-action tiles + count-up stat tiles (`shared/lib/useCountUp.ts`); sign-in has an animated brand panel; Tabs/segmented controls are pills; modals animate in with a blurred backdrop; **Tasks has a List/Board switch — the board supports drag-and-drop between status columns** (only API-legal moves, confirm for cancel/reopen, and a keyboard/touch `<select>` fallback; `tasks/TaskBoard.tsx`). Tests: 100 pass. All routes re-checked at 375 px with no horizontal overflow.

### UI round 2 (2026-10-15, user feedback)
- **Top navigation bar** replaces the side rail (`app/AppShell.tsx`): navy→fuchsia gradient bar with the white bilingual lockup, link pills where only the active (or hovered/focused) page shows its name (all labels at ≥1280 px), Ctrl/⌘+K search, bell, language, avatar. Phones keep the floating bottom pill.
- **Calendar is a month grid** (`calendar/CalendarPage.tsx`): Sunday-first 7-column squares, today ring, selected day, event/task chips in cells (dots on phones), side panel (below on phones) listing the selected day with links. Cells are buttons; links live only in the panel.
- **Richer inner lists**: `shared/ui/RowList.tsx` (`RowList`, `Row`, `Avatar`) — leading avatar/icon, title link with animated underline, meta chips, state edge colour, trailing status/actions — now used by Tasks list, Members, Announcements, Notifications (category icons), task Assignees and Subtasks. Tables remain for dense admin data (role defaults, overrides, admins, audit, effective access).
Tests: 100 pass; all main routes re-checked at 375 px, no overflow.

### UI round 3 (2026-10-15, user feedback)
- Greeting "حياك الله" (afternoon). Quick search / Ctrl+K palette **removed** (component and messages deleted).
- After signing in the app opens **Home**: signing out sets `signedOut` in the session so `RequireAuth` no longer remembers the page left (deep links and expired sessions still return to where you were).
- Tasks default view: **board** at ≥768 px (tablets/desktop), **list** on phones (`useMediaQuery`); `?view=list|board` overrides.
- **"Sign out of all devices" removed** from My Account on request (`POST /auth/sign-out-all` is therefore the one backend endpoint the UI does not call; `signOutAll` deleted from `auth/api.ts`).
- Backend coverage audit (script comparing contract §16 with `http.*` calls in `src/`): **80 of 81 endpoints used**. Newly wired: `GET /admin/audit-records/{id}` (detail refetched on open), `GET /calendar/events` (Home "Upcoming events"), `GET /health` (connection-failure screen tells whether the server is back), `GET /notifications/{id}` (re-checked before opening a notification; redacted ones stay), `GET /organization/units/{id}` (unit "Details" dialog).

## Verification evidence (M2)
`npm run check` green (lint, tsc, 25 tests, build). Browser: sign-in page checked at 1280 px (art panel + form) and phone width, no horizontal overflow. **Not verified:** any call against the real backend (Docker/Postgres were not running). First thing to do when the backend is up: bootstrap an admin (`uv run python -m kora_api.access.bootstrap <username>` in `backend/`), run the real flow sign-in → forced password change → shell → sign-out-all, confirm cookie/CSRF behaviour through the Vite proxy, and record results here.

## Verification evidence (M1)
`npm run check` green (lint, tsc, 12 tests, production build: JS 355 kB / 112 kB gz). Browser check on dev server: Ghroob weights load, `dir="rtl"` default, sidebar on the right; at 375 px the mobile header + bottom nav render with no horizontal overflow; language switch flips to `ltr`/`en`. **Not yet verified:** any call to the real backend (nothing calls the API yet).

## Decisions made (M1)
- Arabic default, English secondary, tiny in-house `t()` (no i18n library). CSS logical properties everywhere.
- Mobile "More" menu appears only when there are >4 nav items.
- Unused mesh image and `old` logos intentionally not copied. `pattern-9.svg` / `pattern-8.svg` copied/available for empty states & sign-in later (pattern-8 not copied yet — copy from the identity folder if needed).
- Preview/launch config is at the **repo root** `.claude/launch.json` (tool requirement), not in `frontend/`.
- The old empty file `frotend_PROJECT_STATE.md` was renamed to `frontend_PROJECT_STATE.md`.

## Open items / blockers
- **G1 (needs user/backend decision, affects M5+):** non-admin accounts cannot learn their own `member_id` and there is no member lookup outside `/admin/members` → non-admins can't create tasks, pick assignees/recipients/invitees, or see names. See roadmap §4. M2–M4 are unaffected.
- Live local backend: `docker compose up -d postgres` (backend/), `uv run alembic upgrade head`, bootstrap admin `root` created in the dev DB (password changed during testing), seeded Operations/Team A and members tl.sara, omar, nora. Cookies/CSRF through the Vite proxy verified live.
- G9: Recruitment & Selection URL not supplied. G11: Ghroob web-serving licence unconfirmed.
- Nothing is committed to git yet (the user has not asked for a commit).

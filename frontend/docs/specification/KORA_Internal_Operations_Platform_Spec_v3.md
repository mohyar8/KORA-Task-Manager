# KORA Internal Operations Platform — Consolidated Product Specification v3

> **Status:** Consolidated product vision plus implementation-alignment notes, reviewed against the backend API contract dated 2026-10-12 (Milestone 8B). The original five detailed sections are retained as desired product requirements; the alignment appendix distinguishes implemented, partial, absent, and decision-pending capabilities. Do not treat desired behavior as an existing API.

## Implementation contract rule — API_CONTRACT.md

When `API_CONTRACT.md` is available, it is the authoritative source for frontend/backend integration details: data shapes, field names, endpoints, request/response behavior, pagination, errors, authentication/authorization integration, and any other agreed interface behavior.

- Read and follow `API_CONTRACT.md` before implementing integration or assuming returned data.
- Do not invent or predict API endpoints, payloads, schemas, identifiers, field names, statuses, or response behavior.
- If the contract is absent, incomplete, or conflicts with a product rule here, preserve the product rule, isolate temporary mock data behind a replaceable boundary, and record or raise the missing contract decision.
- Product requirements in this document define desired behavior; `API_CONTRACT.md` defines the approved technical interface used to realize it.
- **Precedence:** explicit user decisions and product rules define intended product behavior; the dated API contract defines only what the backend currently supports. A discrepancy is a gap, not permission to fabricate an endpoint or silently change the product.
- The uploaded contract is named `API_CONTRACT(2).md`. In the frontend repository, verify the authoritative contract filename/path and version before integration; do not assume the file is present under the shorter name.
- The addendum at the end of this document is the current implementation-readiness reference. Where older sections describe a capability differently, use the addendum to distinguish desired future behavior from implemented backend behavior.

---

KORA INTERNAL OPERATIONS PLATFORM — MASTER CONTEXT
We are building a new internal operations platform for KORA.
The goal is to create one central platform for managing KORA's organization, members, day-to-day work, tasks, performance, communication, permissions, and administrative operations.
This is not a recruitment platform. KORA already has a separate working Recruitment & Selection system, which should remain separate and be accessible from the new platform rather than rebuilt.
The new platform revolves around five major domains:
1. Core Platform, Accounts & Access
Authentication, user accounts, organizational roles, System Admin, permissions, access scopes, user-specific permission overrides, navigation, and shared platform behavior.
2. Organization & Members
KORA's organizational structure, Event/Project leadership, Project Management Office, administrations, teams, members, member directory, member profiles, member administration, and member import.
3. Tasks, Workspaces & Analytics
The complete task lifecycle, assignment to one or multiple members or entire teams, self-created tasks, team visibility, PMO-originated work, Home, My Tasks, team and administration workspaces, and operational analytics.
4. Communication, Notifications & Reminders
Internal messaging, Inbox, broadcasts, scheduled communication, notifications, task-related alerts, one-time reminders, and recurring reminders.
5. Governance, Audit & Selection Platform Integration
System-wide auditability, administrative safety, historical integrity, sensitive-action traceability, and the connection to KORA's existing Recruitment & Selection platform.
GENERAL PRODUCT MODEL
KORA's organizational structure conceptually includes:
- Event/Project Leader
- Event/Project Deputy Leader
- Project Management Office
  - PMO Leader
  - PMO Members
- Administrations
  - Administration Managers
  - Teams
    - Team Leaders
    - Members
System Admin is separate from this organizational hierarchy.
The platform must not assume that organizational seniority automatically determines system access.
Access is flexible and conceptually based on:
Organizational Role
+
Organizational Scope
+
Permissions
+
User-Specific Overrides
System Admin is the only authority that manages permissions and may grant or deny access at the individual-user level, including expanding a normal Member's access or restricting capabilities from senior organizational leaders.
System Admin is also the only authority responsible for administratively adding, editing, moving, deactivating/removing, importing, and managing KORA members.
Every KORA member is expected to have a platform account, while Member and User Account remain conceptually distinct.
PRODUCT PRINCIPLES
The platform should be:
- organization-aware,
- permission-aware,
- responsive,
- Arabic/RTL-first,
- accessible,
- consistent,
- operationally clear,
- and suitable for real day-to-day KORA work.
Permissions must represent real access control, not merely hidden interface elements.
Historical information should remain meaningful when members, roles, teams, permissions, or organizational structures change.
Important actions should be traceable and high-impact actions should include appropriate safeguards.
Do not introduce destructive deletion where deactivation or archiving better preserves organizational history.
RECRUITMENT BOUNDARY
KORA already has an existing Recruitment & Selection platform.
Do not rebuild its applicant management, decisions, requests, objections, accepted-applicant flows, imports, or other recruitment-specific functionality inside the new platform.
The new platform should provide an authorized entry point to the existing recruitment system.
A future integration may support:
Accepted Applicant → KORA Member
but its technical contract has not yet been defined and must not be invented.
WORKING RULE
The detailed specifications for the five domains will be provided separately after this master context.
Treat those detailed section specifications as authoritative for their respective domains.
Do not invent missing business rules.
If a required behavior is not defined, identify the ambiguity rather than silently making a product decision.
Do not assume a frontend architecture, backend architecture, API design, database schema, framework, library, or infrastructure unless explicitly requested later.
The goal is to preserve KORA's actual operational rules while creating one coherent internal platform rather than forcing the product into a generic project-management, HR, or SaaS template.
# SECTION 1 — CORE PLATFORM, ACCOUNTS & ACCESS
You are defining the first functional domain of the new KORA internal operations platform.
This specification is product- and behavior-focused only. Do not assume or prescribe frontend architecture, backend architecture, APIs, database schemas, frameworks, libraries, infrastructure, or implementation technologies.
The goal of this section is to define the common platform experience, user accounts, authentication, organizational roles, system administration, permissions, access scopes, and user-specific permission overrides that all later sections of the platform will rely on.
Preserve every business rule below. Do not simplify role, permission, or scope behavior into a conventional fixed role-based system.
## 1. PLATFORM PURPOSE
KORA is building a new internal platform for managing its organization and day-to-day operations.
The platform will eventually include:
- organizational structure,
- members,
- tasks,
- team and administration workspaces,
- analytics,
- internal communication,
- notifications,
- reminders,
- administrative tools,
- and access to the existing recruitment/selection platform.
This section does NOT define those later business domains in detail.
It defines the common platform foundation required for users to enter the platform, navigate it, manage their own accounts, and access only the capabilities and information they are currently authorized to use.
## 2. CORE ACCESS PRINCIPLE
Access must never be determined only by a user's organizational title.
The platform must distinguish between:
1. Organizational Role
   Who the person is organizationally inside KORA.
2. Organizational Scope
   The organizational area naturally associated with that person.
3. Permissions
   The capabilities and information the person is allowed to access.
4. User-Specific Overrides
   Explicit permission or scope changes applied to a particular user by a System Admin.
A user's organizational position provides sensible defaults, but it must not permanently determine what that user can or cannot access.
The platform must support exceptions in both directions:
- expanding a user's access beyond the normal scope of their role,
- and restricting access that their role would normally provide.
## 3. ORGANIZATIONAL ROLES
The platform recognizes the following organizational roles:
- Event/Project Leader
- Event/Project Deputy Leader
- Project Management Office Leader
- Project Management Office Member
- Administration Manager
- Team Leader
- Member
The Event/Project Leader and Event/Project Deputy Leader are organization-wide leadership positions.
The Project Management Office is an organizational unit within KORA.
Administrations contain teams.
Teams contain members.
Do not introduce a separate "Deputy Team Leader" role.
If KORA has a deputy leader for a team, that person is treated as a Team Leader for role purposes rather than receiving a separate platform role.
The final list of administrations and teams has not yet been provided. Do not invent it.
## 4. SYSTEM ADMIN
System Admin is separate from the organizational hierarchy.
Being a System Admin is not the same thing as being:
- Event/Project Leader,
- Event/Project Deputy Leader,
- PMO Leader,
- Administration Manager,
- Team Leader,
- or any other organizational position.
System Admin represents administrative authority over the platform itself.
The organizational chart should not imply that the System Admin is organizationally "above" the Event/Project Leader merely because the System Admin has powerful system permissions.
A person may have an organizational identity and administrative system authority, but those concepts must remain distinguishable.
## 5. SYSTEM ADMIN AUTHORITY
Only System Admins may manage platform permissions.
Event/Project Leaders, Deputy Leaders, PMO leadership, Administration Managers, and Team Leaders must NOT automatically receive permission-management authority because of their organizational position.
System Admins must be able to control access with high flexibility.
A System Admin must be able to:
- manage user accounts,
- manage role permission defaults,
- inspect a user's effective access,
- grant additional permissions to a specific user,
- revoke or deny permissions for a specific user,
- expand a user's normal access scope,
- restrict a user's normal access scope,
- and manage sensitive system-level access settings.
This authority applies regardless of organizational seniority.
For example:
- a normal Member may be explicitly granted access to information outside his normal team scope;
- an Administration Manager may be given additional organization-wide capabilities;
- an Event/Project Leader may explicitly lose a capability that would normally be available to that role.
Therefore, never assume:
"high organizational position = unrestricted system access."
## 6. DEFAULT PERMISSIONS AND USER OVERRIDES
Every organizational role should have a sensible default permission set.
These defaults exist so that normal users do not require individual configuration.
However, defaults are not absolute.
The effective access model must conceptually support:
Role Defaults
+
Organizational Scope
+
User-Specific Overrides
User-specific overrides have the ability to alter what would normally result from the role and scope.
An override may:
- grant something additional,
- deny something normally granted,
- broaden scope,
- or narrow scope.
Example:
A Member normally belongs to Team A and receives the normal Member permissions for Team A.
A System Admin may explicitly allow that Member to view a resource outside Team A.
Another example:
An Event/Project Leader normally receives broad platform access.
A System Admin may explicitly deny that leader access to a particular capability.
The user's effective access must respect that explicit override.
Do not design the platform around hardcoded assumptions such as:
"Event Leader can always do X"
or
"Member can never see Y."
Roles define defaults; permissions and overrides determine actual access.
## 7. SCOPE
Permissions and scope are different concepts.
A permission answers:
"What type of action or information may this user access?"
Scope answers:
"Within what organizational boundary may the user exercise that permission?"
Typical natural scopes include:
- self,
- team,
- administration,
- Project Management Office,
- organization-wide.
These are conceptual examples, not a requirement to expose these exact labels to users.
A user's natural scope generally follows his organizational position.
Examples:
- a Member is naturally associated with his team;
- a Team Leader is naturally associated with his team;
- an Administration Manager is naturally associated with his administration and its teams;
- organization-wide leadership naturally has broader scope.
However, System Admin overrides may expand or restrict these defaults.
Scope must therefore not be permanently hardcoded to role.
## 8. PERMISSION ENFORCEMENT
Permissions are not merely a presentation rule.
If a user does not have access to something, the platform must actually prevent that user from accessing or modifying it.
Simply hiding a button, menu item, page link, or action is not sufficient.
This principle applies to:
- direct navigation,
- copied links,
- refreshed pages,
- searches,
- filtered views,
- actions,
- data access,
- and any other route through which restricted information or functionality could otherwise be reached.
A user must not gain access merely by knowing or guessing the location of a restricted resource.
## 9. PERMISSION-AWARE NAVIGATION
Navigation must reflect the user's current effective permissions.
Users should see only platform areas that are relevant and accessible to them.
If the user has no accessible items inside an entire navigation group, that empty group should not be displayed.
Navigation must respond to effective permissions, including user-specific overrides, rather than relying only on organizational role.
If an Admin changes a user's effective access, the platform navigation and accessible areas must reflect the resulting permission state.
## 10. MAIN PLATFORM NAVIGATION
The overall platform is organized into logical areas.
The complete platform will eventually contain areas such as:
- Home,
- Dashboard/Analytics,
- Work,
- Members,
- Communication,
- Recruitment & Selection access,
- and System Administration.
Not every user sees every area.
The visible navigation is determined by effective access.
The platform should provide a persistent primary navigation structure on larger screens.
The navigation contains:
- KORA identity/branding,
- available platform areas,
- relevant counters/badges where applicable,
- and the signed-in user's account area.
Relevant items may later show counters such as:
- pending personal work,
- unread communication,
- pending actions.
The exact counters are defined by their corresponding later sections.
## 11. MOBILE NAVIGATION
The platform must be genuinely usable on mobile devices rather than merely shrinking the desktop layout.
On smaller screens:
- the large primary navigation should collapse into an appropriate mobile navigation pattern,
- high-frequency destinations should remain quickly accessible,
- secondary destinations should remain available through a compact navigation mechanism,
- content must not require desktop-width layouts,
- and desktop tables or dense layouts in later sections must have appropriate mobile representations.
The original product concept proposes quick mobile access to areas such as:
- Home,
- My Tasks,
- Inbox,
- Members,
- More.
The exact visibility of these destinations still follows permissions.
## 12. PAGE-LEVEL PLATFORM STRUCTURE
Pages should share a consistent platform structure.
A typical page may include:
- its current section/context,
- a clear page title,
- a short description when useful,
- page-specific primary actions,
- notifications access,
- communication access where relevant.
The exact actions depend on the page and the user's effective permissions.
Do not show actions that the user cannot perform.
## 13. DEEP LINKS AND PERSISTENT PAGE STATE
Pages must be directly addressable.
A user should be able to:
- refresh a valid page without being incorrectly sent to a generic error,
- copy a link to an accessible page,
- open an accessible direct link,
- and return to meaningful filtered states where applicable.
Filters and meaningful page state should be representable in a way that supports direct navigation when appropriate.
Access checks still apply to direct links.
A valid URL does not grant permission.
If a user opens a valid resource without sufficient access, show an appropriate access-denied state rather than exposing the content.
## 14. SHARED PAGE STATES
Reusable content areas and lists must account for at least:
Loading
- Clearly communicate that content is being loaded.
Empty
- Explain that no relevant content exists.
- When appropriate, provide the next meaningful action.
- Example concept: "Add the first item" when the user has permission to do so.
Error
- Explain the problem in understandable language.
- Provide retry or recovery actions where appropriate.
The platform should not leave users with blank screens when a known state can be communicated.
## 15. IMPORTANT ACTION CONFIRMATION
Important or potentially disruptive actions must require clear confirmation where appropriate.
Examples include:
- disabling something,
- archiving important records,
- changing sensitive account/access settings,
- performing broad-impact actions.
The confirmation should explain the effect of the action rather than simply asking "Are you sure?"
Later sections may define additional domain-specific confirmation requirements.
## 16. CONCURRENT CHANGES
The platform must account for situations where multiple authorized users interact with the same data.
If a user attempts to act on information that has changed since it was loaded, the platform should not silently overwrite a newer change.
The user should receive a clear message that the item was changed by someone else and should be given an appropriate way to refresh/reload the current information.
The exact conflict behavior may depend on the affected domain.
## 17. AUTHENTICATION
Users access the platform through their own accounts.
The sign-in experience includes:
- username,
- password,
- sign-in action.
After successful authentication, the user enters the platform and is taken to the appropriate starting experience.
Authentication failure must not reveal unnecessary account information.
For invalid credentials, use a generic message equivalent to:
"The username or password is incorrect."
Do not reveal whether:
- the username exists,
- or only the password was incorrect.
## 18. FAILED LOGIN PROTECTION
Repeated incorrect login attempts must trigger temporary protection against continued rapid attempts.
After several failed attempts, sign-in attempts should be temporarily limited for a period of time.
The user must receive a clear message explaining that another attempt can be made later.
Do not expose sensitive internal authentication details.
## 19. TEMPORARY PASSWORD AND FIRST LOGIN
Accounts may be created or reset using a temporary password.
When a user signs in using a temporary password for the first time, the platform must require the user to replace it before continuing normal platform usage.
The user should not continue operating indefinitely with the temporary password.
## 20. FORGOTTEN PASSWORD
The platform must provide a "Forgot password?" path.
The currently agreed product behavior is that the user is informed to contact the appropriate platform administration/System Admin for account recovery or password reset.
Do not assume a self-service email/SMS password recovery flow unless it is explicitly approved later.
## 21. ACCOUNT MANAGEMENT
Every signed-in user has a "My Account" area.
At minimum, it should communicate:
- the user's identity,
- organizational role,
- relevant organizational affiliation/scope,
- and account-related actions available to that user.
The user can change his password.
The user can sign out.
The user must also have the ability to sign out of all active devices/sessions.
Notification preferences are not currently a required part of this section and may be added later.
## 22. MEMBERS AND USER ACCOUNTS
A Member and a User Account are conceptually different records.
Member:
Represents the person as a KORA member and contains organizational/member information.
User Account:
Represents that person's ability to authenticate and use the platform.
However, the current KORA business decision is:
Every KORA member should have a platform account.
Therefore, the platform must support a clear relationship between the member identity and the corresponding account without treating the two concepts as identical.
Detailed member management belongs to Section 2, not this section.
## 23. USER ACCOUNT ADMINISTRATION
System Admins manage user accounts.
Administrative account capabilities include the ability to:
- create/manage platform accounts as required,
- inspect account status,
- manage account access,
- disable access,
- reset a user's password using the approved temporary-password process,
- manage the user's effective permissions,
- manage permission overrides,
- and manage relevant access scope.
Detailed member data such as organizational member records belongs to Section 2.
Do not merge general account administration with member-profile editing simply because every member has an account.
## 24. SYSTEM ADMINISTRATION AREA
The platform must have an administrative area accessible according to System Admin permissions.
This area serves as the control point for sensitive platform administration.
It should provide access to appropriate administrative capabilities such as:
- user account administration,
- permissions,
- role defaults,
- user-specific permission overrides,
- access scope management,
- and approved system-level settings.
Additional administrative functions from later sections may appear in this area when those sections are defined.
Do not assume that all operational leadership users can access System Administration.
## 25. SYSTEM SETTINGS
The platform should support centrally managed settings where a business rule needs to be configurable instead of permanently hardcoded.
One already agreed future-facing example concerns recruitment:
The platform must be able to support a setting controlling whether applicants in a recruitment cycle select:
- an Administration,
or
- a Team.
This setting is administratively controlled rather than permanently fixed in code/product behavior.
The actual recruitment system remains separate and is covered in Section 5, so do not build recruitment functionality as part of this section.
This requirement only establishes that appropriate configurable platform settings may exist and are managed through authorized administration.
## 26. SYSTEM STATES AND ERROR PAGES
The platform must provide understandable system-level states rather than technical or blank error screens.
At minimum, account for:
Page Not Found
- Explain that the requested page does not exist.
- Provide a way back to a safe destination such as Home.
Access Denied
- Explain that the signed-in user does not have permission to access the requested area.
Session Expired
- Explain that the session has ended and that the user needs to sign in again.
Connection Failure
- Explain that the platform could not connect or load the required information.
- Provide retry/recovery where appropriate.
These states must also work when users:
- refresh,
- use bookmarks,
- open direct links,
- or follow links sent by another user.
## 27. PLATFORM RESPONSIVENESS
The platform must support desktop and mobile usage as first-class experiences.
Requirements include:
- no unintended horizontal overflow,
- usable navigation at different viewport sizes,
- readable content,
- appropriately adapted dense content,
- usable forms and actions,
- and touch-friendly interaction where relevant.
A desktop-only feature may be explicitly identified later if a particular administrative workflow genuinely requires it, but this should not be assumed globally.
## 28. RTL AND ARABIC
The platform is intended to support Arabic as a first-class experience.
RTL behavior must be native and consistent rather than visually patched after the fact.
Navigation, content flow, controls, forms, tables, directional elements, and responsive behavior must account for RTL usage.
Do not assume that an interface designed only for LTR can simply be mirrored without checking interaction meaning.
## 29. ACCESSIBILITY
Platform-wide interaction must account for accessibility.
At minimum:
- keyboard access must be supported where applicable,
- focus states must be visible,
- controls must have understandable labels,
- status must not depend only on color,
- disabled states must be distinguishable,
- loading states must be communicated,
- interactive elements must have clear states,
- and contrast must remain usable.
These rules apply to all later platform sections as well.
## 30. VISUAL AND INTERACTION CONSISTENCY
The platform should behave as one coherent product.
Shared concepts should use consistent patterns across sections, including:
- buttons,
- inputs,
- navigation,
- page headings,
- dialogs,
- status indicators,
- loading states,
- empty states,
- errors,
- confirmations,
- permissions behavior,
- and responsive behavior.
Do not create different interaction rules for equivalent actions in different sections without a product reason.
KORA branding should be present, but operational clarity takes priority over unnecessary decoration.
## 31. SECURITY AND PRIVACY PRINCIPLE
Never expose information simply because the interface has a route or component capable of displaying it.
Every sensitive operation or resource must respect the user's current effective access.
This applies especially to future sections involving:
- member personal information,
- organization-wide data,
- tasks outside a user's normal scope,
- administrative settings,
- messages,
- analytics,
- and audit information.
Permission changes must affect actual access, not only visual presentation.
## 32. IMPORTANT DISTINCTIONS TO PRESERVE
Do not collapse these concepts:
Organizational Role ≠ Permission
Organizational Role ≠ System Admin
Permission ≠ Scope
Member ≠ User Account
Visible Navigation ≠ Authorization
Organizational Seniority ≠ Guaranteed System Access
Default Role Access ≠ Final Effective Access
These distinctions are foundational to the entire KORA platform.
## 33. OUT OF SCOPE FOR THIS SECTION
Do not fully define or build the business behavior of:
- organizational structure management,
- member directory and member profiles,
- member import,
- tasks,
- task lifecycle,
- personal task workspace,
- team/administration workspaces,
- analytics,
- messaging,
- broadcasts,
- notifications,
- reminders,
- audit log,
- or recruitment/selection.
Those belong to later sections.
Only establish the common platform/account/access behavior required for them.
## 34. UNRESOLVED INFORMATION
Do not invent answers for information that has not yet been provided.
In particular:
- the final list of KORA administrations and teams will be supplied later;
- detailed permission names and the complete permission matrix may need to be finalized as later domains are defined;
- do not invent recruitment APIs or integration behavior;
- do not invent additional organizational roles;
- do not invent authentication methods beyond the username/password and temporary-password behavior currently agreed;
- do not assume external identity providers, email recovery, SMS recovery, SSO, MFA, or social login unless explicitly approved later.
Where a later section introduces a new capability, its permission should integrate with the permission model defined here rather than bypassing it.
## 35. EXPECTED PRODUCT RESULT
When this section is fully represented in the product, KORA should have a coherent platform foundation where:
- users can securely sign in and manage basic account actions;
- temporary-password and first-login behavior is handled;
- sessions and common authentication states are clear;
- every member can have a corresponding platform account;
- organizational roles provide useful default access;
- actual access is not permanently locked to organizational titles;
- permissions and organizational scope remain separate concepts;
- System Admins alone control permission management;
- System Admins can grant or deny access at the individual-user level;
- even organization-wide leaders can be restricted by explicit Admin configuration;
- ordinary users can receive exceptional access when explicitly granted;
- navigation reflects actual effective permissions;
- direct links cannot bypass access rules;
- system/error states are understandable;
- the product works coherently across desktop and mobile;
- Arabic RTL and accessibility are first-class requirements;
- and all later KORA domains can build on the same account and access-control foundation.
Do not weaken, simplify, or reinterpret these rules merely to fit a conventional fixed RBAC model.
# SECTION 2 — ORGANIZATION & MEMBERS
You are defining the second functional domain of the new KORA internal operations platform.
This specification is product- and behavior-focused only.
Do not assume or prescribe:
- frontend architecture,
- backend architecture,
- APIs,
- database schemas,
- frameworks,
- libraries,
- infrastructure,
- or implementation technologies.
Section 1 already establishes the platform-wide foundation for:
- authentication,
- user accounts,
- organizational roles,
- System Admin,
- permissions,
- organizational scope,
- user-specific permission overrides,
- permission-aware navigation,
- shared platform states,
- responsive behavior,
- RTL,
- accessibility,
- and common system behavior.
Do not redefine or weaken those rules here.
This section defines:
- KORA's organizational structure,
- administrations and teams,
- organizational leadership relationships,
- members,
- member directory,
- member profiles,
- member privacy,
- member administration,
- member movement between organizational units,
- member lifecycle,
- and bulk member import.
Preserve every business rule below.
## 1. CORE DOMAIN PURPOSE
The purpose of this section is to make the KORA organizational structure and its members first-class entities inside the platform.
The platform must replace the need to depend on spreadsheets for day-to-day member lookup and organizational membership management.
The organization structure should answer questions such as:
- What are KORA's administrations?
- What teams belong to each administration?
- Who leads the event/project?
- Who is the deputy event/project leader?
- Who leads the Project Management Office?
- Who manages each administration?
- Who leads each team?
- Who belongs to each team?
- Where does a specific member belong?
- What is a member's organizational role?
- Is an organizational unit currently active?
- Is a member currently active?
- What historical organizational information should remain preserved?
The member system should answer questions such as:
- Who are KORA's current members?
- What administration and team does each member belong to?
- What is each member's organizational role?
- What member information may the current user see?
- Who is allowed to create, edit, move, deactivate, or otherwise manage members?
- How can the current spreadsheet-based member data be imported into the platform safely?
## 2. ORGANIZATIONAL MODEL
The platform must represent KORA's organizational structure.
The currently agreed conceptual hierarchy is:
KORA Event / Project
│
├── Event/Project Leader
├── Event/Project Deputy Leader
│
├── Project Management Office
│   ├── Project Management Office Leader
│   └── Project Management Office Members
│
└── Administrations
    │
    ├── Administration Manager
    │
    └── Teams
        │
        ├── Team Leader
        └── Members
This is the organizational structure, not the permission model.
Do not infer system access solely from a person's position in this hierarchy.
Section 1's permission rules remain authoritative.
## 3. EVENT/PROJECT LEADERSHIP
KORA has organization-wide event/project leadership.
The platform must recognize:
- Event/Project Leader
- Event/Project Deputy Leader
These are distinct organizational positions.
They are not the same as:
- System Admin,
- Project Management Office Leader,
- Administration Manager,
- or Team Leader.
Their organizational position may naturally provide broad default scope or permissions, but Section 1 still applies:
Organizational seniority does not guarantee unrestricted system access.
A System Admin may grant or deny specific capabilities even for the Event/Project Leader or Deputy Leader.
## 4. PROJECT MANAGEMENT OFFICE
The Project Management Office is a distinct organizational unit.
It includes:
- a Project Management Office Leader,
- and Project Management Office Members.
Use the term "Project Management Office" rather than the older concept of "Project Management Team" where the new organizational terminology applies.
The Project Management Office may operate across KORA and may later create work for other teams.
Task-specific behavior involving PMO-created tasks is defined in Section 3.
Do not define that task behavior here.
## 5. ADMINISTRATIONS
KORA contains multiple administrations.
Each administration should conceptually have information such as:
- name,
- current status,
- Administration Manager,
- teams belonging to it,
- member counts,
- and other relevant organizational information.
The final list of administrations has NOT yet been provided.
Do not invent administration names.
The platform must be capable of supporting the final administration list once it is supplied.
## 6. TEAMS
Teams exist under administrations.
A team should conceptually have information such as:
- name,
- parent administration,
- current status,
- Team Leader,
- members,
- and relevant organizational counts.
The final list of teams and their administration relationships has NOT yet been provided.
Do not invent them.
## 7. TEAM LEADERSHIP
Do not introduce a separate platform role called "Deputy Team Leader."
The agreed rule is:
A deputy team leader, where one exists organizationally, is treated as a Team Leader for platform role purposes.
Do not recreate the old recruitment-specific deputy-leader behavior inside this new organizational model.
If more than one person must operationally function with Team Leader-level authority for a team, the product should support the agreed role behavior without inventing a new Deputy Team Leader permission model.
## 8. ORGANIZATION STRUCTURE VIEW
Authorized users should be able to understand KORA's organizational structure from the platform.
The structure should clearly communicate:
- Event/Project leadership,
- Project Management Office,
- administrations,
- teams under each administration,
- administration leadership,
- team leadership,
- organizational status,
- and relevant member/team counts.
The representation may be hierarchical or otherwise structured clearly.
Do not treat the organization as a flat list of unrelated teams.
## 9. ORGANIZATION MANAGEMENT
The platform must support authorized management of the organizational structure.
Relevant organizational actions include:
- creating an administration,
- creating a team under an administration,
- renaming an administration,
- renaming a team,
- moving a team from one administration to another,
- assigning/changing an Administration Manager,
- assigning/changing Team Leader responsibility,
- activating an organizational unit,
- deactivating an organizational unit.
The ability to perform these actions is governed by the permission system from Section 1.
Do not assume that organizational leadership automatically has permission to perform every structural administration action.
## 10. ORGANIZATIONAL DEACTIVATION AND HISTORY
Organizational units should not be permanently destroyed merely because they are no longer active.
The original product requirement establishes the principle that administrations and teams with historical platform data should remain preserved.
Therefore:
- prefer deactivation over destructive removal,
- historical references must remain understandable,
- old tasks or historical records must not become meaningless because an organizational unit was removed,
- and previously existing organizational relationships should remain interpretable where required.
An administration should not simply be deactivated while it still contains active members without resolving those memberships appropriately.
Do not silently orphan active members.
## 11. MEMBER CONCEPT
A Member represents a person as a member of KORA.
Member information is organizational/member information.
It is conceptually different from a User Account.
Section 1 establishes:
Member ≠ User Account
However, the current business decision is:
Every KORA member should have a platform account.
Therefore, each member should be clearly associated with the corresponding platform account while preserving the conceptual distinction between:
- membership information,
- and authentication/access information.
Account authentication and permission administration remain governed by Section 1.
## 12. MEMBER INFORMATION
The member domain must support the currently identified information needed for KORA operations.
Member information includes, where available:
- full name,
- university/student ID,
- phone number,
- email,
- major/specialization,
- academic year,
- administration,
- team,
- organizational role,
- membership/account status,
- and other member information explicitly approved later.
Do not invent additional personal data requirements.
The actual existing member spreadsheet may contain additional fields.
Those fields have not yet been fully confirmed.
Do not invent the spreadsheet's exact columns before the real file is provided and reviewed.
## 13. MEMBER DIRECTORY
The platform must provide a searchable Member Directory.
The purpose is to replace the need to search spreadsheets manually for members.
The directory should allow authorized users to locate members using relevant information.
The currently agreed search/filter capabilities include:
- member name,
- university/student ID,
- phone number where the current user is permitted to access it,
- administration,
- team,
- organizational role.
The directory should make the member's organizational context immediately understandable.
Useful directory information includes:
- member identity,
- administration,
- team,
- organizational role,
- and access to the member's profile.
Task/performance information associated with members is defined in Section 3 and may later appear in the directory once that section exists.
## 14. MEMBER CONTACT INFORMATION
Contact information includes sensitive member information such as:
- phone number,
- email,
- and potentially direct communication actions.
Contact information must not automatically be visible to every member.
The agreed organizational default is:
A person's sensitive contact information may be visible to users who are organizationally above that person where appropriate.
Peer-level members should not automatically receive unrestricted access to each other's sensitive contact information.
However, this is a default access rule, not an immutable rule.
Section 1's permission system remains authoritative.
A System Admin may:
- grant access beyond the normal organizational default,
- or restrict access that would otherwise normally exist.
Therefore, contact visibility must respect effective permissions and scope.
Do not hardcode contact visibility solely from role names.
## 15. PHONE AND WHATSAPP ACTIONS
Where a user is permitted to see a member's phone number, the platform may provide convenient actions such as:
- copying the phone number,
- opening a direct WhatsApp conversation,
- or initiating another approved contact action.
These conveniences must not bypass privacy rules.
If the user does not have permission to access the phone number, a WhatsApp action must not indirectly expose or reveal it.
This is separate from automated WhatsApp messaging or notification integration.
Automated external communication is addressed separately in Section 4.
## 16. MEMBER PROFILE
Each member should have a member profile.
The profile serves as a concise internal view of that member.
It should include available and authorized information such as:
- name,
- administration,
- team,
- organizational role,
- phone number where permitted,
- email where permitted,
- university/student ID,
- major/specialization,
- academic year.
The member profile may later include operational information from Section 3 such as:
- current tasks,
- completed tasks,
- completion/performance information.
Do not invent task behavior in this section.
The profile should also support relevant actions only when the current user's effective permissions allow them.
## 17. MEMBER MANAGEMENT AUTHORITY
A major business rule overrides the original document's broader PMO member-management authority:
System Admin is the only authority responsible for member administration.
Only System Admin may perform member-management operations such as:
- manually adding a member,
- editing member information,
- changing member organizational information,
- moving a member between teams,
- moving a member between administrations where appropriate,
- changing relevant member status,
- deactivating a member,
- deleting/removing a member where the final approved lifecycle policy allows it,
- importing members,
- and managing the relationship between membership and the member's platform account.
Do NOT automatically give these member-management capabilities to:
- Event/Project Leader,
- Event/Project Deputy Leader,
- Project Management Office Leader,
- Project Management Office Members,
- Administration Managers,
- Team Leaders,
- or ordinary Members.
Those users may have visibility or operational access according to their permissions, but member record administration belongs to System Admin.
## 18. SYSTEM ADMIN AND MEMBER MANAGEMENT
System Admin is responsible for the administrative lifecycle of members.
This includes the process of bringing an accepted or otherwise approved person into the main KORA member platform.
Recruitment decisions themselves remain in the separate existing recruitment/selection platform and are covered in Section 5.
The distinction is:
Recruitment/Selection Platform:
Determines recruitment/selection outcomes.
Main KORA Platform:
Contains official KORA members.
System Admin:
Controls the administrative creation/onboarding of members into the main platform.
Do not assume that accepting an applicant automatically gives non-admin users authority to create or modify the resulting member record.
## 19. MEMBER CREATION
System Admin must be able to create a member manually when appropriate.
Member creation must capture the required member information and valid organizational placement.
A member should not be assigned to an administration or team that does not exist in the current organizational structure.
The process should clearly communicate missing or invalid organizational information.
Because every member is expected to have a platform account, the relationship between the new member and account setup must be handled coherently.
Do not collapse member creation and authentication account concepts into a single indistinguishable record.
## 20. MEMBER EDITING
System Admin must be able to update member information.
Changes may include, where appropriate:
- correcting personal/member information,
- changing contact information,
- changing academic information,
- changing organizational assignment,
- changing organizational role,
- changing member status.
Sensitive changes should preserve appropriate history/auditability as defined by Section 5.
Do not silently rewrite historical organizational meaning where historical records need to remain understandable.
## 21. MOVING MEMBERS
System Admin may move a member between teams or administrations.
A move should result in a clear current organizational assignment.
The platform must account for the fact that the member may already have historical activity associated with the previous team or administration.
Do not treat moving a member as if the member had always belonged to the new unit.
Historical activity should remain attributable to its appropriate historical context where required.
Task-specific behavior after a member moves is defined in Section 3 and must not be invented here.
## 22. MEMBER DEACTIVATION / REMOVAL
The product must support removing a person from active KORA membership when required.
The exact permanent-deletion policy has not yet been finalized.
Therefore:
- do not assume hard deletion,
- preserve historical integrity,
- prefer a reversible/non-destructive lifecycle where historical records exist,
- distinguish inactive/deactivated membership from active membership,
- and do not erase historical references simply to remove someone from current active lists.
If a future requirement explicitly permits permanent deletion in a specific situation, that policy can be added later.
Until then, do not invent destructive deletion behavior.
## 23. MEMBER VISIBILITY
Users may see members according to their effective permissions and scope.
Natural organizational visibility may include:
- a Member seeing relevant members of his team,
- a Team Leader seeing his team,
- an Administration Manager seeing his administration and its teams,
- broader leadership seeing broader organizational areas.
However, these are defaults, not absolute authorization rules.
Section 1 applies:
Role Defaults
+
Organizational Scope
+
User-Specific Overrides
A System Admin may expand or restrict a user's member visibility.
Do not assume that being able to see a member means being able to:
- edit that member,
- see all sensitive information,
- manage the member's account,
- or change the member's organizational assignment.
These are separate permissions.
## 24. ORGANIZATION DIRECTORY EXPERIENCE
Users should be able to navigate from organizational context to members naturally.
Examples include:
Administration
→ Teams
→ Team
→ Members
→ Member Profile
and:
Member Directory
→ Member Profile
→ Organizational context
The organization and member experiences should feel connected rather than like unrelated databases.
Users should be able to understand:
- where a member belongs,
- who leads that organizational unit,
- and the relationship between administrations and teams.
## 25. MEMBER COUNTS
Where organizational summaries are shown, the platform may display useful counts such as:
- number of teams in an administration,
- number of members in an administration,
- number of members in a team.
Counts should reflect the appropriate current membership/status rules.
Historical/inactive members should not be misleadingly presented as current active membership unless the view explicitly includes them.
## 26. MEMBER IMPORT PURPOSE
KORA currently has member information in spreadsheet form.
The platform must provide a controlled member import process so this information can be migrated into the platform.
This import capability is available to System Admin only.
The import process must not simply insert spreadsheet rows blindly.
It must provide validation and review before confirmation.
## 27. MEMBER IMPORT FLOW
The member import flow must conceptually follow:
1. Upload
2. Column Mapping
3. Preview and Validation
4. Confirm
5. Result
The user must have a chance to review what will happen before final confirmation.
## 28. IMPORT FILE FORMAT
The confirmed requirement for the existing member migration is Excel support.
Do not assume the exact workbook structure before the real current member file is supplied.
Do not hardcode unverified column names.
The platform should be able to map source columns to the approved member fields.
If additional file formats are approved later, they can be added without changing the business meaning of the import flow.
## 29. COLUMN MAPPING
The import process should allow the System Admin to map spreadsheet columns to member fields.
Expected concepts include, where present:
- name,
- phone number,
- email,
- university/student ID,
- administration,
- team,
- organizational role,
- and other approved member fields.
The exact final mapping must be based on the actual spreadsheet once it is provided.
Do not invent missing columns.
## 30. IMPORT PREVIEW
Before confirmation, imported rows must be classified clearly.
The currently required conceptual classifications include:
- New
- Existing / Update
- Error
The preview should explain what will happen to each row.
Examples:
New:
The person does not currently exist as a matching member and would be added.
Existing / Update:
The row corresponds to an existing member and would update approved information.
Error:
The row cannot safely be imported and requires correction.
Do not silently skip invalid data without communicating why.
## 31. IMPORT VALIDATION
Import validation must protect organizational integrity.
If the spreadsheet references an administration or team that does not exist in the current organizational structure, this must be reported clearly as an error.
Do NOT automatically create:
- a new administration,
- or a new team
simply because an unknown name appears in the spreadsheet.
Organizational structure must be managed intentionally through the appropriate organizational management capability.
Other invalid or incomplete required member information should also produce understandable validation feedback.
## 32. EXISTING MEMBER MATCHING
The import process must distinguish new members from existing members reliably enough to avoid accidental duplicate member creation.
The exact matching rules must be defined using confirmed member data and the actual import file.
Do not invent a final duplicate/matching algorithm before the real data and identifiers are reviewed.
University/student ID is an important member identifier, but do not silently assume it is the only matching rule unless explicitly confirmed.
## 33. IMPORT CONFIRMATION
The System Admin must explicitly confirm the import after reviewing the preview.
The confirmation should communicate the expected impact, such as:
- how many members will be created,
- how many existing members will be updated,
- how many rows contain errors,
- and which rows will not proceed.
The import should not be finalized merely because a file was uploaded.
## 34. IMPORT RESULT
After confirmation, the System Admin should receive a clear result.
The result should communicate:
- successful additions,
- successful updates,
- failures,
- and any rows that require further attention.
The System Admin should be able to understand what happened without manually comparing the entire spreadsheet against the directory.
## 35. IMPORT AND ACCOUNT RELATIONSHIP
Because every KORA member should have a platform account, member import must eventually coexist with account provisioning.
However:
Member Import
and
Account Authentication Setup
remain conceptually different concerns.
Do not assume that importing a spreadsheet row automatically means that a fully usable account with an arbitrary password should be silently created.
Any account provisioning behavior must remain consistent with Section 1's account and temporary-password rules.
Do not invent an unapproved account activation flow.
## 36. SEARCH AND FILTER BEHAVIOR
Member and organization search/filtering should help users find information quickly without exposing data they are not allowed to access.
Search results must respect:
- effective permissions,
- effective scope,
- member privacy rules,
- and user-specific overrides.
A restricted member or restricted field must not become discoverable merely through search.
Filters should preserve meaningful context when users navigate between lists and profiles where appropriate.
## 37. MOBILE BEHAVIOR
Organization and member experiences must remain usable on mobile.
Dense desktop-style tables should not be assumed to be the only presentation.
On smaller screens:
- member information should remain readable,
- important actions should remain accessible,
- member lists may use card-style representations,
- organization hierarchy must remain navigable,
- search and filtering must remain usable.
System Admin-heavy bulk workflows such as spreadsheet import may reasonably be optimized primarily for desktop if necessary, but the platform should communicate that clearly rather than presenting a broken mobile experience.
## 38. RTL AND ACCESSIBILITY
All Section 1 platform-wide RTL and accessibility requirements apply here.
In particular:
- organizational hierarchy must work naturally in Arabic RTL,
- member lists must remain understandable without relying on visual direction alone,
- status must not depend only on color,
- privacy-sensitive actions must have clear labels,
- keyboard and focus behavior must remain usable,
- and mobile/desktop layouts must preserve semantic relationships.
## 39. EMPTY, LOADING, AND ERROR STATES
Organization and member experiences must account for:
Loading
- while organizational/member information is being retrieved.
Empty
- no teams yet,
- no members in a valid scope,
- no search results,
- no import rows in a category.
Error
- failed loading,
- invalid import data,
- unknown organizational reference,
- failed administrative operation,
- or other known failure states.
Empty states should suggest a meaningful next step only if the current user has permission to perform that step.
For example:
A System Admin may see an action to add the first member.
An ordinary Member should not see an administrative creation action merely because the list is empty.
## 40. PERMISSION-AWARE ACTIONS
All organization/member actions must use Section 1's effective permission model.
Do not infer permission solely from:
- page visibility,
- organizational role,
- organizational seniority,
- or the fact that the user can view a member.
Examples:
A Team Leader may be allowed to view a member without being allowed to edit the member.
An Administration Manager may see all members in the administration but still not have member-management authority.
An Event/Project Leader may have broad visibility but can still be denied a capability by System Admin.
A Member may be granted exceptional visibility outside his normal team by a System Admin override.
System Admin remains the only role authorized to manage member records according to the agreed business rule.
## 41. RELATIONSHIP WITH TASKS
Members and organizational units will later be used by the task system.
Section 3 will define:
- task creators,
- assignees,
- multi-member assignment,
- team-wide assignment,
- team task visibility,
- member self-created tasks,
- task history,
- task performance,
- and analytics.
This section must provide coherent organizational/member concepts for those features without defining their task behavior prematurely.
Do not invent task rules here.
## 42. RELATIONSHIP WITH COMMUNICATION
Members, teams, administrations, and organizational roles will later be used as communication audiences.
Section 4 will define:
- individual messages,
- team messages,
- administration messages,
- organization-wide broadcasts,
- reminders,
- and notifications.
This section should preserve the organizational/member information required for those audiences without defining communication behavior prematurely.
## 43. RELATIONSHIP WITH RECRUITMENT
KORA's existing recruitment/selection platform remains a separate platform.
Do not rebuild:
- applicants,
- applicant decisions,
- selection queues,
- objections,
- recruitment imports,
- or other recruitment functionality here.
The future lifecycle may include:
Applicant
→ Accepted Applicant
→ KORA Member
However, the actual integration between the existing recruitment platform and the new member platform belongs to Section 5.
For now, preserve the ability for a person who becomes an official member to exist correctly in the Member domain.
Do not invent an API or automatic conversion mechanism.
## 44. HISTORICAL INTEGRITY
Organization and member changes must not destroy the meaning of historical platform activity.
Examples:
- moving a member to another team should not imply that old activity happened in the new team;
- renaming or deactivating a team should not make old references unintelligible;
- deactivating a member should not erase historical activity;
- changing organizational leadership should not rewrite who performed past actions.
The detailed Audit Log is defined in Section 5, but this domain must preserve enough conceptual integrity for meaningful historical records.
## 45. ADMINISTRATIVE SAFETY
Sensitive organizational/member actions should use appropriate confirmation.
Examples include:
- moving a member,
- deactivating a member,
- deactivating a team,
- moving a team to another administration,
- bulk importing members,
- and other high-impact administrative changes.
The confirmation should explain the impact where appropriate.
Do not use confirmation dialogs mechanically for harmless actions.
## 46. CONCURRENT CHANGES
Section 1's concurrent-change rule applies.
If two authorized administrative actions conflict, the platform should not silently overwrite newer information.
For example:
- two administrators editing the same member,
- organizational placement changing while another edit is open,
- a team changing while an import references it.
The affected user should be informed that the information changed and should be given an appropriate way to refresh/review the current state.
## 47. OUT OF SCOPE FOR THIS SECTION
Do not fully define or build:
- authentication,
- permission engine internals,
- task management,
- task assignment,
- task status,
- task analytics,
- messaging,
- notifications,
- reminders,
- Audit Log UI,
- recruitment/selection,
- applicant conversion integration,
- or external WhatsApp automation.
Those belong to other sections.
This section should define only the organization/member behavior required for those later capabilities.
## 48. UNRESOLVED INFORMATION
Do not invent answers for information that is still pending.
The following are intentionally unresolved:
1. The final list of KORA administrations.
2. The final list of teams under each administration.
3. The actual current member Excel file and its exact columns.
4. The final matching/duplicate-detection rule for imported members.
5. The exact permanent deletion policy for member records.
6. Any additional member fields discovered when the real spreadsheet is reviewed.
7. Detailed behavior for historical tasks after organizational moves; Section 3 will define task-specific consequences.
8. The exact future integration mechanism between accepted applicants and member creation; Section 5 will define this when real integration information exists.
When any of these become necessary, request or use the real information rather than inventing it.
## 49. IMPORTANT RULES TO PRESERVE
Never lose the following distinctions and business rules:
Organization Structure ≠ Permission Structure
Organizational Role ≠ Effective Access
Member ≠ User Account
Member Visibility ≠ Member Edit Permission
Contact Visibility ≠ General Member Visibility
System Admin ≠ Organizational Leader
Recruitment Applicant ≠ KORA Member
Inactive Member ≠ Historically Deleted Person
Inactive Team ≠ Nonexistent Historical Team
Spreadsheet Import ≠ Automatic Blind Data Creation
Unknown Administration/Team in Import ≠ Permission to Create It Automatically
And most importantly:
System Admin is the only authority responsible for adding, editing, moving, deactivating/removing, importing, and administratively managing KORA members.
## 50. EXPECTED PRODUCT RESULT
When this section is fully represented in the product, KORA should have a coherent organizational and membership system where:
- KORA's event/project leadership is represented clearly;
- the Project Management Office is represented as a distinct organizational unit;
- administrations contain teams;
- teams contain members;
- administration and team leadership are understandable;
- there is no separate Deputy Team Leader platform role;
- the final organization structure can be added later without redesigning the domain;
- organizational units can be managed without destroying historical meaning;
- every member has a clear organizational placement;
- every member can be associated with his platform account while Member and User Account remain distinct concepts;
- users can search and browse members according to their effective access;
- sensitive contact information respects privacy and permission rules;
- authorized users can open useful member profiles;
- ordinary leaders can view operational member information without automatically receiving member-administration authority;
- System Admin alone manages member records;
- System Admin can add, edit, move, deactivate/remove, and import members;
- the existing member spreadsheet can be migrated through a controlled Upload → Mapping → Preview → Confirm flow;
- invalid organizational references are caught rather than silently creating new structure;
- existing members can be distinguished from new members before import confirmation;
- historical organizational context remains meaningful;
- and the domain is ready to support tasks, communication, analytics, auditing, and future recruitment integration in later sections.
Do not weaken these rules to fit a generic employee directory or conventional organization-management template.
# SECTION 3 — TASKS, WORKSPACES & ANALYTICS
You are defining the third functional domain of the new KORA internal operations platform.
This specification is product- and behavior-focused only.
Do not assume or prescribe:
- frontend architecture,
- backend architecture,
- APIs,
- database schemas,
- frameworks,
- libraries,
- infrastructure,
- or implementation technologies.
Section 1 already defines:
- authentication,
- accounts,
- organizational roles,
- System Admin,
- permissions,
- scopes,
- user-specific overrides,
- permission-aware access,
- shared platform states,
- responsiveness,
- RTL,
- accessibility,
- and common platform behavior.
Section 2 already defines:
- KORA's organizational structure,
- Event/Project leadership,
- Project Management Office,
- administrations,
- teams,
- members,
- member profiles,
- member privacy,
- member administration,
- and member import.
Do not redefine or weaken those rules here.
This section defines KORA's operational work system:
- tasks,
- task creation,
- self-created tasks,
- assignment,
- multiple assignees,
- team-wide assignments,
- task source,
- PMO-originated tasks,
- task status,
- task notes,
- task history,
- task visibility,
- task editing,
- archiving,
- reminders associated with tasks,
- personal workspaces,
- team workspaces,
- administration workspaces,
- Home,
- My Tasks,
- and performance analytics.
Preserve every business rule below.
## 1. CORE PURPOSE
The task system is the operational core of the KORA platform.
Its purpose is to replace spreadsheet-based task tracking with a shared system where members and leadership can understand:
- what work exists,
- who created it,
- which team it belongs to,
- who is responsible for it,
- when it is due,
- what its current status is,
- what changed,
- who changed it,
- what notes have been added,
- what work belongs specifically to the current user,
- what work exists across a team,
- and how teams and administrations are performing.
The platform must support both individual responsibility and shared team visibility.
Tasks must not behave like isolated private to-do items.
## 2. TASK CONCEPT
Every task must have a clear identity and operational context.
A task must support at least:
- title,
- description,
- creator,
- organizational/team context,
- responsible assignee(s),
- deadline,
- priority,
- current status,
- notes/activity,
- relevant timestamps,
- task source/context where applicable,
- history of meaningful changes,
- archive state,
- and reminder behavior where applicable.
The task must always make it possible to distinguish:
Who created the task?
Who is responsible for executing it?
These are not the same concept.
## 3. TASK CREATOR
Every task must preserve the identity of the person who created it.
The creator must remain visible as part of the task's information.
Examples:
Created by: [Member Name]
Created by: [Team Leader Name]
Created by: [PMO Member Name]
Creating a task does not automatically mean that the creator is responsible for executing it.
The creator may:
- assign the task to himself,
- assign it to another authorized person,
- assign it to multiple people,
- or assign it to an entire team,
depending on his effective permissions.
Historical creator information must not be rewritten merely because the creator later changes team, role, or organizational position.
## 4. WHO CAN CREATE TASKS
Task creation must follow effective permissions from Section 1.
Do not hardcode task creation solely from organizational roles.
However, the product must support the normal operational use cases where authorized leadership users can create tasks for their allowed scope.
In addition, there is one explicit business rule:
Every ordinary Member must be able to create a task for himself.
This self-task capability is part of normal member behavior.
Therefore:
A Member does NOT need general task-assignment authority merely to create a task for himself.
Do not interpret self-task creation as permission to assign tasks to other people.
## 5. MEMBER SELF-CREATED TASKS
A Member may create a task for himself.
A self-created task is a real KORA task.
It is NOT a private personal to-do item hidden from the team.
It belongs to the appropriate team/work context and participates in the task system.
Therefore, when a Member creates a task for himself:
- the Member is the creator,
- the Member is an assignee,
- the task is associated with the relevant team,
- the task is visible to people who are allowed to see that team's tasks,
- it follows the normal task lifecycle,
- it may affect task counts and analytics according to the same agreed calculation rules,
- and its activity/history is treated like other tasks.
Do not create a separate private task system unless explicitly requested later.
## 6. TASK ASSIGNMENT
The platform must support more than one assignment model.
A task may be assigned to:
1. One specific member.
2. Multiple specific members.
3. The entire team.
Do NOT restrict a task to exactly one assignee.
The task must communicate clearly whether responsibility belongs to:
- one person,
- several named people,
- or the team collectively.
## 7. MULTIPLE ASSIGNEES
A task may have several responsible members simultaneously.
For example:
Responsible:
- Member A
- Member B
- Team Leader C
The system must treat these people as assignees of the same task rather than automatically creating unrelated duplicate tasks.
Do not assume that only ordinary Members can be selected.
If the creator's effective permissions allow it, an assignee may be someone organizationally above the creator.
## 8. ASSIGNMENT TO ORGANIZATIONALLY SENIOR USERS
Organizational hierarchy must not automatically block task assignment upward.
For example, if a user's effective permissions allow the assignment, that user may assign a task to:
- a Team Leader,
- an Administration Manager,
- or another organizationally senior person.
Do not implement a generic rule such as:
"You may only assign tasks to people below you."
Task-assignment authority is determined by effective permissions and scope, not merely by organizational seniority.
## 9. TEAM-WIDE TASKS
A task may be assigned to the entire team.
This means responsibility is attached to the team rather than to only one named member.
The task must clearly indicate:
Responsible: Entire Team
Do not silently convert a team-wide task into separate unrelated tasks for every member unless a future requirement explicitly requests that behavior.
Team-wide tasks must remain distinguishable from individually assigned tasks.
## 10. ORGANIZATIONAL CONTEXT OF A TASK
Every task must have a clear work context.
At minimum, the relevant team must be identifiable.
This is important for:
- visibility,
- workspace placement,
- filtering,
- assignment,
- reporting,
- and analytics.
Where broader administration context is needed, it should follow from the organizational structure defined in Section 2.
Do not create free-floating organizational names that are disconnected from the actual KORA structure.
## 11. TASK CREATION INFORMATION
When creating a normal task, the product must support the relevant information required to define the work clearly.
This includes:
- task title — required,
- description — optional,
- relevant team — required where applicable,
- deadline,
- assignment mode,
- assignee(s) where applicable,
- priority,
- reminder configuration where applicable.
The exact available teams and people must respect the user's effective access.
Do not allow the user to select invalid or unauthorized organizational targets merely because they exist elsewhere in KORA.
## 12. TASK PRIORITY
Tasks support the following currently agreed priority levels:
- Normal
- Important
- Urgent
Priority is separate from task status.
For example:
Urgent ≠ Overdue
Important ≠ In Progress
Priority communicates importance.
Status communicates progress/outcome.
Do not merge these concepts.
## 13. TASK DEADLINE
Every task should support a deadline.
The deadline must be visible wherever understanding urgency or responsibility requires it.
The task experience should make it clear:
- when the task is due,
- whether the deadline is approaching,
- and whether the task has become overdue.
Do not treat "overdue" as a manually selected priority.
Overdue is derived from the task's deadline and its completion/status state.
## 14. TASK STATUS
The currently agreed core task statuses are:
- In Progress
- Completed
- Not Completed
A newly created task starts as:
In Progress
unless a later explicitly approved rule changes this.
Overdue is not a replacement for these statuses.
A task can be considered overdue when:
- its deadline has passed,
- and its current state means it has not been successfully completed.
The product must clearly distinguish:
- current task status,
- deadline state,
- and priority.
## 15. WHO CAN CHANGE TASK STATUS
The platform must support task status changes by all relevant operational participants according to effective permissions.
The agreed normal behavior includes:
- the assigned Member may change the status of his task,
- the Team Leader may change task status within the permitted scope,
- the Administration Manager may change task status within the permitted scope.
Do not implement the earlier unresolved model where a Member can only say "I finished it" and must always wait for leader approval.
The agreed decision is:
Members, Team Leaders, and Administration Managers may change task status where their effective permissions and scope allow it.
Section 1's permission overrides still apply.
A System Admin may alter an individual's effective capabilities.
## 16. STATUS CHANGE NOTIFICATIONS
Task status changes must be visible to the relevant people.
The key business rule is mutual awareness.
If an assigned Member changes the status of a task:
- relevant Team Leader(s) should be notified,
- relevant Administration Manager(s) should be notified where appropriate,
- and other relevant task participants may be notified where appropriate.
If a Team Leader or Administration Manager changes the task's status:
- relevant assignee(s) should be notified,
- and other relevant participants should receive the appropriate awareness.
The purpose is:
No important status change should happen silently when another responsible party needs to know about it.
Detailed notification delivery and notification-center behavior belong to Section 4.
This section defines the task event that must exist.
## 17. STATUS CHANGE HISTORY
Every meaningful status change must preserve history.
The task should make it possible to understand:
- previous status,
- new status,
- who changed it,
- when it changed.
Do not simply replace the status value and discard the previous change history.
Example:
In Progress
→ Completed
Changed by: Member X
Time: ...
If the status later changes again, that new event should also be preserved.
## 18. NOTES
Tasks support notes.
A user with appropriate access may add a note to a task without necessarily changing the task status.
A note should preserve:
- its content,
- who wrote it,
- when it was added.
Notes should appear in chronological/task activity context.
Do not overwrite older notes when a new note is added.
## 19. NOTES DURING STATUS CHANGES
The task experience should allow relevant context to be captured when status changes occur.
The original product concept requires a note/reason when marking a task as Not Completed.
Preserve this rule:
When a task is changed to Not Completed, an explanatory note/reason is required.
For other status changes, a note may be provided when useful unless a later business rule makes it mandatory.
## 20. TASK ACTIVITY AND CHANGE HISTORY
Each task should provide a coherent history of meaningful activity.
Relevant events may include:
- task created,
- assignment changed,
- status changed,
- note added,
- deadline changed,
- priority changed,
- task edited,
- task archived,
- task restored,
- other meaningful task changes.
The user should be able to understand the sequence of what happened.
At minimum, meaningful history should identify:
- what changed,
- who performed the change,
- and when.
The broader system Audit Log is defined in Section 5.
Task activity is the task-specific operational history visible in the context of the task itself.
Do not confuse the two concepts.
## 21. TASK DETAILS
A task details experience must provide the relevant information in one place.
It should include, as applicable:
- title,
- description,
- creator,
- team,
- assignee(s),
- assignment mode,
- priority,
- deadline,
- current status,
- overdue state,
- source/context,
- notes,
- status history,
- meaningful change history.
Available actions depend on effective permissions.
Potential actions include:
- change status,
- add note,
- edit,
- archive,
- restore where applicable,
- send a manual reminder.
Do not show or allow an action merely because the user can view the task.
## 22. TASK EDITING
Authorized users may edit task information according to their effective permissions.
Editing may include appropriate fields such as:
- title,
- description,
- deadline,
- priority,
- assignee(s),
- team/context where permitted.
Meaningful changes should remain traceable.
Do not silently rewrite task history.
Changing assignees or organizational context can have significant consequences and should be treated as a meaningful change.
## 23. TASK ARCHIVING
Tasks may be archived.
Archiving is not permanent deletion.
An archived task:
- should disappear from normal active task lists,
- should not be treated as active operational work,
- should not incorrectly distort active task indicators,
- should be retrievable through an appropriate archived view/filter by authorized users,
- and may be restored where permitted.
Do not permanently delete task history merely because the task is archived.
## 24. TASK DELETION
Permanent destructive task deletion has not been approved as the normal task lifecycle.
Do not invent hard deletion.
Use archiving as the normal removal mechanism unless a later explicit requirement introduces a controlled permanent deletion rule.
## 25. TASK REMINDERS
A task may have reminder behavior.
The original agreed task concept includes an automatic reminder before the deadline, with the creator/authorized user able to disable that reminder where appropriate.
The current baseline behavior is:
Automatic reminder:
One day before the deadline.
The platform should also support a manual reminder action from task details for authorized users.
The broader reminder scheduling and delivery system is defined in Section 4.
This section only establishes that tasks generate reminder needs/events.
## 26. TASK SOURCE
Tasks may originate from different organizational contexts.
The platform must preserve enough source information to distinguish important cases.
One explicitly required case is:
A task created by someone from the Project Management Office and assigned to another team.
Such a task must be clearly distinguishable from an ordinary internally created team task.
## 27. PMO-ORIGINATED TASKS
If a Project Management Office member creates a task for a different team, that task must receive a distinct visual/semantic treatment.
The user should be able to recognize that the task came from the Project Management Office.
Use an explicit indicator equivalent to:
"From the Project Management Office"
or:
"PMO Task"
The distinction must NOT depend only on color.
A distinct visual accent may be used in addition to the explicit source indicator.
Do not confuse:
- task source,
- task priority,
- task status,
- and assignment type.
These are separate concepts.
## 28. TASK VISIBILITY WITHIN A TEAM
All members of a team should be able to see the team's tasks.
This includes:
- tasks assigned to themselves,
- tasks assigned to other members of the same team,
- multi-assignee tasks,
- team-wide tasks,
- and self-created tasks created by members of that team.
This shared visibility is intentional.
The purpose is to provide team awareness rather than isolated private task lists.
However, Section 1 still applies:
System Admin permission/scope overrides may explicitly restrict or expand access.
Do not treat team visibility as permission to edit every visible task.
Visibility and action authority remain separate.
## 29. HOME VS TEAM VISIBILITY
A critical distinction must be preserved:
Team Workspace:
Shows the team's work.
Home:
Focuses on the current user's own work and attention needs.
Therefore, although a Member can see all team tasks in the Team Workspace, the Home page should not flood that Member with every task belonging to teammates.
Home should prioritize tasks that personally involve the current user.
30. HOME — "MY SPACE"
The Home page is the user's operational starting point.
Its purpose is to answer:
"What needs my attention today?"
It should not behave like a generic directory of links.
The content changes according to the user's effective access and responsibilities.
Relevant Home information may include:
- the user's active tasks,
- the user's overdue tasks,
- tasks due soon,
- unread messages,
- upcoming reminders,
- and other role/permission-specific items from later sections.
The task portion of Home should focus on work personally relevant to the current user.
## 31. HOME TASK SUMMARY
Home should provide concise task indicators.
Examples include:
- active tasks assigned to me,
- overdue tasks assigned to me,
- tasks due this week,
- other personally relevant task indicators.
Selecting an indicator should take the user to the corresponding detailed workspace with the relevant filter applied where appropriate.
Do not make dashboard numbers decorative.
They should help the user reach the underlying work.
## 32. HOME — TASKS DUE SOON
Home should include a concise list of tasks requiring near-term attention.
The list may include:
- task title,
- deadline,
- overdue indicator where applicable,
- relevant assignment/source context.
The purpose is rapid prioritization.
Do not attempt to show every team task on Home.
## 33. HOME CONTENT FROM OTHER DOMAINS
Home will eventually also include information such as:
- unread messages,
- reminders,
- other permission-relevant attention items.
Those domains are defined in Section 4.
Do not fully define communication/reminder behavior here.
This section only establishes that Home is a cross-domain personal attention surface.
## 34. MY TASKS
The platform must provide a dedicated My Tasks workspace.
Its purpose is to give each user a complete view of work that personally involves him.
The workspace should distinguish useful task groupings such as:
- Current
- Completed
- All
It should also make overdue tasks clearly discoverable.
## 35. WHAT APPEARS IN MY TASKS
My Tasks should include tasks where the current user is personally responsible.
This includes:
- tasks assigned only to the user,
- multi-assignee tasks where the user is one of the assignees,
- team-wide tasks that apply to the user's team where the agreed responsibility model makes them relevant,
- tasks the user created for himself.
Do not automatically include every task visible to the user's team merely because he can see it.
Team visibility belongs to the Team Workspace.
My Tasks represents personal responsibility.
## 36. MY TASKS ACTIONS
From My Tasks, the user should be able to perform the task actions his effective permissions allow.
For an ordinary assigned Member, this normally includes:
- opening task details,
- changing status where permitted,
- adding a note,
- and understanding deadline/priority/source.
The user must not receive general edit/archive powers merely because the task appears in My Tasks.
## 37. ORGANIZATION WORK ENTRY
The platform should provide a clear way to navigate operational work through KORA's organizational structure.
Users with access to multiple organizational units may navigate through:
- administrations,
- teams,
- and their workspaces.
Users who effectively have access to only one relevant team/unit should not be forced through unnecessary organization-wide browsing before reaching their work.
The exact navigation must respect effective scope from Section 1.
## 38. ADMINISTRATION OVERVIEW
An Administration Workspace should provide an operational view of an administration and its teams.
Relevant information may include:
- administration name,
- Administration Manager,
- number of teams,
- number of members,
- overall task completion information,
- teams within the administration,
- work/task summaries,
- and relevant actions according to permissions.
The purpose is to allow authorized users to understand work across the administration without opening each team individually.
## 39. ADMINISTRATION WORKSPACE TABS / AREAS
The Administration Workspace should support coherent views of:
- Overview
- Teams
- Tasks/work
- Members
The exact presentation is flexible, but these concepts should remain easily reachable.
Users should be able to move from administration-level context into a specific team's workspace.
## 40. TEAM WORKSPACE
The Team Workspace is the shared operational space for a team.
All team members should be able to see the team's tasks according to the agreed team-visibility rule and any explicit permission overrides.
The Team Workspace should provide:
- team identity/context,
- Team Leader information,
- members,
- task list,
- task filtering,
- relevant performance summary,
- task creation actions where permitted.
## 41. TEAM TASK LIST
The team task list must make key information understandable without requiring every task to be opened.
Relevant task information includes:
- task title,
- creator,
- responsible assignee(s) or entire-team assignment,
- deadline,
- status,
- priority where useful,
- overdue state,
- task source where important,
- and relevant recent note/context where appropriate.
Do not hide the creator.
The user explicitly requires every task to show who created it.
## 42. TASK FILTERING
Operational task workspaces should support useful filtering.
Required concepts include:
- search by task title,
- status,
- assignment type,
- assignee,
- due/deadline criteria.
Additional useful filters may include:
- priority,
- source,
- archived state,
where appropriate.
Do not introduce filters that have no meaningful product use.
## 43. TASK ORDERING
The agreed default task ordering prioritizes actionable work.
The baseline ordering is:
1. Overdue tasks.
2. In Progress tasks ordered by nearest deadline.
3. Finished/closed task states after active work.
This should help urgent unfinished work surface before completed historical work.
Users may have additional sorting/filtering options where useful, but do not lose the meaningful default ordering.
## 44. ASSIGNMENT TYPE DISTINCTION
The original product concept visually distinguishes:
- tasks assigned to specific people,
- and tasks assigned to an entire team.
Preserve the semantic distinction.
A visual treatment may help users scan the list quickly.
However:
- do not rely on color alone,
- and do not confuse assignment type with task source or status.
Because multiple named assignees are now supported, the "specific people" category includes both:
- one named assignee,
- multiple named assignees.
## 45. TASK CREATION FOR MULTIPLE TEAMS
The original product concept includes the ability for an authorized administration-level user to add similar work to more than one team.
Preserve this capability conceptually.
An authorized user may choose multiple teams where his effective permissions allow it.
The resulting work should preserve clear team ownership/context.
Do not assume that a single task shared ambiguously across unrelated teams is always the correct behavior.
Where the product creates one task instance per team, those tasks should remain understandable as separate team work items.
Do not invent cross-team completion semantics beyond this requirement.
## 46. TEAM MEMBERS AND TASKS
The Team Workspace should connect members and work naturally.
Users should be able to understand:
- who belongs to the team,
- who is responsible for a task,
- and how tasks relate to team members.
Opening a member's identity may lead to the Member Profile defined in Section 2 where permitted.
Opening a task leads to Task Details.
Do not duplicate member administration inside the task system.
## 47. TASK-RELATED MEMBER PERFORMANCE
Member profiles and team views may display task-derived information such as:
- current tasks,
- completed tasks,
- completion rate or related operational indicators.
These values must be derived consistently from the task system.
Do not invent subjective performance ratings.
Do not turn task completion metrics into unsupported judgments about a member's quality or value.
## 48. DASHBOARD PURPOSE
The Dashboard is different from Home.
Home:
Personal attention and personal work.
Dashboard:
Aggregated operational performance and trends.
The Dashboard exists to replace manual spreadsheet calculations and give authorized leadership an understandable view of work performance.
## 49. DASHBOARD ACCESS
Dashboard access and data scope must follow Section 1's effective permission model.
Natural defaults may include:
- organization-wide leadership seeing broad organizational data,
- PMO leadership seeing broad operational information,
- Administration Managers seeing their administration,
- Team Leaders seeing their team.
However, these are defaults.
Do not hardcode the Dashboard only by role.
System Admin permission/scope overrides may expand or restrict dashboard access.
## 50. DASHBOARD TIME FILTERS
The Dashboard should support time-based analysis.
The agreed period concepts include:
- This Week
- This Month
- Custom Period
Where comparisons are shown, the relevant previous period should be understandable.
Do not present a comparison without making its comparison basis clear.
## 51. DASHBOARD ORGANIZATIONAL FILTERS
Where the user has access to more than one organizational scope, the Dashboard should allow appropriate organizational filtering.
Examples include:
- administration,
- team.
The available filters must respect effective access.
A filter must not expose the existence or metrics of an organizational unit the user is not authorized to access.
52. CORE TASK KPIs
The Dashboard should support at least the following core task metrics:
- Total Tasks
- Completed Tasks
- Not Completed Tasks
- In Progress Tasks
- Overdue Tasks where useful
- Overall Completion Rate
The original product concept specifically includes:
- total,
- completed,
- not completed,
- in progress,
- completion percentage,
- and comparison with the previous period.
Preserve those metrics.
## 53. COMPLETION RATE
The agreed baseline definition of task completion rate is:
Completed tasks
÷
All non-archived tasks
The product must communicate the metric clearly enough that users understand what the percentage means.
Archived tasks are excluded from this baseline denominator.
If future requirements introduce period-specific or alternative metrics, label them clearly rather than silently changing the meaning of "Completion Rate."
## 54. PERFORMANCE BY ADMINISTRATION
Authorized organization-wide users should be able to understand task completion/performance across administrations.
The Dashboard should support a comparative view of administrations where the user's access allows it.
Useful information may include:
- completion percentage,
- task counts,
- overdue work.
The purpose is operational visibility, not subjective ranking of people.
## 55. PERFORMANCE BY TEAM
Administration-level users should be able to understand performance across teams within their accessible administration.
The original product concept includes showing teams with lower completion performance and overdue task counts.
Preserve the ability to surface teams requiring operational attention.
Do not label people or teams with subjective judgments.
Use factual metrics.
## 56. LOWEST-COMPLETION TEAMS
The Dashboard may highlight a small number of teams with the lowest completion results in the relevant scope.
The original concept proposes the lowest three teams and their overdue task counts.
Preserve this concept as an operational attention view.
The metric and period must be clear.
Do not turn it into a permanent public ranking unrelated to the selected analysis period.
## 57. TASK TRENDS
The Dashboard should show task activity over time.
The original concept includes a recent four-week view comparing:
- tasks added,
- tasks completed.
Preserve this type of trend view.
The purpose is to help leadership understand whether work is accumulating or being completed over time.
## 58. CLICK-THROUGH FROM ANALYTICS
Where practical, Dashboard metrics should lead users toward the underlying operational context.
Examples:
Selecting an administration performance item
→ Administration Workspace
Selecting a team
→ Team Workspace
Selecting a task count
→ relevant filtered task view
Access permissions still apply.
Analytics should not become a dead-end set of decorative numbers.
## 59. HOME VS DASHBOARD VS WORKSPACES
Preserve the distinction between these concepts:
Home
= What needs my attention?
My Tasks
= What work am I personally responsible for?
Team Workspace
= What work exists across my team?
Administration Workspace
= What work exists across the administration and its teams?
Dashboard
= What do aggregated operational metrics and trends show?
Do not merge all of these into one overloaded page.
They may share task data, but they serve different user goals.
## 60. TASK SEARCH AND DIRECT LINKS
Tasks and filtered task views should participate in Section 1's deep-link behavior.
Where appropriate:
- a task should have a directly reachable location,
- filtered task views should preserve meaningful state,
- notifications/reminders should be able to lead directly to the relevant task,
- refreshing should not incorrectly lose access/context.
Direct links must never bypass authorization.
## 61. PERMISSION-AWARE TASK ACTIONS
Seeing a task does not automatically mean the user can perform every task action.
Treat permissions such as these as conceptually separable:
- view task,
- create self-task,
- create task for others,
- assign task,
- edit task,
- change task status,
- add note,
- archive task,
- restore task,
- send reminder,
- view broader task analytics.
The final permission catalogue may be refined as the platform is implemented/configured.
Do not collapse all task authority into a single "can manage tasks" assumption if that would undermine the agreed flexibility.
## 62. USER-SPECIFIC PERMISSION OVERRIDES
All task behavior must respect Section 1's user-specific overrides.
Examples:
A Member may normally only create a task for himself.
A System Admin could grant that Member additional task-assignment authority.
A Team Leader may normally have broad task authority within the team.
A System Admin could explicitly remove a particular task action from that Team Leader.
An Event/Project Leader may normally have broad visibility.
A System Admin may restrict a specific capability or scope.
Do not hardcode exceptions that make these overrides ineffective.
## 63. CROSS-SCOPE TASK VISIBILITY
The normal team rule is:
Team members see their team's tasks.
Broader organizational users may naturally see tasks in broader scopes according to permissions.
However, effective permissions and explicit scope overrides remain authoritative.
A user should not see a task merely because his title sounds senior enough.
Likewise, a user may be allowed to see a task outside his natural scope if a System Admin explicitly grants that access.
## 64. TASK CREATOR VISIBILITY
The creator's identity is required task information.
It should be visible in appropriate task contexts such as:
- task cards/list items where useful,
- task details,
- activity/history.
This is especially important for distinguishing:
- member self-created tasks,
- team leadership tasks,
- PMO-originated tasks.
Do not hide creator identity behind generic labels when the actual creator is relevant.
## 65. MULTIPLE ASSIGNEES AND STATUS
A task with multiple assignees is still one task.
The current specification does NOT define separate completion states for each individual assignee.
Therefore, do not invent:
- per-assignee completion percentages,
- separate hidden subtask statuses,
- automatic completion when one particular assignee completes,
- unanimous completion requirements,
- or majority approval rules.
The task has the agreed task-level status unless a future requirement explicitly introduces per-assignee progress.
If implementation requires a decision not defined here, surface the ambiguity rather than inventing business behavior.
## 66. TEAM-WIDE TASK COMPLETION
The current specification defines team-wide assignment but does not establish special voting/approval semantics for team-wide completion.
Do not invent them.
The task follows the standard task status model and effective status-change permissions.
If later KORA wants:
- one person to complete on behalf of the team,
- leader approval,
- or member-by-member completion,
that must be defined explicitly later.
## 67. PMO TASK SOURCE VS PERMISSIONS
A PMO-originated task's special visual/source treatment does not automatically create new permissions.
"From the Project Management Office" communicates source.
It does not inherently mean:
- the task cannot be edited,
- the team cannot change status,
- it has Urgent priority,
- it bypasses normal permissions,
- or it must always be completed differently.
Those behaviors still follow task permissions and task fields.
Do not infer additional rules from the PMO label.
## 68. MOBILE TASK EXPERIENCE
Tasks and workspaces must remain fully usable on mobile.
On smaller screens:
- dense desktop task layouts should adapt appropriately,
- filters may be consolidated into an accessible filtering experience,
- task details may use a full-page mobile presentation,
- administration/team navigation must remain usable,
- assignee information must remain understandable,
- status changes and notes must remain practical,
- important task source/deadline/status information must not disappear.
The original concept allows desktop side panels or dialogs to become full-screen mobile experiences.
Preserve functional equivalence rather than forcing identical layouts.
## 69. RTL AND ACCESSIBILITY
All Section 1 RTL and accessibility rules apply.
Task-specific requirements include:
- status must not depend on color alone,
- assignment type must not depend on color alone,
- PMO source must not depend on color alone,
- overdue state must be explicitly understandable,
- controls must be keyboard accessible where applicable,
- focus must remain visible,
- multi-assignee information must remain readable,
- Arabic RTL layout must remain natural,
- task history must preserve readable chronological structure.
## 70. LOADING, EMPTY, AND ERROR STATES
Task/workspace/analytics experiences must handle:
Loading
- task data is being retrieved/calculated.
Empty
Examples:
- no tasks yet,
- no tasks assigned to me,
- no completed tasks,
- no overdue tasks,
- no results for the current filters.
Where appropriate and permitted, an empty state may offer a relevant action.
For example:
My Tasks empty state
→ Member may be offered "Create a task for myself."
Team Workspace empty state
→ a user with appropriate task-creation permission may be offered "Add the first task."
A user without that permission must not be shown an unauthorized creation action.
Error
- failed task loading,
- failed status update,
- failed note,
- failed analytics loading,
- conflict with a newer task change,
- or other understandable operational failure.
## 71. CONCURRENT TASK CHANGES
Section 1's concurrent-change principle applies strongly to tasks.
If two authorized users are working on the same task and one changes it before the other submits an outdated change, the platform must not silently overwrite the newer information.
The second user should receive a clear message equivalent to:
"This task was modified by someone else."
and be given an appropriate way to refresh/review the current task.
This is especially relevant to:
- status,
- assignment,
- deadline,
- priority,
- editing.
## 72. TASK CONFIRMATIONS
Use confirmation when the effect justifies it.
Examples may include:
- archiving a task,
- restoring where consequential,
- changing significant assignment/context,
- other high-impact actions.
Do not add confirmation to every routine status change or note if it unnecessarily slows normal work.
## 73. ANALYTICS CONSISTENCY
The same task must not produce contradictory metrics across different views.
Definitions such as:
- active,
- completed,
- not completed,
- overdue,
- archived,
- completion rate
must remain consistent across:
- Home summaries,
- My Tasks,
- Team Workspace,
- Administration Workspace,
- Dashboard.
Different views may filter different scopes, but they must not silently redefine the same metric.
## 74. ARCHIVED TASKS AND ANALYTICS
Archived tasks are excluded from the baseline Completion Rate definition.
They should also not appear as ordinary active work.
If historical analytics later need to include archived records for a specific report, that report must state its calculation clearly.
Do not silently mix archived and active operational work.
## 75. RELATIONSHIP WITH MEMBERS
Task assignment must use the member and organizational information defined in Section 2.
Do not create duplicate independent representations of:
- members,
- teams,
- administrations,
- leaders.
If a task references a member, that person is the same KORA Member represented elsewhere in the platform.
Member administration remains a System Admin responsibility under Section 2.
Task users do not gain member-management authority merely because they can assign work to someone.
## 76. RELATIONSHIP WITH COMMUNICATION
Section 4 will define:
- messaging,
- notifications,
- reminders.
This section generates events that Section 4 must be able to communicate.
Examples include:
- task assigned,
- task status changed,
- task deadline approaching,
- task overdue,
- manual reminder requested.
Do not fully define delivery channels here.
## 77. RELATIONSHIP WITH AUDIT
Section 5 defines the system-wide Audit Log.
This section must preserve meaningful task actions so they can later participate in system auditing.
Relevant actions include:
- task creation,
- task edits,
- assignment changes,
- status changes,
- notes,
- archiving,
- restoring,
- other sensitive task operations.
Do not wait until Section 5 conceptually to care about the identity of the actor or the meaning of a task change.
## 78. OUT OF SCOPE FOR THIS SECTION
Do not fully define:
- account/authentication behavior,
- permission administration,
- member administration,
- organization creation/editing,
- messaging,
- broadcast messages,
- notification-center delivery behavior,
- general reminder scheduling,
- automated WhatsApp integration,
- system-wide Audit Log interface,
- recruitment/selection functionality,
- recruitment-to-member integration.
Those belong to other sections.
## 79. UNRESOLVED INFORMATION
Do not invent answers for requirements that are not yet finalized.
Currently unresolved or intentionally deferred:
1. The final KORA administration/team list.
2. Detailed final permission names for every task action.
3. Special completion semantics for multiple-assignee tasks, beyond the currently defined task-level status.
4. Special completion semantics for team-wide tasks, beyond the standard task-level status.
5. Whether any additional task statuses will be introduced later.
6. Whether deadlines require time-of-day in every case or only a date.
7. Any future external notification channel such as WhatsApp.
8. Any advanced analytics not explicitly defined here.
9. Any permanent task deletion behavior.
Do not invent these rules.
If one becomes necessary to proceed, identify it explicitly.
## 80. IMPORTANT DISTINCTIONS TO PRESERVE
Never collapse the following concepts:
Task Creator ≠ Task Assignee
Task Visibility ≠ Task Edit Permission
Task Status ≠ Task Priority
Task Status ≠ Overdue State
Assignment Type ≠ Task Source
PMO Source ≠ Urgent Priority
Self-Created Task ≠ Private Task
Team Workspace ≠ My Tasks
My Tasks ≠ Every Task I Can See
Home ≠ Team Workspace
Home ≠ Dashboard
Dashboard ≠ Task List
Task Activity History ≠ System Audit Log
Archived ≠ Deleted
Organizational Seniority ≠ Automatic Assignment Authority
Team Visibility ≠ Authority to Change Every Task
Multiple Assignees ≠ Multiple Independent Tasks
And preserve these critical business rules:
- Every task identifies its creator.
- Every task identifies its deadline.
- Every task identifies who is responsible for execution.
- A task may have one assignee, multiple assignees, or an entire team.
- Assignment may include a person organizationally above the creator when effective permissions allow it.
- Every Member may create a task for himself.
- A self-created task is visible as part of the team's work, not private.
- All team members can see their team's tasks by default.
- Home focuses on the current user's own work rather than all team work.
- Members, Team Leaders, and Administration Managers can change task status according to effective permissions.
- Relevant people are notified when task status changes.
- PMO-created work assigned to another team is explicitly identifiable as PMO-originated.
- PMO source must not rely only on color.
- System Admin overrides remain authoritative over default task permissions and scopes.
## 81. EXPECTED PRODUCT RESULT
When this section is fully represented in the product, KORA should have a complete operational work system where:
- every task has a clear creator;
- every task has clear responsibility;
- every task has a deadline;
- priorities and statuses are distinct;
- tasks can be assigned to one person, several people, or an entire team;
- authorized users can assign work upward or across the permitted organizational scope without artificial hierarchy restrictions;
- every Member can create a task for himself;
- self-created tasks participate in the real team task system;
- team members can see their team's work;
- personal work remains focused in Home and My Tasks;
- status changes are traceable;
- relevant participants are made aware of status changes;
- notes preserve operational context;
- task history explains what happened and who did it;
- tasks can be archived without destroying their history;
- PMO-originated tasks sent to other teams are clearly identifiable;
- administrations and teams have coherent operational workspaces;
- users can search and filter work effectively;
- Home answers what personally needs attention;
- My Tasks shows personal responsibility;
- Team Workspace shows team work;
- Administration Workspace shows administration-level work;
- Dashboard provides factual operational metrics and trends;
- Completion Rate uses the agreed Completed ÷ All Non-Archived Tasks definition;
- analytics respect organizational scope and user-specific permission overrides;
- task behavior remains consistent across all workspaces;
- and the domain is ready to integrate with communication, reminders, notifications, and system-wide auditing in later sections.
Do not simplify this domain into a generic single-assignee task manager.
KORA's task system is intentionally collaborative, organization-aware, permission-aware, transparent within teams, and flexible enough to support individual work, multi-person responsibility, team-wide responsibility, PMO-originated work, and leadership oversight.
# SECTION 4 — COMMUNICATION, NOTIFICATIONS & REMINDERS
You are defining the fourth functional domain of the new KORA internal operations platform.
This specification is product- and behavior-focused only.
Do not assume or prescribe:
- frontend architecture,
- backend architecture,
- APIs,
- database schemas,
- frameworks,
- libraries,
- infrastructure,
- notification providers,
- messaging providers,
- or implementation technologies.
Section 1 already defines:
- authentication,
- user accounts,
- organizational roles,
- System Admin,
- permissions,
- scopes,
- user-specific overrides,
- permission-aware access,
- shared platform states,
- responsiveness,
- RTL,
- accessibility,
- and common platform behavior.
Section 2 already defines:
- KORA's organizational structure,
- Event/Project leadership,
- Project Management Office,
- administrations,
- teams,
- members,
- member privacy,
- and member profiles.
Section 3 already defines:
- tasks,
- task assignment,
- task lifecycle,
- task activity,
- personal workspaces,
- team/administration workspaces,
- Home,
- and analytics.
Do not redefine or weaken those rules here.
This section defines KORA's internal communication and attention-delivery system:
- individual messages,
- Inbox,
- Sent,
- Archive,
- replies,
- message priorities,
- broadcast messages,
- audience targeting,
- scheduled messages,
- notifications,
- notification read state,
- reminders,
- scheduled reminders,
- recurring reminders,
- task-related reminders,
- and the relationship between messages, reminders, notifications, and Home.
Preserve every business rule below.
## 1. CORE PURPOSE
KORA needs an internal communication system so operational communication does not depend entirely on external messaging applications.
The platform must allow users to:
- receive official internal messages,
- send permitted messages,
- communicate directly where allowed,
- send announcements/broadcasts to organizational audiences where authorized,
- distinguish urgent communication from normal communication,
- keep communication available after it is sent,
- receive quick notifications about important platform events,
- schedule reminders,
- receive task-related reminders,
- and navigate from an alert directly to the relevant platform context.
The communication system should help users understand:
"What was communicated?"
"Who sent it?"
"Who was it sent to?"
"How important is it?"
"Have I read it?"
"Does it require my attention?"
"When should I be reminded?"
## 2. THREE RELATED BUT DISTINCT CONCEPTS
Preserve the distinction between:
1. Messages
Persistent communication content between users or organizational audiences.
2. Notifications
Short attention signals generated by platform events.
3. Reminders
Time-based communication intended to remind users about something.
These concepts may interact, but they are not identical.
For example:
A task status change
→ may generate a notification.
A scheduled reminder
→ may appear in the user's communication experience and notification area when its time arrives.
A broadcast message
→ remains a message even if it also generates a notification.
Do not collapse all three into one generic alert object from a product-behavior perspective.
## 3. INTERNAL MESSAGING
The platform must provide an internal messaging experience.
The primary communication areas include:
- Inbox
- Sent
- Archive
Inbox contains messages received by the current user.
Sent contains messages sent by the current user where applicable.
Archive contains messages the user has archived.
Messages should remain accessible according to the appropriate lifecycle rather than disappearing immediately after being read.
## 4. INBOX
Inbox is the user's main location for persistent received communication.
It should allow the user to understand at least:
- message priority,
- sender,
- audience/recipient context where relevant,
- sent time,
- a useful preview/excerpt,
- read/unread state.
Unread messages must be clearly distinguishable.
The distinction must not depend only on color.
## 5. MESSAGE READING
Opening a message should provide the full communication context.
Relevant information includes:
- sender,
- recipients/audience where appropriate,
- priority,
- sent time,
- full message content,
- and relevant reply/action options.
Reading a message should update its read state appropriately.
Do not treat merely seeing a preview in a list as necessarily equivalent to reading the full message unless explicitly defined later.
## 6. READ / UNREAD STATE
Messages must support read/unread state.
Unread messages should contribute to relevant unread indicators.
A user should be able to understand which messages have not yet been read.
The communication system should support the platform-wide attention model, including:
- Inbox counters,
- Home summaries,
- and other relevant indicators.
Do not expose another user's private read state unless a future requirement explicitly introduces delivery/read tracking for senders.
## 7. MESSAGE ARCHIVE
Users should be able to archive messages.
Archiving does not permanently delete the message.
Archived messages:
- leave the normal active Inbox/Sent view where appropriate,
- remain available through Archive,
- and may be restored where appropriate.
Do not treat Archive as permanent deletion.
Permanent message deletion behavior has not been defined.
Do not invent it.
## 8. MESSAGE SEARCH
Users should be able to search their accessible messages.
Search should help locate relevant communication without exposing messages the user is not authorized to access.
Search must respect:
- effective permissions,
- recipient relationships,
- scope,
- and user-specific overrides.
A message must not become discoverable through search merely because it exists elsewhere in the platform.
## 9. MESSAGE PRIORITY
Messages support the following agreed priority levels:
- Normal
- Important
- Urgent
Priority should be clearly communicated.
The user should be able to distinguish urgent communication quickly.
Do not rely only on color to communicate priority.
Message priority is separate from:
- read/unread state,
- recipient scope,
- message type,
- and notification state.
## 10. MESSAGE ORDERING
The communication experience should prioritize attention appropriately.
The original product concept requires urgent messages to surface prominently, followed by recency.
Preserve the principle that urgent communication should not be buried beneath ordinary messages merely because of chronological ordering.
The exact ordering should remain understandable and predictable.
## 11. INDIVIDUAL MESSAGES
The platform must support direct communication to one person where the sender's effective permissions allow it.
Relevant places elsewhere in the platform may provide entry points to message a member directly, such as:
- Member Profile,
- member-related context,
- or communication areas.
The recipient must be a valid accessible member/account.
Do not allow direct messaging to bypass Section 1's access rules or Section 2's member/privacy rules.
## 12. REPLIES
Users should be able to reply to messages where replies are allowed.
A reply should preserve enough context for the conversation to remain understandable.
Do not invent a complex real-time chat system.
This requirement defines internal messaging/reply behavior, not necessarily instant chat presence, typing indicators, calls, or other chat-app features.
## 13. BROADCAST MESSAGES
The platform must support broadcast/group communication for authorized users.
A broadcast allows one message to be sent to an organizational audience.
Potential audience types include:
- all members,
- an administration,
- a team,
- an organizational role/group.
The available audience options depend on the sender's effective permissions and scope.
Do not assume every user can broadcast.
## 14. BROADCAST AUTHORITY
Broadcast authority must follow Section 1's permission system.
Natural organizational defaults may include:
- organization-wide leadership or appropriately authorized PMO users communicating broadly,
- Administration Managers communicating within their administration,
- Team Leaders communicating within their team.
However, these are defaults rather than immutable role rules.
System Admin permission overrides remain authoritative.
A System Admin may:
- grant additional communication authority,
- remove broadcast authority,
- broaden communication scope,
- or restrict it.
Do not hardcode broadcast rights solely from role names.
## 15. BROADCAST AUDIENCE SCOPE
A user must not be able to select a broadcast audience outside his effective allowed scope.
For example, under normal defaults:
A Team Leader
→ may communicate to his team.
An Administration Manager
→ may communicate to his administration and its teams.
A broader authorized user
→ may communicate to broader audiences.
But explicit System Admin overrides may change those defaults.
The audience selector must reflect actual effective access.
## 16. BROADCAST RECIPIENT COUNT
Before a broadcast is sent, the sender should be able to understand how many recipients will receive it.
This is especially important for broad communication.
The recipient count should reflect the actual resolved audience at the relevant time as accurately as practical.
Do not present a broad organizational label without helping the sender understand its impact.
## 17. BROADCAST CONFIRMATION
High-impact broadcasts require confirmation.
In particular, sending a message to all KORA members must require a confirmation that communicates the number of recipients.
The confirmation should explain the impact.
Example concept:
"You are about to send this message to 145 members."
Do not use a vague confirmation such as only:
"Are you sure?"
## 18. BROADCAST CONTENT
A broadcast should support:
- audience,
- message content,
- priority,
- sending time.
The sender should understand:
- who will receive it,
- how important it is,
- and whether it will be sent immediately or scheduled.
Do not invent attachments, rich formatting, polls, reactions, or other messaging features unless explicitly requested later.
## 19. SEND NOW
An authorized message/broadcast may be sent immediately.
Once sent:
- recipients should receive the persistent message,
- relevant unread indicators should update,
- appropriate notifications may be generated,
- and the sender should be able to understand that the send action succeeded.
Sent communication should remain available in the appropriate history.
## 20. SCHEDULED BROADCAST
The platform must support scheduling a broadcast/message for a future time.
The sender chooses an approved future date/time rather than sending immediately.
Before the scheduled send occurs, authorized users should be able to understand that the communication is scheduled.
Appropriate edit/cancel behavior should be available before delivery where permitted.
Do not treat a scheduled message as already delivered.
## 21. SCHEDULED MESSAGE VS REMINDER
Preserve the distinction:
Scheduled Message
= persistent communication intentionally scheduled for future delivery.
Reminder
= time-based reminder intended to prompt attention about something.
They may use similar scheduling concepts, but they serve different product purposes.
Do not automatically merge them into one user-facing concept.
## 22. NOTIFICATION SYSTEM
The platform must provide a notification system for quick attention signals.
Notifications are accessible through the platform's notification area, represented conceptually by a notification bell.
Notifications should help users notice important events without requiring them to constantly inspect every workspace.
## 23. NOTIFICATION EVENTS
Notifications may be generated by events from multiple platform domains.
Agreed examples include:
- a task was assigned to the user,
- a task's status changed,
- an assigned Member changed task status,
- a Team Leader or Administration Manager changed task status,
- a task is due soon,
- a task became overdue,
- a new message was received,
- an urgent message was received,
- a scheduled reminder became due.
Later platform capabilities may introduce additional valid notification events.
Do not invent unrelated notification categories without a product need.
## 24. TASK STATUS NOTIFICATIONS
Section 3 defines an important mutual-awareness rule.
If an assigned Member changes a task's status:
- relevant Team Leader(s) should receive awareness,
- relevant Administration Manager(s) should receive awareness where appropriate.
If a Team Leader or Administration Manager changes the status:
- relevant assignee(s) should receive awareness.
Section 4 is responsible for representing these events through the notification system.
Do not silently discard status-change events.
## 25. TASK ASSIGNMENT NOTIFICATIONS
When a user becomes responsible for a task, the platform should notify that user appropriately.
This applies to:
- single-person assignment,
- addition to a multi-assignee task,
- and other cases where personal responsibility is newly created.
Team-wide task behavior should avoid unnecessary notification spam while still ensuring relevant team awareness.
Do not invent excessive notification behavior without considering the difference between personal assignment and broad team visibility.
## 26. TASK DEADLINE NOTIFICATIONS
Tasks may generate time-sensitive notifications.
The baseline agreed task reminder is:
One day before the deadline.
A task that becomes overdue may also generate an appropriate overdue reminder/notification.
Section 3 defines the task/deadline relationship.
This section defines the attention/reminder behavior.
## 27. MESSAGE NOTIFICATIONS
Receiving a message should be able to generate an appropriate notification.
Urgent messages should receive stronger attention treatment than ordinary communication.
However:
Urgent priority must still be communicated semantically and not through color alone.
The notification should lead the user to the relevant message.
## 28. NOTIFICATION CONTENT
A notification should be concise but understandable.
It should communicate enough context for the user to know what happened.
Examples:
"You were assigned a task."
"Member X changed Task Y to Completed."
"Task Y is due tomorrow."
"You received an urgent message."
Avoid notifications that merely say:
"Something changed."
when useful context can safely be provided.
## 29. NOTIFICATION READ STATE
Notifications support read/unread state.
Unread notifications should contribute to the notification indicator.
The user should be able to distinguish unread notifications from previously seen/read ones.
The platform must support:
"Mark all as read."
Do not confuse:
- notification read state,
- and message read state.
A message and its related notification are distinct concepts.
## 30. NOTIFICATION DEEP LINKS
Selecting a notification should take the user directly to the relevant accessible context.
Examples:
Task notification
→ Task Details.
Message notification
→ Message.
Reminder about a task
→ Relevant Task.
The destination must still perform normal permission checks.
A notification must never become a mechanism for bypassing access restrictions.
If the user's permission changed after the notification was created, current effective access wins.
## 31. STALE OR INACCESSIBLE NOTIFICATION TARGETS
A notification may refer to something the user can no longer access.
For example:
- the user's scope changed,
- the resource became unavailable,
- the resource was archived,
- the user's permission was removed.
Do not expose restricted information merely because an older notification exists.
The user should receive an understandable unavailable/access-denied outcome where appropriate.
## 32. NOTIFICATION VOLUME
Notifications should support operational awareness without turning every minor platform action into noise.
Generate notifications for events where user attention is meaningfully useful.
Do not automatically notify every person who can see a resource about every change to that resource.
Recipient relevance matters.
For example:
All team members may be able to see all team tasks.
That does NOT mean every team member must receive a notification every time any team task changes.
Visibility and notification subscription/relevance are different concepts.
## 33. REMINDERS
The platform must provide an internal reminder system.
Reminders allow authorized users to create time-based prompts for relevant organizational audiences.
The currently agreed reminder system is internal to the KORA platform.
Do not require external services for core reminder functionality.
## 34. WHO CAN CREATE REMINDERS
Reminder creation follows effective permissions.
Natural defaults may allow:
- appropriately authorized organization/PMO users,
- Administration Managers for their administration,
- Team Leaders for their team.
However, Section 1 remains authoritative.
System Admin overrides may grant or deny reminder capabilities or change scope.
Do not hardcode reminder creation solely from organizational titles.
## 35. REMINDER CONTENT
A reminder should support:
- audience,
- reminder text,
- date,
- time,
- recurrence where applicable,
- current state.
The user creating the reminder must be able to understand:
- what will be sent,
- to whom,
- and when.
## 36. REMINDER AUDIENCE
Reminder audiences must respect effective scope and permissions.
Relevant audience concepts may include:
- specific permitted users,
- team,
- administration,
- broader approved organizational audience.
Do not allow a reminder creator to target users outside the creator's effective authorized scope.
## 37. ONE-TIME REMINDERS
The platform must support reminders that occur once at a specified date and time.
Before the reminder is delivered, authorized users should be able to understand that it is scheduled.
Once delivered, its state should reflect that it has been sent/delivered according to the product's terminology.
## 38. RECURRING REMINDERS
The agreed reminder system supports recurring weekly reminders.
Example:
"Submit reports"
Every Wednesday
8:00 PM
To: Team X
Do not invent additional recurrence patterns such as:
- daily,
- monthly,
- custom cron-like schedules,
unless explicitly approved later.
The currently agreed recurrence options are:
- Once
- Weekly
## 39. REMINDER STATES
A reminder should have an understandable lifecycle.
Relevant states include concepts such as:
- Scheduled
- Sent
- Cancelled
Do not treat cancelled reminders as if they were delivered.
The exact wording may be refined, but the lifecycle distinction must remain.
## 40. EDITING REMINDERS
An authorized user may edit a reminder before it is sent.
Once a reminder has already been delivered, do not rewrite history by editing the already delivered event as though the new content had been what recipients originally received.
If future behavior supports creating a new follow-up reminder, treat it as a new action.
## 41. CANCELLING REMINDERS
An authorized user may cancel a scheduled reminder before delivery.
Cancellation should prevent the future reminder from being delivered.
The reminder should retain an understandable cancelled state where history is relevant.
Do not silently erase it if preserving the scheduling history is useful.
## 42. AUTOMATIC TASK REMINDERS
The reminder system must support automatic task-related reminders.
The agreed baseline includes:
- reminder one day before task deadline,
- reminder when a task becomes overdue.
Section 3 also establishes that the automatic pre-deadline reminder may be disabled for a task where appropriate.
Respect that task-level setting.
## 43. MANUAL TASK REMINDER
Section 3 allows an authorized user to send a manual reminder related to a task.
This reminder should reach the relevant responsible user(s) according to the task and effective permissions.
The reminder should provide enough context to identify the task.
Do not require the sender to manually recreate all task information in a separate unrelated message.
## 44. REMINDER DELIVERY
The currently agreed core delivery mechanism is internal to the KORA platform.
A due reminder should reach the user through appropriate in-platform attention surfaces.
The original product requirement establishes:
Reminder
→ user's internal communication/inbox experience
+
notification/bell attention.
Preserve this behavior conceptually.
The user should not need an external application to receive core platform reminders.
## 45. HOME INTEGRATION
Section 3 defines Home as:
"What needs my attention today?"
Communication-related information should contribute to that experience.
Relevant Home information may include:
- unread messages,
- urgent unread messages where appropriate,
- upcoming reminders,
- other personally relevant communication indicators.
Do not turn Home into a full Inbox.
Home provides concise attention summaries and links into the detailed communication areas.
## 46. COUNTERS AND BADGES
Relevant navigation items may show attention counters.
Examples include:
Inbox
→ unread message count.
Notifications
→ unread notification count.
Other communication-related counts may be introduced when meaningful.
Counters must represent a clear concept.
Do not show unexplained numbers.
The same unread concept should be calculated consistently wherever it appears.
## 47. COMMUNICATION AND ORGANIZATIONAL STRUCTURE
Communication audiences must use the organizational structure defined in Section 2.
Do not create duplicate independent lists of:
- administrations,
- teams,
- organizational roles,
- or members.
For example:
"Send to Administration X"
must refer to the actual Administration X represented in KORA's organizational structure.
"Send to Team Y"
must refer to the actual Team Y.
## 48. COMMUNICATION AND MEMBER STATUS
Audience resolution should respect relevant current member/account status.
Do not blindly send operational communication to users who are no longer active platform participants unless a specific business rule requires it.
The exact handling of unusual account/member states should remain consistent with Sections 1 and 2.
## 49. COMMUNICATION PRIVACY
Users must not gain access to private or restricted communication simply because they share an organizational unit.
For example:
The fact that all team members can see team tasks does NOT automatically mean they can see all direct messages sent between individual team members.
Message access depends on:
- sender/recipient relationship,
- audience,
- permissions,
- and relevant scope.
Do not infer message visibility from task visibility.
## 50. ROLE/GROUP TARGETING
Broadcast communication may target an organizational role/group where authorized.
For example, a permitted sender may target an appropriate role audience within an allowed scope.
Role targeting must still respect scope.
Example concept:
"Team Leaders"
could mean Team Leaders inside the sender's allowed organizational scope, not automatically every Team Leader in all of KORA.
Do not interpret role targeting as automatic organization-wide targeting.
## 51. USER-SPECIFIC PERMISSION OVERRIDES
All communication behavior must respect Section 1's user-specific overrides.
Examples:
A Member may normally lack broadcast authority.
A System Admin could explicitly grant that Member a communication capability and permitted scope.
An Administration Manager may normally be able to communicate within his administration.
A System Admin could restrict that capability.
An Event/Project Leader may normally have broad communication access.
A System Admin could explicitly remove a particular communication permission.
Do not create role-based shortcuts that bypass the override model.
## 52. MESSAGE SOURCE AND AUDIENCE CLARITY
Users should be able to understand the source and intended audience of important communication.
For example, a message should make it clear whether it was:
- sent directly to the user,
- sent to the user's team,
- sent to the user's administration,
- or sent broadly to all members.
This context is particularly useful for broadcast communication.
Do not expose sensitive recipient lists unnecessarily when audience context alone is sufficient.
## 53. SCHEDULED COMMUNICATION MANAGEMENT
Authorized users should be able to review communication they have scheduled but that has not yet been delivered.
They should be able to understand:
- what is scheduled,
- audience,
- scheduled time,
- priority,
- current state.
Appropriate edit/cancel actions should be available before delivery according to permissions.
## 54. FAILED DELIVERY / PROCESSING
If a scheduled internal communication or reminder cannot be processed successfully, the system must not silently pretend it was delivered.
The responsible authorized user should receive an understandable state or feedback indicating that the expected action did not complete.
Do not expose unnecessary technical implementation details.
## 55. CONCURRENT CHANGES
Section 1's concurrent-change principle applies.
Examples include:
- one authorized user edits a scheduled reminder while another cancels it,
- a scheduled broadcast is modified by one user while another is viewing an outdated version.
The platform should not silently overwrite newer changes.
Provide an understandable conflict/reload experience where appropriate.
## 56. MESSAGE AND REMINDER HISTORY
Communication should preserve meaningful history.
Examples:
- a sent message should remain identifiable as sent,
- a scheduled reminder that was sent should not revert to looking unsent,
- a cancelled reminder should remain distinguishable from a delivered reminder,
- a broadcast should retain its sender and audience context.
Do not rewrite past communication history merely because:
- a member later changes team,
- an organizational leader changes,
- or an organizational unit is renamed.
Historical meaning should remain understandable.
## 57. ARCHIVING VS AUDITING
Message Archive is a user-facing communication organization feature.
System Audit Log is a governance feature defined in Section 5.
They are not the same.
Archiving a message:
→ changes how the user organizes/views the message.
Auditing:
→ records meaningful system actions for governance.
Do not use one as a substitute for the other.
## 58. COMMUNICATION ACTION AUDITABILITY
Although the system-wide Audit Log is defined in Section 5, this domain must preserve meaningful actions so they can be audited.
Relevant examples include:
- sending broad broadcasts,
- scheduling broadcasts,
- cancelling scheduled communication,
- creating reminders,
- editing reminders,
- cancelling reminders,
- other high-impact communication actions.
Do not wait until Section 5 to preserve the identity of the actor or the meaning of important actions.
## 59. MOBILE COMMUNICATION EXPERIENCE
Messaging, notifications, and reminders must remain usable on mobile.
The original product concept expects:
- message lists to use the available mobile screen effectively,
- an opened message to have a focused mobile reading experience,
- notification history to be accessible as a full mobile experience,
- reminder lists to adapt to compact card-like layouts where appropriate,
- communication creation actions to remain easily reachable.
Do not force desktop-width message tables onto mobile.
## 60. RTL
All communication experiences must support Arabic RTL naturally.
This includes:
- message lists,
- message content,
- sender/recipient information,
- priorities,
- timestamps,
- audience selection,
- scheduling controls,
- notification lists,
- reminder forms,
- recurrence information.
Do not assume English/LTR interaction patterns and mirror them blindly.
## 61. ACCESSIBILITY
All Section 1 accessibility rules apply.
Communication-specific requirements include:
- unread state must not depend only on color,
- priority must not depend only on color,
- urgent communication must have understandable text/semantics,
- notification state must be accessible,
- scheduling controls must be usable,
- focus must remain visible,
- interactive message rows/items must be keyboard accessible where applicable,
- confirmation dialogs must communicate their effect clearly.
## 62. LOADING STATES
Communication experiences must provide understandable loading states for:
- Inbox,
- Sent,
- Archive,
- notifications,
- reminders,
- scheduled communication,
- audience resolution where needed.
Do not display unexplained blank areas while content is being loaded.
## 63. EMPTY STATES
Provide useful empty states.
Examples:
Inbox:
"No messages yet."
Unread:
"No unread messages."
Archive:
"No archived messages."
Notifications:
"No new notifications."
Reminders:
"No scheduled reminders."
Search:
"No messages match your search."
If the current user has permission to take a relevant next action, an appropriate action may be offered.
Do not show unauthorized creation actions in empty states.
## 64. ERROR STATES
Provide understandable error handling for:
- failed message loading,
- failed message send,
- failed broadcast,
- failed schedule operation,
- failed reminder creation,
- failed reminder cancellation,
- failed notification loading,
- failed audience resolution,
- permission changes that make an action unavailable.
Where appropriate, allow retry.
Do not display raw technical errors as the primary user-facing explanation.
## 65. BROADCAST SAFETY
Broad communication can affect many people.
The platform should reduce accidental organization-wide communication.
At minimum:
- clearly show the selected audience,
- show recipient count for broad sends,
- clearly show priority,
- distinguish immediate send from scheduled send,
- require confirmation for organization-wide/all-member broadcasts.
Do not make "All Members" an ambiguous or easily overlooked state.
## 66. REMINDER SAFETY
Reminder creation should make timing and audience clear before saving.
The user should not accidentally create:
- a weekly reminder when intending a one-time reminder,
- a reminder for the wrong team,
- or a reminder at an unclear time.
Present recurrence and timing as explicit concepts.
## 67. NOTIFICATION SAFETY
Notifications should not reveal sensitive information to users who no longer have access.
If a user's permissions change after a notification is generated:
- current permissions control access,
- notification content should not become a loophole for restricted data.
This applies especially to:
- member-sensitive information,
- cross-team resources,
- administrative resources,
- and communication content.
## 68. WHATSAPP
Automated WhatsApp integration is NOT a core dependency of this platform.
The current business decision is:
If an appropriate official and genuinely suitable free WhatsApp integration is available in the future, it may be considered.
If not, the platform's internal communication system is sufficient.
Therefore, the platform must work fully with:
- internal messaging,
- internal notifications,
- internal reminders.
Do not design core communication in a way that requires WhatsApp to function.
Do not assume unofficial automation methods.
Do not assume that WhatsApp integration exists.
## 69. EMAIL
Email delivery is not currently required for the core communication/reminder system.
Do not assume email notification delivery.
The approved baseline is internal platform delivery.
Email may be evaluated later if explicitly requested.
## 70. EXTERNAL CHANNELS
Treat external communication channels as optional future integrations.
Core KORA communication must remain functional without:
- WhatsApp,
- email,
- SMS,
- push-notification providers,
- or other external communication services.
Do not invent external integrations.
## 71. RELATIONSHIP WITH HOME
Section 3's Home page should consume concise communication indicators.
Examples:
- unread message count,
- latest relevant messages,
- urgent message attention,
- upcoming reminders.
Home must link users into the communication system rather than duplicating the entire Inbox.
## 72. RELATIONSHIP WITH TASKS
Section 3 creates task events that this section communicates.
Relevant examples:
Task assigned
→ notification to relevant assignee(s).
Task status changed
→ notification to relevant parties.
Task due tomorrow
→ task reminder.
Task overdue
→ overdue reminder/notification.
Manual task reminder
→ reminder to relevant responsible user(s).
Do not redefine task status or task permissions here.
## 73. RELATIONSHIP WITH MEMBERS
Messages and reminders target real KORA members/accounts from Section 2.
Do not maintain a separate duplicate communication contact directory.
Member privacy and effective permissions remain relevant.
A user's ability to message someone does not automatically mean the user can administratively edit that member.
## 74. RELATIONSHIP WITH ORGANIZATION
Broadcast and reminder audiences use the real organizational structure.
Audience membership should follow the relevant current organizational context at the appropriate time.
Do not manually duplicate team membership inside communication features.
## 75. RELATIONSHIP WITH PERMISSIONS
Every communication action must respect effective access from Section 1.
Conceptually separable permissions may include:
- view Inbox,
- send direct message,
- reply,
- archive own messages,
- send broadcast,
- broadcast to team,
- broadcast to administration,
- broadcast organization-wide,
- schedule broadcast,
- create reminder,
- create recurring reminder,
- cancel reminder,
- view relevant scheduled communication.
Do not assume this exact list must be the final permission catalogue.
The important rule is that communication authority must remain granular enough to respect KORA's flexible permission model.
## 76. OUT OF SCOPE FOR THIS SECTION
Do not fully define or build:
- authentication,
- account administration,
- permission administration,
- organization management,
- member administration,
- task creation or task lifecycle,
- task analytics,
- system-wide Audit Log UI,
- recruitment/selection,
- applicant conversion,
- external WhatsApp integration,
- email integration,
- SMS integration,
- voice/video calling,
- presence indicators,
- typing indicators,
- social-media-style reactions,
- public chat rooms.
Those belong elsewhere or have not been approved.
## 77. UNRESOLVED INFORMATION
Do not invent answers for requirements that have not been finalized.
Currently unresolved or intentionally deferred:
1. Whether WhatsApp will ever be integrated.
2. Whether email will later be used as a delivery channel.
3. Whether additional reminder recurrence patterns beyond Once and Weekly will be required.
4. Whether users will eventually have configurable notification preferences.
5. Whether message attachments will be supported.
6. Whether message deletion will ever be supported.
7. Whether detailed sender-facing delivery/read receipts will be required.
8. Exact notification behavior for team-wide task assignment to avoid unnecessary notification volume.
9. Any external push-notification mechanism.
10. Any future communication features not explicitly described here.
Do not invent these behaviors.
## 78. IMPORTANT DISTINCTIONS TO PRESERVE
Never collapse these concepts:
Message ≠ Notification
Message ≠ Reminder
Notification ≠ Reminder
Scheduled Message ≠ Reminder
Inbox ≠ Notification Center
Message Read State ≠ Notification Read State
Archive ≠ Delete
Message Priority ≠ Read State
Message Priority ≠ Audience
Audience Scope ≠ Permission
Ability to View Member ≠ Ability to Message Member
Ability to Message Member ≠ Ability to Edit Member
Task Visibility ≠ Requirement to Receive Every Task Notification
Team Membership ≠ Access to Private Direct Messages
Organizational Role ≠ Fixed Communication Authority
External WhatsApp ≠ Core Communication Requirement
And preserve these critical business rules:
- KORA has a persistent internal Inbox.
- Messages support Normal, Important, and Urgent priority.
- Users can archive messages without deleting them.
- Direct messaging is supported where permitted.
- Replies are supported where permitted.
- Authorized users can send broadcasts.
- Broadcast audiences may include all members, administrations, teams, and appropriate organizational roles/groups.
- Broadcast scope follows effective permissions.
- Broad sends show recipient impact.
- Sending to all members requires explicit confirmation with recipient count.
- Broadcasts may be sent immediately or scheduled.
- Notifications provide short attention signals for meaningful platform events.
- Notifications support read/unread state and Mark All as Read.
- Notifications deep-link to the relevant accessible resource.
- Current permissions always override old notification access.
- Status changes in tasks notify relevant parties.
- Task assignment can notify responsible users.
- Tasks support a reminder one day before the deadline.
- Overdue tasks may trigger reminder/notification behavior.
- Authorized users can send manual task reminders.
- The platform supports one-time reminders.
- The platform supports weekly recurring reminders.
- Scheduled reminders may be edited or cancelled before delivery where permitted.
- Reminders are delivered through the internal platform experience.
- Home surfaces concise communication/reminder attention information.
- Core communication does not depend on WhatsApp, email, or another external service.
- System Admin user-specific permission overrides remain authoritative.
## 79. EXPECTED PRODUCT RESULT
When this section is fully represented in the product, KORA should have a coherent internal communication and attention system where:
- every user has a useful Inbox;
- received communication remains available instead of disappearing;
- users can distinguish unread and read messages;
- messages have understandable Normal, Important, and Urgent priorities;
- users can search and archive communication;
- authorized users can communicate directly with individuals;
- replies preserve useful communication context;
- authorized leadership can broadcast to valid organizational audiences;
- broadcast authority respects permissions and scope rather than only role titles;
- broad communication clearly communicates its audience and recipient impact;
- organization-wide sends require explicit confirmation;
- communication can be sent immediately or scheduled;
- notifications surface meaningful operational events;
- task assignment and task status changes create appropriate awareness;
- notification links lead directly to relevant accessible resources;
- permission changes cannot be bypassed through old notifications;
- users can distinguish message read state from notification read state;
- authorized users can create one-time and weekly reminders;
- task deadlines generate the agreed reminder behavior;
- manual task reminders are supported;
- reminders can be managed before delivery;
- Home surfaces concise unread-message and reminder information;
- organizational audiences reuse KORA's actual administrations, teams, roles, and members;
- communication respects member privacy and effective permissions;
- the system avoids unnecessary notification noise;
- and KORA can operate its internal communication workflow without depending on WhatsApp, email, SMS, or another external messaging service.
Do not simplify this domain into either a generic chat application or a generic notification feed.
KORA needs a structured internal communication system that combines persistent messages, controlled organizational broadcasts, event-driven notifications, and scheduled reminders while respecting organizational scope and the flexible permission model established in Section 1.
# SECTION 5 — GOVERNANCE, AUDIT & SELECTION PLATFORM INTEGRATION
You are defining the fifth and final functional domain of the new KORA internal operations platform.
This specification is product- and behavior-focused only.
Do not assume or prescribe:
- frontend architecture,
- backend architecture,
- APIs,
- database schemas,
- frameworks,
- libraries,
- infrastructure,
- deployment architecture,
- or implementation technologies.
Sections 1–4 already define the main KORA platform domains.
Section 1 defines:
- authentication,
- user accounts,
- organizational roles,
- System Admin,
- permissions,
- scopes,
- user-specific permission overrides,
- platform navigation,
- common states,
- responsiveness,
- RTL,
- accessibility,
- and system-level access behavior.
Section 2 defines:
- KORA's organizational structure,
- Event/Project leadership,
- Project Management Office,
- administrations,
- teams,
- members,
- member administration,
- member privacy,
- member profiles,
- and member import.
Section 3 defines:
- tasks,
- task assignment,
- self-created tasks,
- multiple assignees,
- team-wide tasks,
- PMO-originated tasks,
- task lifecycle,
- task activity,
- Home,
- My Tasks,
- team and administration workspaces,
- and operational analytics.
Section 4 defines:
- internal messaging,
- Inbox,
- broadcasts,
- notifications,
- reminders,
- scheduling,
- and communication-related attention behavior.
Do not redefine or weaken those rules here.
This section defines:
- platform-wide governance,
- system Audit Log,
- audit visibility,
- administrative safety,
- historical integrity,
- sensitive-operation traceability,
- and integration/navigation between the new KORA platform and the existing KORA recruitment/selection platform.
Preserve every business rule below.
## 1. CORE PURPOSE
The purpose of this section is to ensure that KORA's platform remains understandable, accountable, and safe as multiple users perform operational and administrative actions.
The platform must make it possible for authorized administrators to answer questions such as:
- Who performed an important action?
- What did they do?
- When did they do it?
- What resource was affected?
- What changed?
- What organizational context did the action belong to?
- Was a sensitive permission changed?
- Was a member moved?
- Was a task status changed?
- Was an organizational unit changed?
- Was a broad communication sent?
- Was an import performed?
- Was a system setting changed?
This section also defines how the new KORA operations platform relates to the already existing recruitment/selection platform.
The recruitment system must remain a separate existing product rather than being unnecessarily rebuilt inside the new platform.
## 2. GOVERNANCE PRINCIPLE
Important platform actions must be attributable.
The platform should not allow sensitive operational or administrative changes to become untraceable.
This does not mean every trivial interaction must appear in a human-facing Audit Log.
Audit should focus on actions that are meaningful for:
- accountability,
- security,
- administration,
- organizational history,
- troubleshooting,
- and operational governance.
## 3. AUDIT LOG
The platform must provide a system-wide Audit Log.
The Audit Log is a governance record of meaningful actions performed across the KORA platform.
It is different from:
- task activity history,
- message archive,
- notification history,
- reminder history,
- and ordinary page history.
Those domain-specific histories serve operational purposes.
The Audit Log provides cross-platform administrative traceability.
## 4. AUDIT ACCESS
Audit Log access is sensitive.
It must follow the effective permission model established in Section 1.
Do not assume that every organizational leader automatically has access to the Audit Log.
System Admin should have appropriate administrative audit capability.
Other users may only receive Audit Log access if their effective permissions explicitly allow it.
Because System Admin controls permissions, Audit Log visibility may also be granted or restricted through the established permission system.
Do not expose Audit Log information merely because a user has access to the underlying operational resource.
For example:
Ability to view a task
does not automatically mean
ability to inspect the system-wide Audit Log for that task.
## 5. AUDIT EVENT INFORMATION
A meaningful audit event should preserve enough information to answer:
- When did the action occur?
- Who performed it?
- What action occurred?
- What resource/entity was affected?
- What changed?
- What relevant organizational/system context applied?
Where useful and appropriate, the Audit Log should support concepts such as:
- timestamp,
- actor,
- action,
- target/resource,
- organizational context,
- change summary,
- before/after information,
- and relevant result/status.
Do not expose sensitive values unnecessarily merely because an action is audited.
Auditability does not override privacy.
## 6. ACTOR
Every audited user action must identify the actor responsible for it.
The actor should refer to the actual platform user who performed the action.
Do not replace meaningful actor identity with vague labels such as:
"System User"
when a real signed-in user performed the action.
Where an action genuinely occurs automatically because of platform behavior, it should be distinguishable from a manually performed user action.
## 7. TIMESTAMP
Audited events must preserve when they occurred.
The timestamp should make event ordering understandable.
Historical audit information must not be rewritten merely because:
- a member changes team,
- a user's role changes,
- an organizational unit is renamed,
- or leadership changes later.
## 8. TARGET / RESOURCE
An audit event should identify what was affected.
Examples include:
- user account,
- permission,
- member,
- administration,
- team,
- task,
- message/broadcast,
- reminder,
- import,
- system setting.
Where appropriate, the user viewing the Audit Log should be able to understand or navigate to the relevant currently accessible resource.
Current permissions still apply.
Audit must not become a route for bypassing access restrictions.
## 9. CHANGE SUMMARY
For meaningful changes, the Audit Log should communicate what changed.
Examples:
Role changed:
Member → Team Leader
Member moved:
Team A → Team B
Task status:
In Progress → Completed
Permission:
Denied → Granted
Team:
Administration A → Administration B
The exact level of before/after detail depends on the sensitivity and usefulness of the information.
Do not record secrets or unnecessary sensitive information merely to create a detailed audit entry.
## 10. AUTHENTICATION AND ACCOUNT AUDIT
Relevant account/security actions should be auditable.
Examples may include:
- account creation,
- account disablement,
- account reactivation where supported,
- administrative password reset,
- significant account access changes,
- sign-out-all-sessions action where relevant,
- other sensitive account administration actions.
Do not store plaintext passwords or temporary passwords in audit records.
Never expose password values through Audit Log.
## 11. PERMISSION CHANGE AUDIT
Permission changes are among the most sensitive actions in the platform.
Section 1 establishes that System Admin alone manages permissions.
The platform must preserve meaningful audit history for:
- role default permission changes,
- user-specific permission grants,
- user-specific permission denials,
- scope expansion,
- scope restriction,
- other significant access-control changes.
The record should make it possible to understand:
- which Admin made the change,
- which user/role was affected,
- what access changed,
- and when.
## 12. PERMISSION HISTORY MUST SURVIVE LATER CHANGES
If a user's permissions are later changed again, the earlier permission-change history must remain understandable.
Do not overwrite the historical record to make it appear that the user always had the current permission state.
## 13. SYSTEM ADMIN ACCOUNTABILITY
System Admin has powerful authority, including the ability to:
- manage accounts,
- manage permissions,
- override normal role access,
- expand user scope,
- restrict user scope,
- manage members,
- perform sensitive administrative operations.
Therefore, System Admin actions must not be exempt from auditing merely because the actor is an administrator.
Administrative power increases the importance of traceability.
## 14. MEMBER AUDIT
Section 2 establishes that System Admin alone administratively manages KORA members.
Relevant member actions should be auditable.
Examples include:
- member created,
- member information changed,
- member organizational role changed,
- member moved to another team,
- member moved to another administration,
- member deactivated,
- member reactivated where supported,
- member removed according to any future approved policy,
- member import performed,
- significant member-account relationship changes.
Do not expose sensitive member information unnecessarily in general audit summaries.
## 15. ORGANIZATION AUDIT
Relevant organizational structure changes should be auditable.
Examples include:
- administration created,
- administration renamed,
- administration activated/deactivated,
- Administration Manager changed,
- team created,
- team renamed,
- team moved to another administration,
- team activated/deactivated,
- Team Leader assignment changed.
Historical audit records should preserve the meaning of what happened at the time.
## 16. TASK AUDIT
Section 3 already defines task-specific activity/history.
The system-wide Audit Log should also capture meaningful task actions where appropriate.
Examples include:
- task created,
- task edited,
- assignment changed,
- deadline changed,
- priority changed,
- status changed,
- note added where appropriate,
- task archived,
- task restored.
Do not assume that every tiny display-level interaction requires an Audit Log entry.
Focus on meaningful changes.
## 17. TASK HISTORY VS AUDIT LOG
Preserve this distinction:
Task Activity History
= operational history shown in the context of the task.
System Audit Log
= administrative/governance history across the platform.
Some actions may appear in both because they serve different purposes.
Do not remove useful task activity merely because the same event exists in Audit Log.
Do not use Task Activity as a substitute for the system-wide Audit Log.
## 18. COMMUNICATION AUDIT
Relevant communication actions should be auditable, especially broad-impact actions.
Examples include:
- broad broadcast sent,
- organization-wide broadcast sent,
- scheduled broadcast created,
- scheduled broadcast changed,
- scheduled broadcast cancelled,
- significant communication administration actions.
Do not assume that the full private content of every direct message must be exposed in the system-wide Audit Log.
Audit should preserve accountability without unnecessarily compromising private communication.
## 19. REMINDER AUDIT
Relevant reminder actions may be audited.
Examples include:
- reminder created,
- recurring reminder created,
- reminder edited,
- reminder cancelled,
- broad reminder targeting changed.
Automatic reminder delivery may be represented appropriately where useful for operational troubleshooting.
Do not create excessive human-facing audit noise from every routine automated process unless it provides real governance value.
## 20. IMPORT AUDIT
Member import is a high-impact administrative operation.
The platform should preserve audit information such as:
- who initiated/confirmed the import,
- when it occurred,
- relevant import type,
- high-level outcome,
- counts of records added/updated/failed where appropriate.
Do not store an entire sensitive source spreadsheet inside a general Audit Log merely for convenience.
Detailed import results may remain associated with the import operation where appropriate.
## 21. SYSTEM SETTINGS AUDIT
Meaningful system setting changes should be auditable.
Examples include settings that affect:
- platform behavior,
- access,
- recruitment-related configuration,
- or other organization-wide behavior.
The audit entry should make it possible to understand:
- what setting changed,
- who changed it,
- and when.
## 22. AUDIT SEARCH AND FILTERING
Authorized Audit Log users should be able to locate relevant events efficiently.
Useful filters include:
- action/operation type,
- actor,
- administration/team context where applicable,
- date/time period.
Additional relevant filters may be introduced when useful.
Do not create meaningless filters merely to increase feature count.
## 23. AUDIT DETAILS
An audit list should provide concise event summaries.
A detailed audit view should provide additional context where appropriate.
For example:
Summary:
"Member moved to another team"
Details:
- Actor
- Member
- Previous team
- New team
- Timestamp
- relevant organizational context
Sensitive details must still respect privacy and permissions.
## 24. AUDIT EXPORT
Authorized users should be able to export Audit Log information where permitted.
Exported information must respect:
- the user's effective access,
- applicable filters,
- and privacy requirements.
Export capability must not become a way to bypass restrictions that apply inside the platform.
## 25. AUDIT IMMUTABILITY PRINCIPLE
Ordinary users must not be able to edit historical Audit Log entries.
An audit history loses its governance value if users can rewrite past actions.
Do not provide ordinary edit/delete actions for audit events.
Any exceptional retention or administrative maintenance policy would require an explicit future requirement.
Do not invent one.
## 26. HISTORICAL IDENTITY
Audit history should preserve enough historical identity to remain understandable even after organizational changes.
Examples:
If a member later moves teams:
an old task or audit event should not falsely imply that the action originally occurred in the new team.
If a team is renamed:
historical records should remain interpretable.
If a user changes role:
old actions should still identify who performed them at the time.
Do not rewrite history based solely on current organizational state.
## 27. HISTORICAL ORGANIZATIONAL INTEGRITY
The same principle applies across the platform.
Changes to:
- administrations,
- teams,
- members,
- roles,
- leadership,
- permissions
must not make older records meaningless.
Historical information should preserve appropriate context.
This does not necessarily require exposing every historical attribute everywhere.
It requires that past actions remain accurately interpretable.
## 28. ADMINISTRATIVE SAFETY
Sensitive administrative actions should include appropriate safeguards.
The purpose is to reduce accidental high-impact changes without making routine work unnecessarily slow.
Examples of actions that may require stronger confirmation include:
- disabling a user account,
- deactivating a member,
- moving a member where it has organizational consequences,
- deactivating an administration,
- deactivating a team,
- moving a team between administrations,
- changing sensitive permissions,
- restricting high-level access,
- broad imports,
- organization-wide broadcasts,
- other high-impact system changes.
The confirmation should explain the consequence.
Do not use meaningless generic confirmation everywhere.
## 29. PERMISSION CHANGE SAFETY
Because System Admin can remove permissions even from organization-wide leaders, permission administration must make the impact understandable.
Before a high-impact access change is finalized, the Admin should be able to understand:
- who is affected,
- what capability is being granted or removed,
- what scope is changing,
- and whether the change significantly affects platform access.
Do not silently apply ambiguous permission changes.
## 30. PREVENTING ADMINISTRATIVE LOCKOUT
The platform must avoid obvious administrative lockout states.
For example, administrative actions should not accidentally leave the platform with no authorized administrative path for managing critical system access.
The exact safety rule depends on the final Admin/account model.
Do not invent unnecessary hierarchy restrictions, but preserve the principle:
Critical platform administration must not become impossible because of an accidental configuration change.
If a proposed action would create an unsafe administrative state, the platform should block it or require an appropriate safe resolution.
## 31. DESTRUCTIVE ACTION PRINCIPLE
The platform should prefer non-destructive lifecycle actions where historical information matters.
Examples already established in earlier sections:
- archive tasks instead of normally deleting them,
- deactivate organizational units instead of erasing them,
- deactivate members rather than automatically destroying historical membership data,
- archive messages rather than treating archive as deletion.
Do not introduce destructive deletion casually.
If permanent deletion is later required for a specific entity, define it explicitly with appropriate rules.
## 32. CONCURRENT ADMINISTRATIVE CHANGES
Section 1's concurrent-change principle applies to governance and administration.
If one authorized user changes an item while another user is acting on stale information, the platform must not silently overwrite the newer state.
Examples:
- two Admins modifying the same user's permissions,
- one Admin moving a member while another edits the member,
- one user moving a team while another changes its leadership,
- one authorized user cancelling a scheduled communication while another edits it.
The affected user should receive a clear conflict/update message and an appropriate way to review the latest state.
## 33. CURRENT ACCESS ALWAYS WINS
Historical records may describe past access, but current permissions control what the user may access now.
Examples:
A user previously had access to Team A and generated an event there.
Later, access is removed.
The historical event may still exist, but the user must not use old links, notifications, or historical references to bypass current restrictions.
Likewise:
Audit visibility does not automatically grant visibility into every referenced sensitive resource.
## 34. RECRUITMENT/SELECTION STRATEGY
KORA already has an existing recruitment/selection platform.
The new KORA internal operations platform must NOT unnecessarily rebuild that system.
The agreed decision is:
Keep the existing recruitment/selection platform as a separate platform.
The new platform provides a clear entry point to it.
Do not rebuild the existing recruitment feature set inside this project merely to make everything appear in one codebase/product surface.
## 35. RECRUITMENT ENTRY POINT
The new platform should contain a navigation option equivalent to:
"Recruitment & Selection"
This option takes the authorized user to the existing recruitment/selection platform.
The transition should be clear enough that users understand they are opening the recruitment system.
The exact visual treatment may indicate that the destination is a separate platform/external destination.
Do not duplicate the recruitment pages inside the new platform.
## 36. RECRUITMENT ACCESS VISIBILITY
The Recruitment & Selection entry point should respect effective permissions.
Not every KORA platform user must automatically see or access recruitment simply because the recruitment platform exists.
Visibility of the navigation entry should follow the relevant access configuration.
Section 1's permission model remains authoritative.
Do not hardcode recruitment navigation solely by organizational role if Admin overrides are intended to control access.
## 37. EXISTING RECRUITMENT FEATURES REMAIN EXISTING
Do NOT rebuild the existing recruitment platform's features in the new platform.
This includes, among other existing recruitment capabilities:
- applicant listing,
- applicant details,
- application responses,
- applicant preferences,
- PMO decisions,
- team decisions,
- viewer requests,
- objections,
- deputy/team suggestions where they exist in the current recruitment system,
- accepted-applicant lists,
- applicant import,
- recruitment-specific queues,
- recruitment-specific decision logic.
These remain the responsibility of the existing recruitment platform.
## 38. DO NOT REINTERPRET THE EXISTING RECRUITMENT SYSTEM
The new platform project should not silently redesign recruitment business rules merely because the internal operations platform uses a newer organizational model.
The existing recruitment platform continues to operate according to its existing approved logic unless a separate recruitment project explicitly changes it.
Do not use this section as permission to refactor or rewrite the recruitment system.
## 39. RECRUITMENT AND NEW ORGANIZATIONAL TERMINOLOGY
The new KORA platform uses the newer organizational concepts such as:
- Project Management Office,
- administrations,
- teams,
- Administration Manager,
- Team Leader.
The existing recruitment platform may contain terminology or behavior inherited from the older system.
Do not automatically rewrite recruitment terminology or logic as part of this new-platform section.
Any such migration should be handled as a deliberate separate change if requested.
## 40. FUTURE APPLICANT-TO-MEMBER INTEGRATION
There is an important future lifecycle connection between the two platforms:
Applicant
→ recruitment process
→ final acceptance
→ KORA Member
The desired future outcome is that a finally accepted applicant can eventually be converted/onboarded into the main KORA Member system without unnecessary manual re-entry.
However:
This integration is NOT currently defined in enough technical detail to implement automatically.
Do not invent an integration contract.
## 41. MEMBER CREATION AUTHORITY STILL APPLIES
Section 2 establishes:
System Admin is the only authority responsible for administratively adding and managing members in the main KORA platform.
That rule still applies to recruitment integration.
A final acceptance decision in the recruitment platform does not automatically grant Team Leaders, PMO users, or other recruitment users authority to administratively create or modify main-platform member records.
The future Applicant → Member process must respect the main platform's member-management authority.
## 42. FUTURE CONVERSION GOAL
When future integration is explicitly designed, the desired product goal is to reduce duplicate data entry.
A finally accepted applicant may eventually provide data for creation/onboarding of a KORA member.
Relevant information may include approved applicant/member information.
However, do not define:
- exact transferred fields,
- automatic vs manual confirmation,
- API behavior,
- synchronization direction,
- identity matching,
- failure recovery,
- or duplicate handling
until the actual integration requirements and contracts are available.
## 43. NO INVENTED API CONTRACT
Do not invent:
- endpoints,
- request bodies,
- response bodies,
- tokens,
- authentication mechanisms between systems,
- webhooks,
- shared database assumptions,
- synchronization jobs,
- or other technical integration contracts.
The two-platform relationship is currently a product requirement, not an approved technical contract.
## 44. NO SHARED-DATABASE ASSUMPTION
Do not assume the new KORA platform and existing recruitment platform share the same data storage.
Do not assume they do not.
That is an implementation/architecture decision that has not been defined here.
The product requirement is simply:
- recruitment remains operational as its existing platform,
- the new platform links users to it,
- and future accepted-applicant-to-member integration should remain possible.
## 45. RECRUITMENT SETTINGS
A previously agreed configurable business setting concerns what applicants select during recruitment:
- Administration
or
- Team.
This choice should be administratively configurable rather than permanently hardcoded.
Section 1 establishes the existence of centrally managed system settings.
Because the recruitment platform remains separate, do not assume how this setting is technically communicated to the recruitment system.
Preserve the product requirement without inventing integration mechanics.
## 46. RECRUITMENT ACCESS AND PERMISSION CHANGES
If a user's access to Recruitment & Selection is removed in the new platform, the new platform must stop presenting that user with an authorized recruitment entry point.
However, because the recruitment platform is separate, do not assume that changing permissions in the new platform automatically changes credentials or authorization inside the existing recruitment platform unless such integration is explicitly implemented later.
Do not pretend cross-platform authorization synchronization exists when it has not been defined.
## 47. CROSS-PLATFORM USER EXPERIENCE
Although recruitment remains separate, the transition should not feel accidental.
The user should understand:
- that Recruitment & Selection is part of KORA's broader operational ecosystem,
- that it opens the existing recruitment platform,
- and that returning to the main operations platform is a separate navigation context if applicable.
Do not recreate recruitment pages merely to make the transition visually seamless.
Functional separation is acceptable.
## 48. RECRUITMENT DATA ON MAIN PLATFORM
Do not automatically surface recruitment applicant data throughout the main KORA operations platform.
Applicant information belongs to the recruitment system until an approved integration/use case says otherwise.
Once a person becomes an official KORA Member, the main platform uses the Member model defined in Section 2.
Do not treat every applicant as a main-platform member.
## 49. MEMBER VS APPLICANT
Preserve the distinction:
Applicant
= a person participating in the recruitment/selection process.
Member
= an official KORA member represented in the main operations platform.
Accepted Applicant
does not automatically equal
fully provisioned Member
until the approved member onboarding/conversion process occurs.
## 50. RECRUITMENT AUDIT SEPARATION
The existing recruitment platform may have its own Audit Log or historical decision tracking.
Do not automatically duplicate all recruitment audit events inside the new platform's Audit Log.
The new platform's Audit Log governs actions occurring in the new KORA platform.
If future cross-platform integration requires shared audit events, define that deliberately at that time.
## 51. FUTURE INTEGRATION AUDIT
When Applicant → Member integration is eventually introduced, the conversion/onboarding action should be auditable in an appropriate way.
It should eventually be possible to understand:
- who initiated/confirmed the conversion where applicable,
- which applicant/member relationship was created,
- when it happened,
- and the result.
Do not define technical details before the integration itself is defined.
## 52. SYSTEM-WIDE AUDIT COVERAGE
Taken together, the Audit Log should be capable of covering meaningful events from Sections 1–4.
This includes appropriate events from:
SECTION 1
- accounts,
- permissions,
- scopes,
- system settings.
SECTION 2
- organization,
- members,
- member import.
SECTION 3
- tasks,
- assignments,
- task status,
- task archive/restore,
- meaningful task changes.
SECTION 4
- broad communication,
- scheduled communication,
- reminders,
- other meaningful communication administration.
Do not require every possible event to be displayed identically.
Audit detail should reflect the type and importance of the action.
## 53. AUDIT FILTERS AND ORGANIZATIONAL CONTEXT
Where an audit event belongs to an organizational context, authorized users should be able to filter or understand that context.
Examples:
- Administration A,
- Team B,
- PMO,
- organization-wide.
However, do not force an organizational context onto actions that are genuinely system-wide or account-level.
## 54. AUDIT AND USER-SPECIFIC OVERRIDES
Permission overrides must be especially clear in audit history.
Example:
System Admin X
granted
Member Y
permission Z
outside normal Team Y scope.
Or:
System Admin X
denied
Event/Project Leader Y
permission Z.
The system should preserve the fact that the effective access changed through an explicit override.
Do not make exceptional access indistinguishable from default role access when reviewing administrative history.
## 55. SENSITIVE AUDIT INFORMATION
Audit must balance traceability with privacy.
Do not place sensitive content into Audit Log merely because the system technically has access to it.
Examples of information that should not be casually exposed in audit entries include:
- passwords,
- temporary passwords,
- authentication secrets,
- unnecessary private message content,
- unnecessary full member personal information.
Audit the action, not every secret associated with the action.
## 56. AUDIT EMPTY, LOADING, AND ERROR STATES
Audit experiences must account for:
Loading
- audit information is being retrieved.
Empty
- no events match the current filters,
- or no relevant events exist.
Error
- audit information could not be loaded,
- export failed,
- or another known operation failed.
Do not present an empty audit table as if it necessarily means the system has never recorded any activity when filters may be responsible.
## 57. AUDIT MOBILE EXPERIENCE
The original product concept identifies Audit Log as a workflow that is preferably used on a computer because of its density.
Preserve desktop optimization for complex audit investigation.
However, mobile access should fail gracefully rather than presenting an unusable broken layout if mobile access is allowed.
The product may communicate that detailed audit investigation is best performed on desktop.
## 58. RTL AND ACCESSIBILITY
All Section 1 RTL and accessibility rules apply.
Governance-specific requirements include:
- change summaries must remain understandable in Arabic RTL,
- before/after values must not become directionally ambiguous,
- status and severity must not rely only on color,
- filters must be accessible,
- audit detail navigation must be keyboard usable where applicable,
- confirmation dialogs must clearly explain consequences.
## 59. ADMINISTRATIVE CONFIRMATION LANGUAGE
High-impact confirmation should communicate:
- what will happen,
- what/who will be affected,
- and whether the action can be reversed where relevant.
For example:
Do not use only:
"Are you sure?"
Prefer the conceptual behavior:
"You are about to deactivate this member. The member will lose active membership access, while historical records will remain."
Exact wording may vary by action.
## 60. FAILURE MUST NOT LOOK LIKE SUCCESS
For sensitive operations, a failed action must not leave the user believing the change succeeded.
Examples:
- permission update failed,
- member move failed,
- import confirmation failed,
- broadcast scheduling failed,
- audit export failed.
The user should receive clear outcome feedback.
Do not silently swallow failures.
## 61. PARTIAL SUCCESS
Bulk/high-impact operations may sometimes have mixed outcomes.
Where an operation can legitimately partially succeed, the product should clearly communicate:
- what succeeded,
- what failed,
- and what requires attention.
Do not present a mixed result as complete success.
Do not invent partial-success behavior for operations that should instead be atomic; that depends on the specific operation.
## 62. GOVERNANCE DOES NOT REPLACE PERMISSIONS
Audit and governance do not grant authority.
Being able to inspect an action does not automatically grant the ability to perform that action.
Likewise:
Being able to perform an action does not automatically grant access to the full Audit Log.
Keep:
- operational permission,
- audit permission,
- and administrative permission
conceptually distinct.
## 63. GOVERNANCE DOES NOT REPLACE DOMAIN HISTORY
Do not remove useful histories from other sections simply because a central Audit Log exists.
Examples:
Task Details still needs task activity/history.
Messaging still needs Sent/Archive.
Reminders still need their own state/history.
The Audit Log supplements these experiences for governance.
## 64. OUT OF SCOPE FOR THIS SECTION
Do not rebuild or redefine:
- authentication flows,
- normal account management behavior,
- organization management workflows,
- member directory,
- member import workflow,
- task creation,
- task assignment,
- task lifecycle,
- task analytics,
- messaging,
- notification-center behavior,
- reminder creation behavior,
- recruitment applicant pages,
- recruitment decisions,
- recruitment queues,
- recruitment imports,
- recruitment objections,
- recruitment-specific business logic.
Those are defined elsewhere or already exist in the recruitment platform.
This section governs/audits the new platform and defines the boundary with recruitment.
## 65. UNRESOLVED INFORMATION
Do not invent answers for information that has not yet been finalized.
Currently unresolved or intentionally deferred:
1. The exact technical relationship between the new platform and the existing recruitment platform.
2. Whether both platforms will eventually share authentication.
3. Whether cross-platform authorization synchronization will exist.
4. The Applicant → Member integration contract.
5. The exact applicant fields transferred during future conversion.
6. Whether conversion is initiated from recruitment, the main platform, or another controlled flow.
7. Duplicate/member matching rules during future applicant conversion.
8. Failure/retry behavior for future cross-platform conversion.
9. The final audit retention policy.
10. Any exceptional ability to remove audit records.
11. Exact export formats for Audit Log.
12. Exact permanent deletion policies for entities whose deletion remains unresolved elsewhere.
13. The final administrative lockout prevention rule based on the eventual account/Admin configuration.
Do not invent these decisions.
## 66. IMPORTANT DISTINCTIONS TO PRESERVE
Never collapse these concepts:
Audit Log ≠ Task Activity History
Audit Log ≠ Message Archive
Audit Log ≠ Notification History
Audit Log ≠ Permission
Audit Visibility ≠ Operational Authority
System Admin Authority ≠ Exemption From Audit
Archive ≠ Delete
Deactivate ≠ Erase History
Current Organizational State ≠ Historical Organizational State
Current Permission ≠ Historical Permission
Applicant ≠ Member
Accepted Applicant ≠ Automatically Provisioned Member
Recruitment Platform ≠ Main KORA Operations Platform
Recruitment Entry Point ≠ Recruitment Reimplementation
Product Integration Goal ≠ Approved Technical API Contract
Main-Platform Permission ≠ Automatically Synchronized Recruitment Permission
And preserve these critical business rules:
- meaningful sensitive actions must be traceable;
- System Admin actions must also be auditable;
- permission grants, denials, and scope overrides must be auditable;
- member administration must be auditable;
- organization changes must be auditable;
- meaningful task changes must be auditable;
- broad communication and reminder administration should be auditable where appropriate;
- member imports must be auditable;
- meaningful system setting changes must be auditable;
- audit history must not be casually editable;
- sensitive secrets must not be exposed through audit;
- historical context must remain understandable after later organizational changes;
- current permissions always control current access;
- high-impact administrative actions require appropriate safeguards;
- destructive deletion should not be introduced casually;
- the existing recruitment/selection platform remains separate;
- the new platform provides an authorized entry point to recruitment;
- existing recruitment features must not be rebuilt as part of this project;
- future Applicant → Member integration remains desirable;
- System Admin remains the authority for creating/managing the resulting main-platform member;
- no integration API or synchronization behavior may be invented before it is actually defined.
## 67. EXPECTED PRODUCT RESULT
When this section is fully represented in the product, KORA should have a governance layer where:
- authorized administrators can understand meaningful actions across the platform;
- important actions identify who performed them and when;
- sensitive permission changes are traceable;
- user-specific access overrides remain understandable historically;
- powerful System Admin actions are accountable;
- member and organizational changes preserve historical meaning;
- meaningful task actions can participate in system-wide auditing without replacing task-specific activity history;
- broad communication and reminder administration can be traced appropriately;
- imports and system-setting changes can be investigated;
- audit information can be searched and filtered;
- authorized users can inspect event details and export appropriate audit information;
- audit history cannot be casually rewritten;
- sensitive secrets are protected from unnecessary audit exposure;
- dangerous administrative actions communicate their impact before execution;
- accidental administrative lockout is guarded against;
- concurrent administrative changes do not silently overwrite newer state;
- failures are clearly distinguished from successful actions;
- the new KORA operations platform remains focused on internal organization and operations;
- Recruitment & Selection remains a separate existing platform;
- authorized users can reach that platform through a clear KORA navigation entry point;
- the existing recruitment system is not unnecessarily rebuilt;
- Applicant and Member remain distinct concepts;
- and the platform remains ready for a future controlled Applicant → Member integration without inventing its technical contract prematurely.
Do not turn this section into a generic logging feature.
Its purpose is to preserve accountability, historical integrity, administrative safety, and a clean boundary between KORA's new internal operations platform and the existing recruitment/selection system.

---

# IMPLEMENTATION ALIGNMENT ADDENDUM — 2026-10-12

**Purpose:** This addendum resolves what can be resolved from the supplied `API_CONTRACT(2).md` (backend Milestone 8B, 2026-10-12), without rewriting the five product domains. It is written for a frontend implementer. **An API contract is evidence of implemented behavior, not approval to erase an unmet product requirement.** The detailed contract remains authoritative for exact request/response fields and endpoint behavior. The frontend should never fabricate unsupported operations, show false success, or treat mocks as live data.

## A. Decisions and clarification of authority

1. **System Admin can grant permissions.** System Admin is a separate, explicitly granted authority, not an organizational role. An Admin may grant/revoke other System Admin grants, manage role defaults, and grant/deny user permissions at organizational units, including for senior leaders. **The last active System Admin cannot be revoked or deactivated.** The original phrase “only Admin manages members and permissions” means **only an account with an active System Admin grant may perform these actions**. A current Admin can grant that authority to another account; it is not permanently limited to one person. Merely receiving an operational permission override is **not** equivalent to receiving System Admin authority.
2. **System Admin does not automatically have operational access.** Admin routes require the active System Admin grant. Tasks, organization operations, announcements and calendar use separate scoped operational permissions. If an Admin needs operational capabilities, an explicit scoped override can grant them (including to the Admin's own account).
3. **Effective permissions:** for a given permission and unit, the nearest applicable unit override wins; at the same unit, deny wins over grant. If no override applies, the current active Member role default applies at its role unit and descendants; otherwise deny. An account's deactivation removes access. Permission changes must not be simulated with frontend-only toggles.
4. **Member administration** (provision, profile replacement, move, role change, deactivate/reactivate, password reset) is available only under `/api/v1/admin/members`. Admin authority may be granted to additional accounts by another Admin; ordinary role/default/operational overrides cannot grant these admin routes.
5. **Recruitment setting owner:** the earlier product decision described PMO leadership controlling whether applicants choose an Administration or Team. The consolidated text instead says administratively configurable. No corresponding API exists, and the separate recruitment platform is not synchronized. **Do not claim this setting works or assign an effective controller until the cross-platform mechanism and permission ownership are explicitly approved.**
6. **Deleted task comments:** the author alone may edit/delete their own comment through the current API. Deletion is soft; `body` becomes `null`. History responses redact all earlier comment text, including `previous_body`, while preserving event type, actor, time and comment ID. The audit log stores comment action metadata, never comment body. The frontend must not show deleted text from cached history after deletion.

## B. Current API coverage by product domain

| Domain | Available now in contract | Product requirement still missing or different |
|---|---|---|
| Core & Access | Username/password sign-in, sessions, CSRF, password change, sign-out/all, current account and effective access, admin role defaults/overrides/System Admin grants | No general account listing/create/reset API independent of Member provisioning; no role-based arbitrary permission catalog editor beyond eight keys; no recruitment setting API |
| Organization & Members | Admin-only Member provisioning/edit/move/role/deactivate/reactivate/reset; scoped organization unit list/create/move/archive | No Excel Member Import flow, no general member directory/profile read API for non-admin users, no unit rename/reactivate API, no dedicated public organizational directory. `GET /organization/units` lists only units with `organization.manage`, not all viewable units |
| Tasks & Workspaces | Task create/list/detail/update/status/assignees/move, one-level subtasks, comments/history, weekly series | No task archive/restore endpoint; no team-wide assignment mode; no dedicated Home/My Tasks/team workspace/dashboard/analytics endpoints; no task reminder API; current task lifecycle and priority differ from old product text |
| Communication | Published/draft/withdrawn announcements with direct recipients, versions and read state; in-app notifications and preferences | No direct message/reply/Inbox/Sent/Archive API; no scheduled broadcast, reminder, recurring reminder, or deadline-triggered reminder API. Announcements are **not** equivalent to private messaging |
| Calendar | Events/meetings, invitees, cancellation/history, unified calendar with personal task due dates | Calendar is implemented although omitted from the original five-domain product scope. Expose it only as its actual contract supports; no RSVP, recurrence, attendance, attachments or comments |
| Governance & Recruitment | Admin-only audit list/detail, permission and other action records | No audit export API; no recruitment integration API; existing recruitment is a separate site and should only be linked when its verified URL and access expectations are supplied |

## C. Critical differences that frontend must follow now

### C1. Session and request handling

- Base path `/api/v1`; JSON; UUID identifiers; UTC response timestamps. Date/time inputs require an explicit timezone offset. Do not submit naive local timestamps.
- Authentication is **cookie-based**, not a bearer token returned to the client. `kora_session` is HttpOnly (`Path=/api`); `kora_csrf` is readable by JavaScript. The sign-in and change-password responses also return `csrf_token`. Every authenticated non-GET/HEAD/OPTIONS request needs `X-CSRF-Token`, except sign-in. Requests must use the deployed **same-origin** API path; the backend does not configure CORS.
- Sessions expire after 8 hours idle or 7 days absolute. Temporary passwords expire after 7 days; while temporary, only sign-out, sign-out-all, `/auth/me` and change-password work. Successful change-password revokes all old sessions and issues a new session/CSRF pair. Five failed sign-ins per normalized username in 15 minutes cause a 15-minute lockout (429 with `Retry-After`).
- Error body is `{ "detail": ... }`; 422 `detail` may be a string or a list of validation issues. There are no machine-readable error codes. Distinguish 401 (session), 403 (CSRF, temporary-password gate, admin-only, or authorization), 404, 409, 422 and 429 according to the contract. Unauthorized list items are omitted; direct forbidden item access generally returns 403, with documented exceptions.
- No `DELETE` HTTP methods exist in this contract. Most lists are **not paginated**; only audit uses `limit` and `cursor`. Do not invent generic pagination parameters.

### C2. Access catalog and Admin UI

The current catalog has **exactly eight permissions**: `organization.manage`, `task.view`, `task.create`, `task.manage`, `announcement.publish`, `announcement.manage`, `calendar.create`, `calendar.manage`. Admins can add/end role defaults, add/end unit-scoped user overrides (with required reason), inspect effective access (optionally `as_of`), and grant/revoke System Admin authority. There is no endpoint to invent new permission keys. An override has no scheduled expiration field. The UI must show real effective access rather than assuming the organizational title alone determines access.

### C3. Members and organization

- Member provisioning creates the Member, account, Team placement and role together; the temporary password is returned **once**. The Admin must be able to handle it without expecting later retrieval. Admin `PUT /members/{id}` is **full profile replacement**, not partial PATCH: omitted optional fields become null. A Team or role change uses its own POST endpoint.
- Deactivation revokes account sessions and ends current placement and role. Reactivation requires a Team and role. Team/role changes and unit moves may affect eligibility of open task assignees.
- Units support creation of Administration and Team, Team move, and archive. KORA and PMO cannot be archived. Archive is blocked by active descendants, active Members or open role assignments. There is no current unit rename or unarchive endpoint.
- The Admin member list is **not** an ordinary-user directory. Do not route non-admin members to `/admin/members` and assume the API will permit it.

### C4. Tasks — implemented behavior vs desired future behavior

- Current `TaskStatus`: `new`, `in_progress`, `completed`, `cancelled`; allowed transitions are `new -> in_progress/completed/cancelled`, `in_progress -> completed/cancelled`, and `completed/cancelled -> new` (reopen), with different permissions. The old product's `Not Completed` is **not** an API status. No required explanatory note for cancellation is enforced by this contract. The frontend must not send unsupported status values or present the older three-status model as if already implemented.
- Current `TaskPriority`: `low`, `normal`, `high`, `urgent`, and may be null; the old Normal/Important/Urgent vocabulary does not directly define API values. Avoid silently equating `high` to a product label without an explicit UX mapping.
- `due_at` is optional and must include an offset when supplied. A task is created with `new` status (not automatically `in_progress`). Current assignees are **one or more distinct active Members** within task scope. There is no `entire_team` assignment flag or all-members dynamic assignment. A single task can have multiple assignees. Members cannot be assigned outside scope simply because they are organizationally senior; authorization and assignee eligibility are distinct checks.
- The creator (if still an active Member) can administer their own task; a current assignee or scoped manager may comment; only the comment author can edit/delete. The creator/current assignee may view a task, subject to an explicit `task.view` deny override. The API does not implement the old blanket rule that every teammate can see every task automatically; access depends on `task.view`, `task.manage`, creator or current assignee.
- Subtasks are one level deep, inherit scope, and have independent status. Weekly series create up to 104 occurrences upfront and may update/move/stop only future unstarted occurrences; this is **weekly task recurrence**, not a reminder schedule. Task cancellation is not task archiving. The old archive/restore product requirement remains a gap.
- Deleted comments are returned with `body: null`; earlier edited text is redacted from task history responses after deletion. Render a neutral deleted-comment placeholder and do not reconstruct deleted text from cached activity.
- No dedicated task analytics API exists. Any permitted client-side summary must be explicitly labeled as derived from the **visible returned tasks**, not falsely claimed as organization-wide analytics. The original Completed / Non-Archived formula is a product target, not a guaranteed backend metric; there is no `archived` task state in the current API.

### C5. Announcements, notifications and calendar

- Announcements have `draft`, `published`, `withdrawn` states. Publishing requires an explicit nonempty list of distinct eligible `recipient_member_ids`; recipients are fixed at publication. Published edits create versions and can make a previously read announcement unread for its current version. `GET /announcements/{id}` marks the current version read for a recipient. Withdrawn recipients see null title/body with `content_hidden: true`. There is **no scheduled publishing** in the current API.
- Notifications support list, read, read-all, soft delete, delete-all, and **user preferences** for six categories. The actor never receives their own event notification. On read, a notification whose source is no longer accessible has `summary: null`, `redacted: true`. Do not expose cached restricted summaries. Notifications currently go to task creator and current assignees for status changes, **not automatically to Team Leaders and Administration Managers**. That original recipient rule remains a backend gap unless they are also recipients through current logic.
- Calendar supports `event` and `meeting`, invites, event cancellation and history. `GET /calendar` requires both `from` and `to` with offsets, an interval of at most 366 days, and returns accessible events plus **only personally created or assigned** open-task due dates. It is not an all-team task calendar. Calendar event recurrence, RSVP and attendance are absent.

### C6. Audit and recruitment

- Audit routes are `/api/v1/admin/audit-records` and `/api/v1/admin/audit-records/{record_id}`. They are **System Admin-only, read-only**, with newest-first cursor pagination and filters. There is no export route. Non-admin audit access via operational permission override is **not supported**. Audit records contain allowlisted metadata, not sensitive bodies/secret values, and are not backfilled before the audit migration.
- Recruitment & Selection remains separate, with **no integration API**. An authorized navigation link is the only current in-scope cross-platform experience, once the correct URL is supplied. Do not promise shared sessions, synchronized permissions, applicant conversion or working recruitment settings.

## D. Frontend scope and honest feature presentation

1. **Build against the contract, not imagined services.** For every interactive action, verify an existing documented route and supported permission. Do not present a success state without a successful response.
2. **Preserve unmet product requirements** in a visible implementation-gap checklist; do not silently remove them from the vision. If design mockups are useful, keep them clearly isolated from production data/actions and do not disguise them as integrated features.
3. **Prioritize supported flows:** sign-in/password reset via Admin/member provisioning, effective access and Admin overrides, Admin member lifecycle, supported organization operations, tasks/subtasks/weekly series/comments, announcements, notifications/preferences, calendar, and read-only Admin audit.
4. **Block or defer unsupported actions** such as Excel member import, ordinary-member directory API, team-wide task assignment, task archive/restore, task reminder scheduling, full messaging/replies, scheduled broadcasts, audit export, and applicant-to-member conversion. Do not wire fake buttons to nonexistent routes.
5. **Product decisions still needing approval:** whether to add a general member directory API, team-wide assignment semantics, a unified operational task status vocabulary, priority label mapping, archived-task lifecycle, task status notification recipients (leaders/managers), true task analytics, messaging/reminders scope, audit export, and recruitment setting ownership/integration. The frontend developer should flag these rather than decide them unilaterally.

## E. API contract implementation checklist

- [ ] Confirm the current contract version matches the deployed backend; the attached file describes Milestone 8B, not an independently verified deployment.
- [ ] Use exact `/api/v1` paths, UUIDs, field names, enum values and required fields from the attached contract.
- [ ] Send session cookies and CSRF headers correctly; implement temporary-password gate and 429 lockout UX.
- [ ] Use `GET /api/v1/access/me` and the actual effective-access model for operational navigation/actions, without treating `is_system_admin` as a blanket operational grant.
- [ ] Distinguish System Admin-only routes from scoped operational routes.
- [ ] Treat Member profile `PUT` as replacement; handle temporary password as a one-time returned secret.
- [ ] Respect exact task status transitions, assignee eligibility, comment-author permissions and deleted-comment redaction.
- [ ] Handle announcements' versioned read behavior and withdrawn-content redaction.
- [ ] Handle notification preferences, notification redaction, and self-notification exclusion.
- [ ] Use calendar time ranges and offset-aware datetimes; distinguish personal due dates from team-wide tasks.
- [ ] Treat audit as Admin-only read/filter/detail with cursor pagination, not export.
- [ ] Keep all unavailable functionality explicitly tracked as product gaps rather than silently fabricated.


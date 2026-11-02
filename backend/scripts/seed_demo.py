# ruff: noqa  (a local demo tool, not application code)
"""Fill a LOCAL database with a realistic KORA organization and a month of activity.

    uv run alembic upgrade head          # on the target database first
    uv run python scripts/seed_demo.py postgresql+asyncpg://kora:kora@127.0.0.1:5440/kora_demo

People, units and accounts are created directly; everything else (tasks, comments, finished parts and
reviews, requests, chat, announcements, events, league points, notes) goes through the real API in-process,
so notifications, history and audit records look exactly as they would in use.

Every account uses the same demo password (see PASSWORD). Local use only: the script refuses a database
whose name does not contain "demo" and one that already has Members.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from kora_api.access import security
from kora_api.access.models import SystemAdminGrant, UserAccount
from kora_api.core.config import Settings
from kora_api.main import create_app
from kora_api.organization.constants import (
    KORA_UNIT_ID,
    PMO_UNIT_ID,
    MemberStatus,
    RoleKey,
    UnitKind,
    UnitStatus,
)
from kora_api.organization.models import (
    Member,
    MemberTeamPlacement,
    OrgUnit,
    OrgUnitPlacement,
    RoleAssignment,
)

PASSWORD = "Kora-Demo-2026"
NOW = datetime.now(UTC).replace(microsecond=0)

# (username, full name, role, unit key, team key or None)
# Unit keys: kora, pmo, then administrations and teams below.
ADMINS = {"media": "إدارة الإعلام", "ops": "إدارة العمليات", "partners": "إدارة الشراكات"}
TEAMS = {
    "design": ("فريق التصميم", "media"),
    "content": ("فريق المحتوى", "media"),
    "video": ("فريق المونتاج", "media"),
    "logistics": ("فريق اللوجستيات", "ops"),
    "volunteers": ("فريق المتطوعين", "ops"),
    "sponsors": ("فريق الرعاة", "partners"),
    "pr": ("فريق العلاقات العامة", "partners"),
}
E, D, PL, PM = (
    RoleKey.EVENT_PROJECT_LEADER,
    RoleKey.DEPUTY_LEADER,
    RoleKey.PMO_LEADER,
    RoleKey.PMO_MEMBER,
)
AM, TL, M = RoleKey.ADMINISTRATION_MANAGER, RoleKey.TEAM_LEADER, RoleKey.MEMBER
PEOPLE: list[tuple[str, str, RoleKey, str, str | None]] = [
    ("khaled", "خالد العتيبي", E, "kora", None),
    ("noura", "نورة السبيعي", D, "kora", None),
    ("majed", "ماجد الحربي", PL, "pmo", None),
    ("rana", "رنا الزهراني", PM, "pmo", None),
    ("haifa", "هيفاء القرشي", PM, "pmo", None),
    ("sultan", "سلطان القحطاني", AM, "media", None),
    ("nasser", "ناصر الجهني", AM, "ops", None),
    ("faisal", "فيصل الدوسري", AM, "partners", None),
    ("omar", "عمر الشهري", TL, "design", "design"),
    ("hind", "هند العسيري", M, "design", "design"),
    ("fahad", "فهد المالكي", M, "design", "design"),
    ("dana", "دانة الشمري", M, "design", "design"),
    ("lama", "لمى الغامدي", M, "design", "design"),
    ("maha", "مها الدوسري", TL, "content", "content"),
    ("yazeed", "يزيد العنزي", M, "content", "content"),
    ("reem", "ريم الحازمي", M, "content", "content"),
    ("aseel", "أسيل الكعبي", M, "content", "content"),
    ("turki", "تركي البقمي", TL, "video", "video"),
    ("abeer", "عبير الرشيدي", M, "video", "video"),
    ("hamad", "حمد السالم", M, "video", "video"),
    ("badr", "بدر الأحمدي", TL, "logistics", "logistics"),
    ("joud", "جود السلمي", M, "logistics", "logistics"),
    ("ziyad", "زياد الحربي", M, "logistics", "logistics"),
    ("salma", "سلمى القرني", M, "logistics", "logistics"),
    ("ghada", "غادة المطيري", TL, "volunteers", "volunteers"),
    ("saud", "سعود العمري", M, "volunteers", "volunteers"),
    ("nada", "ندى الثبيتي", M, "volunteers", "volunteers"),
    ("abdullah", "عبدالله الفيفي", M, "volunteers", "volunteers"),
    ("lina", "لينا الصالح", TL, "sponsors", "sponsors"),
    ("waleed", "وليد البلوي", M, "sponsors", "sponsors"),
    ("shahad", "شهد العمري", M, "sponsors", "sponsors"),
    ("rakan", "راكان الزامل", TL, "pr", "pr"),
    ("maram", "مرام الفهد", M, "pr", "pr"),
]


def days(n: float) -> str:
    return (NOW + timedelta(days=n)).isoformat()


async def build_structure(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Units, accounts, Members, roles. Returns unit key -> unit id."""
    units: dict[str, uuid.UUID] = {"kora": KORA_UNIT_ID, "pmo": PMO_UNIT_ID}

    async def unit(key: str, kind: UnitKind, name: str, parent: uuid.UUID) -> None:
        row = OrgUnit(kind=kind, name=name, status=UnitStatus.ACTIVE, created_at=NOW)
        db.add(row)
        await db.flush()
        db.add(OrgUnitPlacement(unit_id=row.id, parent_id=parent, valid_from=NOW))
        units[key] = row.id

    for key, name in ADMINS.items():
        await unit(key, UnitKind.ADMINISTRATION, name, KORA_UNIT_ID)
    for key, (name, admin) in TEAMS.items():
        await unit(key, UnitKind.TEAM, name, units[admin])

    hashed = security.hash_password(PASSWORD)
    for username, full_name, role, unit_key, team_key in PEOPLE:
        account = UserAccount(
            username=username,
            password_hash=hashed,
            password_is_temporary=False,
            password_changed_at=NOW,
            status="active",
        )
        db.add(account)
        await db.flush()
        member = Member(
            account_id=account.id,
            full_name=full_name,
            university_id=f"44{abs(hash(username)) % 10**7:07d}",
            major="هندسة" if team_key else None,
            status=MemberStatus.ACTIVE,
        )
        db.add(member)
        await db.flush()
        if team_key:
            db.add(
                MemberTeamPlacement(
                    member_id=member.id,
                    team_id=units[team_key],
                    valid_from=NOW,
                    created_by_account_id=account.id,
                )
            )
        db.add(
            RoleAssignment(
                member_id=member.id,
                role_key=role,
                unit_id=units[unit_key],
                valid_from=NOW,
                created_by_account_id=account.id,
            )
        )
    admin = UserAccount(
        username="admin",
        password_hash=hashed,
        password_is_temporary=False,
        password_changed_at=NOW,
        status="active",
    )
    db.add(admin)
    await db.flush()
    db.add(SystemAdminGrant(account_id=admin.id, granted_at=NOW))
    await db.commit()
    return units


class Who:
    """A signed-in user driving the in-process API."""

    def __init__(self, app: Any, username: str) -> None:
        self.username = username
        self.http = AsyncClient(transport=ASGITransport(app=app), base_url="https://demo")
        self.member_id = ""

    async def login(self) -> "Who":
        r = await self.http.post(
            "/api/v1/auth/sign-in", json={"username": self.username, "password": PASSWORD}
        )
        r.raise_for_status()
        self.csrf = r.json()["csrf_token"]
        self.member_id = r.json()["account"]["member_id"] or ""
        return self

    async def call(
        self, method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200, 201, 204)
    ) -> Any:
        r = await self.http.request(
            method, "/api/v1" + path, json=body, headers={"X-CSRF-Token": self.csrf}
        )
        if r.status_code not in ok:
            raise RuntimeError(f"{self.username} {method} {path} -> {r.status_code} {r.text[:300]}")
        return r.json() if r.content else None


async def main(url: str) -> None:
    engine = create_async_engine(url)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        if (await db.scalar(select(func.count()).select_from(Member))) or 0:
            sys.exit("This database already has Members; use a fresh demo database.")
        units = await build_structure(db)
    await engine.dispose()

    app = create_app(Settings(environment="local", database_url=SecretStr(url)))
    users: dict[str, Who] = {}
    for username, *_ in PEOPLE:
        users[username] = await Who(app, username).login()
    mid = {u: w.member_id for u, w in users.items()}
    api = lambda who: users[who].call  # noqa: E731

    # ---- Tasks -------------------------------------------------------------------------------
    async def task(
        creator: str,
        scope: str,
        title: str,
        assignees: list[str],
        *,
        due: float | None,
        priority: str = "normal",
        description: str | None = None,
        state: str = "new",
        comments: list[tuple[str, str]] | None = None,
        subtasks: list[tuple[str, list[str]]] | None = None,
        other: list[str] | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "title": title,
            "scope_unit_id": str(units[scope]),
            "priority": priority,
            "description": description,
            "assignee_member_ids": [mid[a] for a in assignees],
            "external_assignee_member_ids": [mid[o] for o in other or []],
        }
        if due is not None:
            body["due_at"] = days(due)
        t = await api(creator)("POST", "/tasks", body)
        tid = t["id"]
        for sub_title, sub_who in subtasks or []:
            await api(creator)(
                "POST",
                f"/tasks/{tid}/subtasks",
                {"title": sub_title, "assignee_member_ids": [mid[a] for a in sub_who]},
            )
        for who, text in comments or []:
            await api(who)("POST", f"/tasks/{tid}/comments", {"body": text})
        first = (assignees or other or [creator])[0]
        if state in ("progress", "partial", "done"):
            await api(first)("POST", f"/tasks/{tid}/status", {"status": "in_progress"})
        if state == "partial":
            await api(first)("PUT", f"/tasks/{tid}/progress", {"finished": True})
        if state == "done":
            await api(creator)("POST", f"/tasks/{tid}/status", {"status": "completed"})
        if state == "cancelled":
            await api(creator)("POST", f"/tasks/{tid}/status", {"status": "cancelled"})
        return tid

    # Design team
    await task(
        "omar",
        "design",
        "تصميم هوية الفعالية البصرية",
        ["hind", "fahad"],
        due=6,
        priority="high",
        description="الشعار، الألوان، والخطوط المعتمدة لجميع المطبوعات.",
        state="progress",
        comments=[
            ("hind", "بدأت بالمسودة الأولى للشعار، أرفقها قريباً."),
            ("omar", "ممتاز، ركّزوا على ثبات الألوان على الطباعة."),
            ("fahad", "جرّبت ثلاث لوحات ألوان، أي واحدة نعتمد؟"),
        ],
        subtasks=[("مسودات الشعار", ["hind"]), ("لوحة الألوان", ["fahad"])],
    )
    await task(
        "omar", "design", "لوحات الإرشاد داخل القاعة", ["dana"], due=9, priority="high", state="new"
    )
    await task(
        "omar",
        "design",
        "تصميم دعوات الحضور الرقمية",
        ["lama", "dana"],
        due=-2,
        priority="urgent",
        state="progress",
        comments=[
            ("lama", "التصميم جاهز للمراجعة النهائية."),
            ("omar", "نحتاجه اليوم قبل إرساله للرعاة."),
        ],
    )
    await task(
        "omar",
        "design",
        "قوالب منشورات المنصات",
        ["hind"],
        due=-5,
        state="done",
        comments=[("hind", "تم التسليم في المجلد المشترك.")],
    )
    await task(
        "omar",
        "design",
        "غلاف كتيب البرنامج",
        ["fahad"],
        due=3,
        priority="normal",
        state="partial",
        comments=[("fahad", "أنهيت التصميم وأحتاج مراجعتك.")],
    )
    await task("omar", "design", "بنرات الصفحة الرئيسية للموقع", ["lama"], due=12, state="new")
    await task(
        "omar",
        "design",
        "تصميم شهادات المشاركة",
        ["dana"],
        due=20,
        priority="low",
        state="cancelled",
    )
    # Content team
    await task(
        "maha",
        "content",
        "كتابة نص كلمة الافتتاح",
        ["yazeed"],
        due=4,
        priority="high",
        state="progress",
        comments=[
            ("yazeed", "المسودة الأولى جاهزة، بانتظار ملاحظاتك."),
            ("maha", "أضف فقرة عن الرعاة."),
        ],
    )
    await task(
        "maha", "content", "تغطية نشرة الأسبوع الإخبارية", ["reem", "aseel"], due=2, state="new"
    )
    await task(
        "maha",
        "content",
        "أسئلة شائعة للمشاركين",
        ["aseel"],
        due=-1,
        priority="normal",
        state="progress",
    )
    await task(
        "maha",
        "content",
        "ملخص المتحدثين وسيرهم",
        ["reem"],
        due=7,
        state="partial",
        comments=[("reem", "أنهيت سير ستة متحدثين.")],
    )
    await task("maha", "content", "نصوص الفيديو الترويجي", ["yazeed", "reem"], due=-8, state="done")
    # Video team
    await task(
        "turki",
        "video",
        "مونتاج الفيديو الترويجي",
        ["abeer", "hamad"],
        due=8,
        priority="high",
        state="progress",
        subtasks=[("اختيار اللقطات", ["hamad"]), ("المؤثرات والصوت", ["abeer"])],
        comments=[("abeer", "اخترت الموسيقى، أرسلها لك للموافقة.")],
    )
    await task("turki", "video", "تصوير مقابلات المتحدثين", ["hamad"], due=5, state="new")
    await task("turki", "video", "فيديو شكر للرعاة", ["abeer"], due=14, priority="low", state="new")
    # Logistics
    await task(
        "badr",
        "logistics",
        "حجز القاعة والتجهيزات",
        ["joud", "ziyad"],
        due=-3,
        priority="urgent",
        state="progress",
        comments=[
            ("joud", "تواصلت مع إدارة المبنى وننتظر تأكيد الحجز."),
            ("badr", "نريد التأكيد قبل نهاية الأسبوع."),
        ],
    )
    await task("badr", "logistics", "ترتيب المواصلات للضيوف", ["salma"], due=10, state="new")
    await task(
        "badr",
        "logistics",
        "قائمة المعدات الصوتية",
        ["ziyad"],
        due=6,
        priority="high",
        state="partial",
    )
    await task("badr", "logistics", "تجهيز منصة التسجيل", ["joud"], due=-6, state="done")
    await task(
        "badr",
        "logistics",
        "التأمين وخطة الإخلاء",
        ["salma", "ziyad"],
        due=15,
        priority="high",
        state="new",
    )
    # Volunteers
    await task(
        "ghada",
        "volunteers",
        "استقطاب متطوعي اليوم الأول",
        ["saud", "nada"],
        due=7,
        priority="high",
        state="progress",
        comments=[("saud", "وصلنا إلى 40 متقدماً."), ("ghada", "ممتاز، حدّدوا مواعيد المقابلات.")],
    )
    await task("ghada", "volunteers", "جدول المناوبات", ["abdullah"], due=9, state="new")
    await task(
        "ghada",
        "volunteers",
        "تدريب المتطوعين على الاستقبال",
        ["nada", "abdullah"],
        due=11,
        state="new",
    )
    await task("ghada", "volunteers", "قمصان المتطوعين", ["saud"], due=-4, state="done")
    # Sponsors / PR
    await task(
        "lina",
        "sponsors",
        "عروض الرعاية للشركات",
        ["waleed", "shahad"],
        due=5,
        priority="high",
        state="progress",
        comments=[("waleed", "أرسلنا عرضين وننتظر الردود.")],
    )
    await task(
        "lina",
        "sponsors",
        "متابعة عقود الرعاة الذهبيين",
        ["shahad"],
        due=-2,
        priority="urgent",
        state="progress",
    )
    await task(
        "rakan", "pr", "بيان صحفي للإطلاق", ["maram"], due=3, priority="high", state="partial"
    )
    await task("rakan", "pr", "التواصل مع وسائل الإعلام المحلية", ["maram"], due=13, state="new")
    # Administration level (assigned to team leaders)
    await task(
        "sultan",
        "media",
        "خطة الإعلام للافتتاح",
        ["omar", "maha", "turki"],
        due=5,
        priority="high",
        state="progress",
        description="جدول موحّد للمحتوى والتصميم والمونتاج حتى يوم الافتتاح.",
        comments=[("omar", "جدول التصميم جاهز."), ("sultan", "أرسلوا جداولكم قبل اجتماع الخميس.")],
    )
    await task(
        "nasser",
        "ops",
        "خطة يوم الفعالية الميدانية",
        ["badr", "ghada"],
        due=10,
        priority="high",
        state="new",
    )
    await task("faisal", "partners", "حملة الرعاة الجدد", ["lina", "rakan"], due=18, state="new")
    # Created by the Event Leader (outside the team's own leadership) and with "Other" assignees
    await task(
        "khaled",
        "design",
        "مراجعة هوية الفعالية قبل الاعتماد",
        ["omar"],
        due=8,
        priority="high",
        state="new",
        comments=[("khaled", "أريد رؤية النسخة النهائية قبل نهاية الأسبوع.")],
    )
    await task(
        "khaled",
        "logistics",
        "التنسيق مع الجهة المضيفة",
        ["badr"],
        due=6,
        state="progress",
        other=["nasser"],
    )
    await task(
        "noura",
        "content",
        "مراجعة نص الإعلان الرسمي",
        ["maha"],
        due=2,
        priority="urgent",
        state="new",
    )

    # A weekly series (preparation meetings notes)
    await api("omar")(
        "POST",
        "/task-series",
        {
            "scope_unit_id": str(units["design"]),
            "title": "تسليم أسبوعي: ملف التصاميم الجاهزة",
            "priority": "normal",
            "first_due_at": days(2),
            "ends_at": days(30),
            "assignee_member_ids": [mid["hind"], mid["fahad"]],
            "subtasks": [
                {"title": "مراجعة الملفات قبل التسليم", "assignee_member_ids": [mid["hind"]]}
            ],
        },
    )

    # ---- Requests between administrations ----------------------------------------------------
    async def request(
        sender: str, from_unit: str, to_unit: str, title: str, body: str, due: float, priority: str
    ) -> str:
        r = await api(sender)(
            "POST",
            "/task-requests",
            {
                "title": title,
                "description": body,
                "priority": priority,
                "due_at": days(due),
                "from_unit_id": str(units[from_unit]),
                "to_unit_id": str(units[to_unit]),
            },
        )
        return r["id"]

    await request(
        "sultan",
        "media",
        "ops",
        "تجهيز منصة الاستقبال الإعلامية",
        "نحتاج منصة وأجهزة للتصوير عند المدخل.",
        9,
        "high",
    )
    done = await request(
        "nasser",
        "ops",
        "media",
        "تصميم لوحات الإرشاد الميدانية",
        "لوحات للمواقف والمداخل والممرات.",
        7,
        "normal",
    )
    await api("sultan")(
        "POST", f"/task-requests/{done}/accept", {"assignee_member_ids": [mid["omar"], mid["hind"]]}
    )
    no = await request(
        "faisal",
        "partners",
        "media",
        "فيديو تعريفي عن الشراكات",
        "فيديو قصير يعرض باقات الرعاية.",
        14,
        "normal",
    )
    await api("sultan")(
        "POST",
        f"/task-requests/{no}/reject",
        {"reason": "الفريق مشغول بالفيديو الترويجي حتى نهاية الشهر."},
    )
    gone = await request(
        "sultan",
        "media",
        "partners",
        "قائمة الضيوف الإعلاميين",
        "ترشيح الضيوف الإعلاميين للحضور.",
        10,
        "low",
    )
    await api("sultan")("POST", f"/task-requests/{gone}/withdraw")
    await request(
        "khaled",
        "kora",
        "ops",
        "خطة الطوارئ والإسعاف",
        "خطة معتمدة لحالات الطوارئ يوم الفعالية.",
        12,
        "urgent",
    )

    # ---- Chat --------------------------------------------------------------------------------
    org = next(
        c for c in await api("khaled")("GET", "/chat/conversations") if c["kind"] == "organization"
    )
    for who, text in [
        ("khaled", "أهلاً بالجميع! بقي أقل من أسبوعين على الفعالية، شكراً على جهودكم."),
        ("sultan", "فريق الإعلام جاهز بجدول المحتوى، نحتاج فقط اعتماد الهوية."),
        ("nasser", "العمليات: تأكدنا من القاعة الرئيسية وسنُعلن الجدول غداً."),
        ("majed", "تذكير: اجتماع المتابعة الخميس الساعة 5 مساءً، نرجو تحديث المهام قبله."),
        ("noura", "بارك الله فيكم، لا تترددوا في التواصل لأي عائق."),
        ("lina", "وصلنا تأكيد من راعٍ ذهبي جديد 🎉"),
    ]:
        await api(who)("POST", f"/chat/conversations/{org['id']}/messages", {"body": text})
    team_lines = {
        "design": [
            ("omar", "صباح الخير، من يستطيع مراجعة اللوحات اليوم؟"),
            ("hind", "أنا أراجعها بعد الظهر."),
            ("fahad", "رفعت نسخة معدّلة من الألوان في المجلد."),
            ("dana", "جاري العمل على لوحات الإرشاد."),
        ],
        "content": [
            ("maha", "نحتاج النصوص النهائية الأحد."),
            ("yazeed", "مسودة الكلمة جاهزة."),
            ("reem", "سأرسل سير المتحدثين غداً."),
        ],
        "video": [("turki", "موعد التصوير الأربعاء الساعة 10."), ("abeer", "تمام، سأجهز المعدات.")],
        "logistics": [("badr", "أي تحديث عن حجز القاعة؟"), ("joud", "ننتظر رد إدارة المبنى.")],
        "volunteers": [
            ("ghada", "قابلنا 12 متطوعاً اليوم."),
            ("nada", "الدفعة القادمة غداً بإذن الله."),
        ],
    }
    for team, lines in team_lines.items():
        author = lines[0][0]
        conv = next(
            c
            for c in await api(author)("GET", "/chat/conversations")
            if c["unit_id"] == str(units[team])
        )
        for who, text in lines:
            await api(who)("POST", f"/chat/conversations/{conv['id']}/messages", {"body": text})
    admin_conv = next(
        c
        for c in await api("sultan")("GET", "/chat/conversations")
        if c["unit_id"] == str(units["media"])
    )
    for who, text in [
        ("sultan", "اجتماع إدارة الإعلام الأحد 11 صباحاً."),
        ("omar", "سأحضر مع الفريق."),
        ("maha", "جدول المحتوى جاهز للعرض."),
    ]:
        await api(who)("POST", f"/chat/conversations/{admin_conv['id']}/messages", {"body": text})
    for a, b, lines in [
        ("omar", "hind", ["هند، هل أنهيتِ مسودة الشعار؟", "نعم، سأرسلها خلال ساعة.", "ممتاز 👌"]),
        ("sultan", "omar", ["عمر، ما وضع الهوية البصرية؟", "تقدّمنا جيداً، ننتظر رأي القائد."]),
        ("khaled", "sultan", ["سلطان، أريد ملخصاً سريعاً عن الإعلام.", "حاضر، سأرسله هذا المساء."]),
    ]:
        dm = await api(a)("POST", "/chat/conversations/direct", {"member_id": mid[b]})
        for i, text in enumerate(lines):
            await api(a if i % 2 == 0 else b)(
                "POST", f"/chat/conversations/{dm['id']}/messages", {"body": text}
            )

    # ---- Announcements -----------------------------------------------------------------------
    everyone = [mid[u] for u, *_ in PEOPLE]
    ann = await api("khaled")(
        "POST",
        "/announcements",
        {
            "scope_unit_id": str(KORA_UNIT_ID),
            "title": "انطلاق مرحلة الاستعداد النهائي",
            "body": "نبدأ اليوم مرحلة الاستعداد النهائي للفعالية. الرجاء تحديث حالة مهامكم يومياً والتواصل مع قادة فرقكم عند أي عائق.",
        },
    )
    await api("khaled")(
        "POST", f"/announcements/{ann['id']}/publish", {"recipient_member_ids": everyone}
    )
    media_people = [
        mid[u]
        for u, _, _, unit, team in PEOPLE
        if unit == "media" or team in ("design", "content", "video")
    ]
    a2 = await api("sultan")(
        "POST",
        "/announcements",
        {
            "scope_unit_id": str(units["media"]),
            "title": "موعد تسليم الهوية والمحتوى",
            "body": "آخر موعد لتسليم الهوية البصرية ونصوص الافتتاح هو يوم الخميس القادم.",
        },
    )
    await api("sultan")(
        "POST", f"/announcements/{a2['id']}/publish", {"recipient_member_ids": media_people}
    )
    a3 = await api("omar")(
        "POST",
        "/announcements",
        {
            "scope_unit_id": str(units["design"]),
            "title": "ورشة مراجعة التصاميم",
            "body": "ورشة داخلية لمراجعة جميع التصاميم يوم الأحد بعد الاجتماع.",
        },
    )
    await api("omar")(
        "POST",
        f"/announcements/{a3['id']}/publish",
        {"recipient_member_ids": [mid[u] for u in ("hind", "fahad", "dana", "lama")]},
    )
    await api("nasser")(
        "POST",
        "/announcements",
        {
            "scope_unit_id": str(units["ops"]),
            "title": "مسودة: تعليمات يوم الفعالية",
            "body": "قيد الإعداد.",
        },
    )
    for u in ("hind", "dana", "yazeed", "badr"):  # a few people have opened the first announcement
        await api(u)("GET", f"/announcements/{ann['id']}")

    # ---- Calendar ----------------------------------------------------------------------------
    def at(day: int, hour: int, minutes: int = 0) -> str:
        return (
            NOW.replace(hour=0, minute=0, second=0)
            + timedelta(days=day, hours=hour, minutes=minutes)
        ).isoformat()

    managers = [mid[u] for u in ("sultan", "nasser", "faisal", "majed", "noura")]
    events = [
        (
            "khaled",
            "meeting",
            "kora",
            "اجتماع المتابعة الأسبوعي",
            at(2, 17),
            at(2, 18, 30),
            managers,
            "قاعة الاجتماعات الرئيسية",
            None,
        ),
        (
            "sultan",
            "meeting",
            "media",
            "اجتماع إدارة الإعلام",
            at(1, 11),
            at(1, 12),
            [mid[u] for u in ("omar", "maha", "turki")],
            None,
            "https://meet.example.com/media-sync",
        ),
        (
            "omar",
            "event",
            "design",
            "ورشة مراجعة التصاميم",
            at(3, 13),
            at(3, 15),
            [mid[u] for u in ("hind", "fahad", "dana", "lama")],
            "استوديو التصميم",
            None,
        ),
        (
            "ghada",
            "event",
            "volunteers",
            "لقاء تعريفي بالمتطوعين",
            at(4, 16),
            at(4, 18),
            [mid[u] for u in ("saud", "nada", "abdullah")],
            "القاعة 2",
            None,
        ),
        (
            "nasser",
            "meeting",
            "ops",
            "جولة ميدانية في موقع الفعالية",
            at(6, 9),
            at(6, 11),
            [mid[u] for u in ("badr", "ghada", "joud")],
            "موقع الفعالية",
            None,
        ),
        (
            "khaled",
            "event",
            "kora",
            "حفل الافتتاح",
            at(14, 18),
            at(14, 22),
            everyone,
            "المسرح الرئيسي",
            None,
        ),
        (
            "lina",
            "meeting",
            "sponsors",
            "لقاء الرعاة الذهبيين",
            at(-1, 14),
            at(-1, 15),
            [mid["waleed"], mid["shahad"]],
            None,
            "https://meet.example.com/sponsors",
        ),
    ]
    for who, kind, scope, title, start, end, invitees, place, link in events:
        body: dict[str, Any] = {
            "type": kind,
            "title": title,
            "starts_at": start,
            "ends_at": end,
            "scope_unit_id": str(units[scope]),
            "invitee_member_ids": [i for i in invitees if i != mid[who]],
        }
        if place:
            body["location_text"] = place
        if link:
            body["online_url"] = link
        await api(who)("POST", "/calendar/events", body)

    # ---- League, notes -----------------------------------------------------------------------
    points = {
        "design": 120,
        "content": 95,
        "video": 80,
        "logistics": 110,
        "volunteers": 70,
        "sponsors": 130,
        "pr": 60,
    }
    await api("majed")(
        "PUT",
        "/league",
        {
            "round_title": "الجولة الثالثة",
            "points": [{"team_id": str(units[k]), "points": v} for k, v in points.items()],
        },
    )
    await api("omar")(
        "PUT",
        "/me/note",
        {
            "body": "• مراجعة الشعار مع القائد\n• تسليم الملفات للطباعة الخميس\n• اجتماع المونتاج",
            "version": 0,
        },
    )
    await api("sultan")(
        "PUT",
        "/me/note",
        {"body": "• متابعة طلب منصة الاستقبال\n• ملخص الإعلام لخالد", "version": 0},
    )

    for w in users.values():
        await w.http.aclose()
    print(f"Done: {len(PEOPLE)} members + admin. Password for everyone: {PASSWORD}")
    print(
        "Try: omar (Team Leader), sultan (Administration Manager), khaled (Event Leader), hind (Member), majed (PMO Leader), admin (System Admin)"
    )


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if "demo" not in target.rsplit("/", 1)[-1]:
        sys.exit('Pass a database URL whose name contains "demo".')
    asyncio.run(main(target))

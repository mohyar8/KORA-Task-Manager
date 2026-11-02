# البيئة التجريبية الواقعية (محلية فقط)

قاعدة بيانات محلية اسمها `kora_demo` مملوءة بمنظمة كورة كاملة (33 عضواً، 3 إدارات، 7 فرق، PMO) وشهر من النشاط: نحو 53 مهمة بحالات مختلفة (جديدة، قيد التنفيذ، متأخرة، منجزة، ملغاة، إنجاز جزئي مع مهام مراجعة)، تعليقات ومهام فرعية وسلسلة أسبوعية، 5 طلبات بين الإدارات (معلّق/مقبول/مرفوض/مسحوب)، دردشة (المنظمة والإدارة والفرق ورسائل خاصة)، إعلانات (منشورة ومسودة)، أحداث تقويم، نقاط الدوري، وملاحظات خاصة.

كل شيء عدا الأشخاص والهيكل أُنشئ **عبر الـ API نفسه**، فالإشعارات والسجل والتدقيق كما في الاستخدام الفعلي.

## التشغيل

1. شغّل Docker Desktop ثم حاوية قاعدة البيانات `kora-review-db` (المنفذ 5440).
2. الباك اند (من مجلد `backend`، PowerShell):

```powershell
$env:KORA_ENVIRONMENT='local'; $env:KORA_DATABASE_URL='postgresql+asyncpg://kora:kora@127.0.0.1:5440/kora_demo'; uv run uvicorn kora_api.main:app --port 8000
```

3. الفرونت (من مجلد `frontend`): `npm run dev` ثم افتح العنوان الذي يطبعه (غالباً http://localhost:5173).
4. وضع الـ mock القديم (بيانات داخل المتصفح بلا خادم): `npm run dev:mock`.

> مهم: لا تشغّل الباك اند بلا تحديد `KORA_DATABASE_URL` كما فوق، فملف `backend/.env` يشير إلى قاعدة سحابية (Neon) وسيتصل بها.

## الحسابات (كلمة المرور للجميع: `Kora-Demo-2026`)

| الحساب | الدور | جرّب |
|---|---|---|
| `khaled` | قائد الحدث | كل شيء، طلب من كورة، إعلانات المنظمة |
| `noura` | نائب القائد | |
| `majed` | قائد PMO | الدوري، المتابعة |
| `sultan` | مدير إدارة الإعلام | الطلبات الصادرة، مراجعة مهام الفرق |
| `nasser` | مدير إدارة العمليات | الطلبات الواردة (طلبان معلّقان) |
| `faisal` | مدير إدارة الشراكات | |
| `omar` | قائد فريق التصميم | مهام المراجعة، دردشة الفريق |
| `maha`، `turki`، `badr`، `ghada`، `lina`، `rakan` | قادة فرق | |
| `hind`، `fahad`، `dana`، `lama`، `yazeed`، `reem`، `joud`، `saud`… | أعضاء | لاحظ أنهم لا يستطيعون إغلاق المهمة: يضغطون «أنهيت جزئيتي» |
| `admin` | System Admin (بلا Member) | الأعضاء والصلاحيات والتدقيق |

## إعادة البناء من الصفر

```powershell
docker exec kora-review-db psql -U kora -d postgres -c "DROP DATABASE IF EXISTS kora_demo" -c "CREATE DATABASE kora_demo"
$env:KORA_ENVIRONMENT='local'; $env:KORA_DATABASE_URL='postgresql+asyncpg://kora:kora@127.0.0.1:5440/kora_demo'
uv run alembic upgrade head
uv run python scripts/seed_demo.py $env:KORA_DATABASE_URL
```

السكربت `scripts/seed_demo.py` يرفض أي قاعدة اسمها لا يحتوي `demo` أو فيها أعضاء أصلاً.

## ما لا يعمل هنا
- رفع الملفات يعطي «تخزين الملفات غير مفعّل بعد» إلى أن تضبط `KORA_STORAGE_*` (حاوية S3 خاصة مع CORS يسمح بـ PUT من عنوان الفرونت).
- المواعيد كلها نُسبت إلى لحظة التعبئة؛ أعد البناء لتتجدد التواريخ.

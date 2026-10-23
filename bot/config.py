"""Bot konfiguratsiyasi va boshlang'ich ma'lumotlar (sohalar + yo'nalishlar).

DIQQAT: .env faylida BOT_TOKEN va ADMIN_ID ni to'ldiring.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

# .env fayl bir nechta joyda bo'lishi mumkin (Pydroid uchun qulay)
for _candidate in (
    PROJECT_DIR / ".env",
    BASE_DIR / ".env",
    Path.cwd() / ".env",
):
    if _candidate.is_file():
        load_dotenv(_candidate, override=False)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "ha"}


# ---------------------------------------------------------------- asosiy sozlamalar
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID: int = _get_int("ADMIN_ID", 0)
DB_PATH: str = os.getenv("DB_PATH", str(PROJECT_DIR / "bot_data.db")).strip()

# Bot ishga tushgandan keyin to'ldiriladi (main.py da)
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "").strip()

# ---------------------------------------------------------------- cheklovlar
DAILY_ORDER_LIMIT: int = _get_int("DAILY_ORDER_LIMIT", 5)
MAX_ACTIVE_ORDERS: int = _get_int("MAX_ACTIVE_ORDERS", 3)
ORDER_TIMEOUT_MINUTES: int = _get_int("ORDER_TIMEOUT_MINUTES", 30)

# ---------------------------------------------------------------- texnik
PAGINATION_SIZE: int = _get_int("PAGINATION_SIZE", 8)
SEND_DELAY: float = _get_float("SEND_DELAY", 0.05)
TZ_OFFSET_HOURS: int = _get_int("TZ_OFFSET_HOURS", 5)
ADMIN_NOTIFY_ALL: bool = _get_bool("ADMIN_NOTIFY_ALL", True)

# ---------------------------------------------------------------- bepul hosting (ixtiyoriy)
# Render.com kabi xizmatlarda diski vaqtincha — baza GitHub Gist orqali saqlanadi.
# 0 = o'chirilgan
MAX_RUNTIME_MINUTES: int = _get_int("MAX_RUNTIME_MINUTES", 0)      # 0 = cheksiz ishlaydi
GIST_TOKEN: str = os.getenv("GIST_TOKEN", "").strip()              # GitHub PAT (gist scope)
GIST_ID: str = os.getenv("GIST_ID", "").strip()                    # Gist ID (avtomatik yaratiladi)
GIST_INTERVAL_MINUTES: int = _get_int("GIST_INTERVAL_MINUTES", 5)  # baza nusxasi oraliq

# "Boshqa" sohasi — ro'yxatda yo'q yo'nalishlar shu yerga tushadi
CUSTOM_CATEGORY_NAME = "➕ Boshqa"

ROLE_EXECUTOR = "executor"
ROLE_CUSTOMER = "customer"

ROLE_LABELS = {
    ROLE_EXECUTOR: "👷 Ijrochi",
    ROLE_CUSTOMER: "📝 Buyurtmachi",
}

# ---------------------------------------------------------------- boshlang'ich katalog
# Bot birinchi marta ishga tushganda shu ro'yxat bazaga yoziladi.
# Keyinchalik baza asosiy manba bo'lib qoladi (admin /addskill orqali o'zgartiriladi).
INITIAL_CATEGORIES: dict[str, list[str]] = {
    "🎨 Dizayn": [
        "Logo",
        "Banner",
        "Instagram/Telegram dizayn",
        "Taqdimot (PowerPoint)",
        "Vizitka va flayer",
        "Qadoq (packaging) dizayni",
        "Infografika",
        "Brend kitobi (brandbook)",
        "UI/UX dizayn",
        "Illyustratsiya",
        "3D modellashtirish",
        "Mockup",
        "Kitob muqovasi",
    ],
    "💻 Dasturlash": [
        "Telegram bot",
        "Veb-sayt (frontend)",
        "Backend/API",
        "Mobil ilova",
        "Desktop dastur",
        "Skript/avtomatlashtirish",
        "Parser/scraping",
        "O'yin yaratish",
        "Ma'lumotlar bazasi",
        "Xatolarni tuzatish (debugging)",
        "Sayt ko'chirish va hosting sozlash",
        "WordPress/Tilda/Shopify",
        "AI/chatbot integratsiyasi",
        "Kod tekshirish (code review)",
    ],
    "🌐 Tarjima va matn": [
        "Ingliz-O'zbek",
        "Rus-O'zbek",
        "Boshqa tillar",
        "Sinxron tarjima",
        "Subtitr yaratish",
        "Korrektor/muharrir",
        "Transkripsiya (audio/videodan matn)",
    ],
    "✍️ Kontent va kopirayting": [
        "Post va maqola yozish",
        "Sayt matnlari",
        "Reklama matni",
        "Ssenariy yozish",
        "Referat/kurs ishi yordami",
        "CV/rezyume yozish",
        "Prezentatsiya matni",
        "Ijodiy yozuv (hikoya, she'r)",
        "SEO matn",
    ],
    "🎬 Video va audio": [
        "Video montaj",
        "Reels/TikTok/Shorts",
        "Animatsiya",
        "Motion grafika",
        "Intro/outro",
        "Ovoz yozish (diktor)",
        "Podcast montaji",
        "Musiqa/saundtrek",
        "Ovozni tozalash",
        "Video rangini sozlash (color grading)",
    ],
    "📣 SMM va marketing": [
        "Kontent reja",
        "Instagram/Telegram yuritish",
        "Target reklama",
        "Google/Yandex reklama",
        "SEO optimallashtirish",
        "Email marketing",
        "Bozor tahlili",
        "Raqobatchilar tahlili",
        "Brend strategiyasi",
        "Influenser bilan ishlash",
    ],
    "📊 Biznes va hisob": [
        "Buxgalteriya",
        "Soliq hisoboti",
        "Moliyaviy model",
        "Biznes-reja",
        "Excel/Google Sheets",
        "Ma'lumotlar tahlili",
        "Prezentatsiya (investor uchun)",
        "Hujjat/shartnoma tayyorlash",
        "CRM sozlash",
    ],
    "🧑‍💼 Virtual yordamchi (assistent)": [
        "Ma'lumot kiritish (data entry)",
        "Mijozlar bilan yozishma",
        "Kalendar va vazifalar boshqaruvi",
        "Ma'lumot qidirish (research)",
        "Operator/qo'llab-quvvatlash xizmati",
    ],
    "🎓 O'qitish va repetitorlik": [
        "Matematika",
        "Ingliz tili",
        "Rus tili",
        "Dasturlash",
        "Dizayn",
        "Fizika/Kimyo/Biologiya",
        "IELTS/DTM tayyorlov",
        "Maktab fanlari",
        "Kompyuter savodxonlik",
        "Onlayn kurs yaratish",
    ],
    "🏗 Muhandislik va chizma": [
        "AutoCAD chizma",
        "3D modellashtirish (SolidWorks, Blender)",
        "Arxitektura loyiha",
        "Interyer dizayn",
        "Elektr sxemalar",
        "Vizualizatsiya (render)",
    ],
    "🔐 IT va texnik xizmat": [
        "Tarmoq sozlash",
        "Server sozlash (VPS)",
        "Xavfsizlik tekshiruvi",
        "Kompyuter ta'mirlash (masofadan)",
        "Dastur o'rnatish va sozlash",
        "Zaxira nusxa (backup)",
    ],
    "🧠 Sun'iy intellekt": [
        "Prompt yozish",
        "AI bilan rasm/video yaratish",
        "Chatbot sozlash",
        "Ma'lumot tahlili (ML)",
        "Avtomatlashtirish (n8n, Zapier)",
        "AI asosida kontent yaratish",
    ],
    "🛒 Elektron savdo": [
        "Marketplace kartochkalari (Uzum, Wildberries)",
        "Mahsulot tavsifi",
        "Do'kon sozlash",
        "Mahsulot rasmlariga ishlov berish",
        "Katalog tayyorlash",
    ],
    "📷 Rasm va foto": [
        "Retush",
        "Fon o'chirish",
        "Rasm sifatini oshirish",
        "Foto kollaj",
        "Eski rasmlarni tiklash",
        "Mahsulot fotosuratiga ishlov berish",
    ],
    "➕ Boshqa": [],
}

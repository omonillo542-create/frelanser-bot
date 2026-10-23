"""Yordamchi funksiyalar: xatolarni boshqarish va matn shakllantirish."""

from __future__ import annotations

import logging
from html import escape
from typing import Any, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.database import db

log = logging.getLogger(__name__)

# Bo'sh klaviatura — eski xabardagi tugmalarni olib tashlash uchun
EMPTY_MARKUP = InlineKeyboardMarkup(inline_keyboard=[])

STATUS_LABELS = {
    "open": "🔄 Kutmoqda",
    "taken": "🔧 Bajarilmoqda",
    "done": "✅ Bajarildi",
    "cancelled": "❌ Bekor qilindi",
}

STATUS_EMOJI = {
    "open": "🔄",
    "taken": "🔧",
    "done": "✅",
    "cancelled": "❌",
}

# Kategoriya topilmaganda ko'rsatiladigan umumiy nom
NO_CATEGORY = "Yo'nalishlar"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "❓ Noma'lum")


def clean(text: Optional[str], limit: int = 4000) -> str:
    """HTML xavfsiz matn + uzunlik cheklovi."""
    if not text:
        return ""
    value = escape(str(text).strip(), quote=False)
    if len(value) > limit:
        value = value[:limit] + "…"
    return value


# ---------------------------------------------------------------- foydalanuvchi
async def ensure_user(user: Any) -> dict:
    """Foydalanuvchini bazada mavjud qiladi va ma'lumotlarini yangilaydi."""
    try:
        return await db.get_or_create_user(user.id, user.username, user.full_name)
    except Exception as exc:  # pragma: no cover
        log.exception("ensure_user xatosi: %s", exc)
        return {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": None,
            "rating_sum": 0,
            "rating_count": 0,
            "is_active": 1,
        }


def user_label(user: Optional[dict]) -> str:
    """Ism + @username (username yo'q bo'lsa faqat ism)."""
    if not user:
        return "Noma'lum"
    name = clean(user.get("full_name"), 64) or "Foydalanuvchi"
    username = user.get("username")
    if username:
        return f"{name} (@{username})"
    return name


# ---------------------------------------------------------------- xavfsiz chaqiruvlar
async def safe_answer(call: CallbackQuery, text: str = "", show_alert: bool = False) -> None:
    try:
        await call.answer(text, show_alert=show_alert)
    except TelegramAPIError:
        pass
    except Exception as exc:  # pragma: no cover
        log.debug("call.answer xatosi: %s", exc)


async def safe_edit(call: CallbackQuery, text: Optional[str] = None, reply_markup: Any = None) -> None:
    try:
        if call.message is None:
            return
        if text is None and reply_markup is None:
            return
        await call.message.edit_text(text, reply_markup=reply_markup)
    except TelegramAPIError as exc:
        log.debug("edit_text xatosi: %s", exc)
    except Exception as exc:  # pragma: no cover
        log.debug("edit_text xatosi: %s", exc)


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs: Any) -> Optional[Message]:
    """Xabar yuborish (xatolarni yutib qo'yadi)."""
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except TelegramAPIError as exc:
        log.warning("Yuborib bo'lmadi (chat_id=%s): %s", chat_id, exc)
    except Exception as exc:  # pragma: no cover
        log.exception("Yuborish xatosi: %s", exc)
    return None


# ---------------------------------------------------------------- buyurtma matnlari
def format_order(
    order: dict,
    category_name: Optional[str] = None,
    skill_name: Optional[str] = None,
) -> str:
    """Buyurtma kartasi (ijrochilarga yuboriladigan matn)."""
    category = clean(category_name, 64) if category_name else "➕ Boshqa"
    skill = clean(skill_name or order.get("skill_name"), 64) or "Erkin yo'nalish"
    description = clean(order.get("description"), 1500) or "—"
    budget = clean(order.get("budget"), 100) or "—"
    deadline = clean(order.get("deadline"), 100) or "—"
    return (
        "🆕 <b>Yangi buyurtma!</b>\n"
        "\n"
        f"📂 <b>Soha:</b> {category}\n"
        f"🛠 <b>Yo'nalish:</b> {skill}\n"
        "\n"
        f"📝 <b>Vazifa:</b>\n{description}\n"
        "\n"
        f"💰 <b>Byudjet:</b> {budget}\n"
        f"⏳ <b>Muddat:</b> {deadline}\n"
        "\n"
        "✅ Qabul qilish uchun quyidagi tugmani bosing"
    )


def format_order_short(order: dict) -> str:
    """Buyurtmalar ro'yxati uchun qisqa satr."""
    return (
        f"{STATUS_EMOJI.get(order.get('status'), '❓')} <b>#{order.get('id')}</b> · "
        f"{clean(order.get('skill_name'), 48) or '—'} · "
        f"💰 {clean(order.get('budget'), 30) or '—'} · "
        f"<i>{status_label(order.get('status', ''))}</i>"
    )

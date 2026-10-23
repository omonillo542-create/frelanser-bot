"""Inline klaviaturalar (sahifalash bilan).

Callback data qoidalari:
  * har doim qisqa prefiks + ID (64 baytdan oshmasin)
  * nomlar emas, faqat ID'lar ishlatiladi
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import PAGINATION_SIZE


# ---------------------------------------------------------------- yordamchilar
def paginate(items: Sequence[Any], page: int, per_page: int = PAGINATION_SIZE):
    """(sahifa elementlari, joriy sahifa, sahifalar soni) qaytaradi."""
    total = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    return chunk, page, total


def _nav_row(prefix: str, page: int, total: int, extra: str = "") -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}{page - 1}{extra}"))
    if page < total - 1:
        row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}{page + 1}{extra}"))
    return row


# ---------------------------------------------------------------- rol menyulari
def role_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👷 Men ijrochiman", callback_data="role:executor"))
    kb.row(InlineKeyboardButton(text="📝 Men buyurtmachiman", callback_data="role:customer"))
    return kb.as_markup()


def main_menu_keyboard(role: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if role == "executor":
        kb.row(InlineKeyboardButton(text="⚙️ Yo'nalishlarim", callback_data="ex_myskills"))
        kb.row(InlineKeyboardButton(text="📨 Buyurtmalarim", callback_data="my_ord"))
    else:
        kb.row(InlineKeyboardButton(text="📝 Buyurtma berish", callback_data="ct_new"))
        kb.row(InlineKeyboardButton(text="📨 Buyurtmalarim", callback_data="my_ord"))
    kb.row(InlineKeyboardButton(text="👤 Profilim", callback_data="profile"))
    kb.row(InlineKeyboardButton(text="🔄 Rolni almashtirish", callback_data="rmenu"))
    return kb.as_markup()


def home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="home")


# ---------------------------------------------------------------- executor
def ex_categories_keyboard(categories: Sequence[dict], page: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.row(InlineKeyboardButton(text=cat["name"], callback_data=f"ex_cat:{cat['id']}"))
    nav = _nav_row("ex_pg:", page, total)
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="✅ Tayyor", callback_data="ex_done"))
    return kb.as_markup()


def ex_skills_keyboard(
    skills: Sequence[dict],
    selected_ids: Iterable[int],
    category_id: int,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    selected = set(int(i) for i in selected_ids)
    kb = InlineKeyboardBuilder()
    for skill in skills:
        mark = "✅ " if int(skill["id"]) in selected else ""
        kb.row(
            InlineKeyboardButton(
                text=f"{mark}{skill['name']}",
                callback_data=f"ex_tog:{skill['id']}:{page}",
            )
        )
    nav = _nav_row("ex_pgsk:", page, total, extra=f":{category_id}")
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="✅ Tayyor", callback_data="ex_done"))
    kb.row(InlineKeyboardButton(text="⬅️ Sohalar", callback_data="ex_backcat"))
    return kb.as_markup()


def ex_skills_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Yo'nalishlarni tahrirlash", callback_data="ex_edit"))
    kb.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="home"))
    return kb.as_markup()


# ---------------------------------------------------------------- customer
def ct_categories_keyboard(categories: Sequence[dict], page: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.row(InlineKeyboardButton(text=cat["name"], callback_data=f"ct_cat:{cat['id']}"))
    nav = _nav_row("ct_pg:", page, total)
    if nav:
        kb.row(*nav)
    return kb.as_markup()


def ct_skills_keyboard(
    skills: Sequence[dict],
    selected_id: Optional[int],
    category_id: int,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for skill in skills:
        mark = "🎯 " if selected_id is not None and int(skill["id"]) == int(selected_id) else ""
        kb.row(
            InlineKeyboardButton(
                text=f"{mark}{skill['name']}",
                callback_data=f"ct_tog:{skill['id']}:{page}",
            )
        )
    nav = _nav_row("ct_pgsk:", page, total, extra=f":{category_id}")
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="➡️ Davom etish", callback_data="ct_next"))
    kb.row(InlineKeyboardButton(text="⬅️ Sohalar", callback_data="ct_backcat"))
    return kb.as_markup()


def ct_confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Yuborish", callback_data="ct_send"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ct_cancel"))
    return kb.as_markup()


# ---------------------------------------------------------------- buyurtma tugmalari
def accept_keyboard(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Qabul qilaman", callback_data=f"acc:{order_id}"))
    kb.row(InlineKeyboardButton(text="⚠️ Shikoyat qilish", callback_data=f"compl:{order_id}"))
    return kb.as_markup()


def relay_link(bot_username: str, order_id: int, role: str) -> str:
    """role: 'e' — ijrochi, 'c' — buyurtmachi."""
    return f"https://t.me/{bot_username}?start=r{order_id}_{role}"


def contact_keyboard(
    order_id: int, target_username: Optional[str], role: str, bot_username: str
) -> InlineKeyboardMarkup:
    """'role' — bu foydalanuvchining roli (u qaysi tomondan yozadi)."""
    kb = InlineKeyboardBuilder()
    if target_username:
        kb.row(InlineKeyboardButton(text="💬 Xabar yozish", url=f"https://t.me/{target_username}"))
    else:
        kb.row(
            InlineKeyboardButton(
                text="✉️ Bot orqali yozish",
                url=relay_link(bot_username, order_id, role),
            )
        )
    kb.row(InlineKeyboardButton(text="⚠️ Shikoyat qilish", callback_data=f"compl:{order_id}"))
    return kb.as_markup()


def customer_order_keyboard(
    order_id: int, executor_username: Optional[str], bot_username: str
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Ish tugadi", callback_data=f"done:{order_id}"))
    if executor_username:
        kb.row(InlineKeyboardButton(text="💬 Xabar yozish", url=f"https://t.me/{executor_username}"))
    else:
        kb.row(
            InlineKeyboardButton(
                text="✉️ Bot orqali yozish",
                url=relay_link(bot_username, order_id, "c"),
            )
        )
    kb.row(InlineKeyboardButton(text="⚠️ Shikoyat qilish", callback_data=f"compl:{order_id}"))
    return kb.as_markup()


def executor_order_keyboard(
    order_id: int, customer_username: Optional[str], bot_username: str
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if customer_username:
        kb.row(InlineKeyboardButton(text="💬 Xabar yozish", url=f"https://t.me/{customer_username}"))
    else:
        kb.row(
            InlineKeyboardButton(
                text="✉️ Bot orqali yozish",
                url=relay_link(bot_username, order_id, "e"),
            )
        )
    kb.row(InlineKeyboardButton(text="⚠️ Shikoyat qilish", callback_data=f"compl:{order_id}"))
    return kb.as_markup()


def rate_keyboard(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        *[
            InlineKeyboardButton(text=f"{i}⭐", callback_data=f"rate:{order_id}:{i}")
            for i in range(1, 6)
        ]
    )
    return kb.as_markup()


def timeout_keyboard(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔁 Qayta yuborish", callback_data=f"rsend:{order_id}"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"canc:{order_id}"))
    return kb.as_markup()


# ---------------------------------------------------------------- admin
def admin_broadcast_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📣 Yuborish", callback_data="ad_bc_send"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ad_bc_cancel"))
    return kb.as_markup()


def admin_dispatch_keyboard(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📣 Eksecutorlarga yuborish", callback_data=f"ad_disp:{order_id}"))
    return kb.as_markup()


def admin_mute_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔇 Bloklash", callback_data=f"ad_mute:{user_id}"))
    return kb.as_markup()

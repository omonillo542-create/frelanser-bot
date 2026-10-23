"""Admin buyruqlari: /stats, /broadcast, /addskill, /complaints, /orders."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import config
from bot.database import db
from bot.keyboards import admin_broadcast_keyboard
from bot.states import AdminStates
from bot.utils import clean, ensure_user, safe_answer, safe_edit, safe_send, status_label

log = logging.getLogger(__name__)

router = Router(name="admin")


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user) and user.id == config.ADMIN_ID and config.ADMIN_ID != 0


admin_filter = IsAdmin()


# ==================================================================
#  /stats
# ==================================================================
@router.message(Command("stats"), admin_filter)
async def cmd_stats(message: Message) -> None:
    try:
        users = await db.count_users()
        executors = await db.count_users_by_role(config.ROLE_EXECUTOR)
        customers = await db.count_users_by_role(config.ROLE_CUSTOMER)
        orders = await db.count_orders()
        by_status = await db.count_orders_by_status()
        ratings = await db.count_ratings()
        avg = await db.get_average_rating()
        categories = await db.get_categories()
        skills = await db.get_skills_all()

        text = (
            "📊 <b>Statistika</b>\n"
            "\n"
            f"👥 Foydalanuvchilar: <b>{users}</b>\n"
            f"👷 Ijrochilar: <b>{executors}</b>\n"
            f"📝 Buyurtmachilar: <b>{customers}</b>\n"
            "\n"
            f"📦 Buyurtmalar: <b>{orders}</b>\n"
            f"   🔄 Kutmoqda: {by_status.get('open', 0)}\n"
            f"   🔧 Bajarilmoqda: {by_status.get('taken', 0)}\n"
            f"   ✅ Bajarildi: {by_status.get('done', 0)}\n"
            f"   ❌ Bekor qilindi: {by_status.get('cancelled', 0)}\n"
            "\n"
            f"⭐ Baholar: <b>{ratings}</b> (o'rtacha {avg:.2f})\n"
            f"🗂 Sohalar: {len(categories)} · Yo'nalishlar: {skills}"
        )
        await message.answer(text)
    except Exception as exc:
        log.exception("/stats xatosi: %s", exc)
        await message.answer("😔 Statistikani olishda xatolik.")


# ==================================================================
#  /broadcast
# ==================================================================
@router.message(Command("broadcast"), admin_filter)
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").split(maxsplit=1)
        if len(text) > 1 and text[1].strip():
            await broadcast_to_all(message.bot, text[1].strip())
            return

        await state.set_state(AdminStates.broadcast)
        await message.answer(
            "📣 <b>Broadcast matnini yozing</b>\n\n"
            "Yuboriladigan xabar barcha foydalanuvchilarga yetkaziladi."
        )
    except Exception as exc:
        log.exception("/broadcast xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(AdminStates.broadcast)
async def broadcast_state(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text:
            await message.answer("📣 Matnni yozing (bo'sh bo'lmasin).")
            return
        await state.update_data(ad_bc_text=text)
        await message.answer(
            "📣 <b>Tasdiqlang</b>\n\n"
            f"{clean(text, 900)}\n\n"
            "Bu xabar barcha foydalanuvchilarga yuboriladi.",
            reply_markup=admin_broadcast_keyboard(),
        )
    except Exception as exc:
        log.exception("Broadcast xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


async def broadcast_to_all(bot, text: str) -> None:
    user_ids = await db.get_all_user_ids()
    sent = 0
    failed = 0
    for index, user_id in enumerate(user_ids, start=1):
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception as exc:
            failed += 1
            log.debug("Broadcast yuborilmadi (%s): %s", user_id, exc)
        if index % 50 == 0:
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(config.SEND_DELAY)
    if config.ADMIN_ID:
        await bot.send_message(
            config.ADMIN_ID,
            f"✅ Broadcast yakunlandi.\n\n📤 Yuborildi: <b>{sent}</b>\n❌ Yuborilmadi: <b>{failed}</b>",
        )


@router.callback_query(F.data == "ad_bc_send", IsAdmin())
async def broadcast_confirm(call: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        text = (data.get("ad_bc_text") or "").strip()
        if not text:
            await safe_answer(call, "Matn topilmadi", show_alert=True)
            return
        await state.clear()
        await safe_answer(call, "📣 Yuborilmoqda...")
        await broadcast_to_all(call.bot, text)
    except Exception as exc:
        log.exception("Broadcast yuborish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "ad_bc_cancel", IsAdmin())
async def broadcast_cancel(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await state.clear()
        await safe_answer(call, "❌ Bekor qilindi")
        await safe_edit(call, text="❌ Broadcast bekor qilindi.")
    except Exception as exc:
        log.exception("Broadcast bekor qilish xatosi: %s", exc)


# ==================================================================
#  /addskill
# ==================================================================
@router.message(Command("addskill"), admin_filter)
async def cmd_addskill(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").split(maxsplit=1)
        if len(text) > 1 and "|" in text[1]:
            raw_cat, raw_skill = text[1].split("|", 1)
            await add_skill(raw_cat.strip(), raw_skill.strip(), message)
            return

        await state.set_state(AdminStates.addskill_category)
        await state.update_data(ad_skill_text=None)
        await message.answer(
            "🗂 <b>Yangi soha nomini yozing</b>\n\n"
            "Masalan: <code>🎬 Video va audio</code> (mavjud bo'lsa — o'shandan foydalaniladi)"
        )
    except Exception as exc:
        log.exception("/addskill xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(AdminStates.addskill_category)
async def addskill_category(message: Message, state: FSMContext) -> None:
    try:
        name = (message.text or "").strip()
        if not name:
            await message.answer("🗂 Soha nomini yozing.")
            return
        await state.update_data(ad_skill_text=None, ad_cat_text=name)
        await state.set_state(AdminStates.addskill_skill)
        await message.answer(
            "🛠 <b>Yo'nalish nomini yozing</b>\n\n"
            f"Soha: <b>{clean(name, 60)}</b>\n"
            "Masalan: <code>Reels/TikTok/Shorts</code>"
        )
    except Exception as exc:
        log.exception("Soha qo'shish xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(AdminStates.addskill_skill)
async def addskill_skill(message: Message, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        category = (data.get("ad_cat_text") or "").strip()
        skill = (message.text or "").strip()
        if not skill:
            await message.answer("🛠 Yo'nalish nomini yozing.")
            return
        await state.clear()
        await add_skill(category, skill, message)
    except Exception as exc:
        log.exception("Yo'nalish qo'shish xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


async def add_skill(category_name: str, skill_name: str, message: Message) -> None:
    """Sohani (yoki yo'nalishni) bazaga qo'shadi."""
    if not category_name or not skill_name:
        await message.answer("😔 Soha va yo'nalish nomi bo'sh bo'lmasin.")
        return

    category = await db.get_category_by_name(category_name)
    if category:
        category_id = int(category["id"])
        created_cat = False
    else:
        category_id = await db.get_or_create_category(category_name)
        created_cat = True

    skill = await db.get_skill(category_id)
    existing = None
    for item in await db.get_skills(category_id):
        if item["name"].lower() == skill_name.lower():
            existing = item
            break

    if existing:
        await message.answer(
            f"ℹ️ Bu yo'nalish allaqachon mavjud:\n"
            f"📂 {clean(category_name, 60)} → 🛠 {clean(existing['name'], 60)}"
        )
        return

    await db.get_or_create_skill(category_id, skill_name)
    await message.answer(
        "✅ <b>Qo'shildi!</b>\n\n"
        f"📂 Soha: {clean(category_name, 60)}\n"
        f"🛠 Yo'nalish: {clean(skill_name, 60)}"
        + ("\n\n<i>(Yangi soha yaratildi)</i>" if created_cat else "")
    )


# ==================================================================
#  Qo'shimcha: buyurtmalar va shikoyatlar
# ==================================================================
@router.message(Command("orders"), admin_filter)
async def cmd_orders(message: Message) -> None:
    try:
        orders = await db.get_last_orders(10)
        if not orders:
            await message.answer("📦 Buyurtma yo'q.")
            return
        lines = []
        for order in orders:
            lines.append(
                f"#{order['id']} · {clean(order.get('skill_name'), 40)} · "
                f"💰 {clean(order.get('budget'), 24)} · {status_label(order.get('status', ''))}"
            )
        await message.answer("📦 <b>Oxirgi buyurtmalar</b>\n\n" + "\n".join(lines))
    except Exception as exc:
        log.exception("/orders xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(Command("complaints"), admin_filter)
async def cmd_complaints(message: Message) -> None:
    try:
        complaints = await db.get_last_complaints(10)
        if not complaints:
            await message.answer("✅ Shikoyat yo'q.")
            return
        lines = []
        for c in complaints:
            lines.append(
                f"🆕 #{c['id']} · 👤 {c['user_id']} · 🛒 #{c['order_id']}\n"
                f"   {clean(c['text'], 200)}"
            )
        await message.answer("⚠️ <b>Shikoyatlar</b>\n\n" + "\n\n".join(lines))
    except Exception as exc:
        log.exception("/complaints xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.callback_query(F.data.startswith("ad_disp:"))
async def admin_dispatch(call: CallbackQuery) -> None:
    try:
        if call.from_user.id != config.ADMIN_ID:
            await safe_answer(call, "Faqat admin", show_alert=True)
            return
        order_id = int(call.data.split(":")[1])
        order = await db.get_order(order_id)
        if not order:
            await safe_answer(call, "Buyurtma topilmadi", show_alert=True)
            return
        if order["status"] != "open":
            await safe_answer(call, "Bu buyurtma allaqachon olindi", show_alert=True)
            return

        from bot.services.dispatcher import dispatch_order

        sent = await dispatch_order(call.bot, order, all_executors=True)
        await safe_answer(call, f"📣 {sent} ta ijrochiga yuborildi")
        await safe_edit(
            call,
            text=(
                f"📣 Buyurtma #{order_id} <b>{sent}</b> ta ijrochiga yuborildi."
                if sent
                else f"😔 Buyurtma #{order_id} uchun faol ijrochi topilmadi."
            ),
        )
        await safe_send(
            call.bot,
            int(order["customer_id"]),
            f"🔔 Buyurtma #{order_id} qayta tarqatildi ({sent} ta ijrochi ogohlantirildi).",
        )
    except Exception as exc:
        log.exception("Admin tarqatish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ad_mute:"))
async def admin_mute(call: CallbackQuery) -> None:
    try:
        if call.from_user.id != config.ADMIN_ID:
            await safe_answer(call, "Faqat admin", show_alert=True)
            return
        user_id = int(call.data.split(":")[1])
        await db.deactivate_user(user_id)
        await safe_answer(call, "🔇 Foydalanuvchi bloklandi")
        await safe_edit(call, text="🔇 Foydalanuvchi bloklandi (bot xabarlari to'xtatildi).")
        await safe_send(call.bot, user_id, "🔇 Siz bot xabarlarini olmay qolingiz.")
    except Exception as exc:
        log.exception("Bloklash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


# ==================================================================
#  Admin panel menyusi
# ==================================================================
@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    try:
        if message.from_user.id != config.ADMIN_ID:
            await message.answer("⛔ Bu buyruq faqat admin uchun.")
            return
        await message.answer(
            "🛠 <b>Admin panel</b>\n\n"
            "• /stats — statistika\n"
            "• /broadcast — hamma foydalanuvchiga xabar\n"
            "• /addskill — yangi soha/yo'nalish qo'shish\n"
            "• /orders — oxirgi buyurtmalar\n"
            "• /complaints — shikoyatlar"
        )
    except Exception as exc:
        log.exception("/admin xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")

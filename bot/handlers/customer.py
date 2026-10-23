"""Buyurtmachi oqimi: soha → yo'nalish → vazifa → byudjet → muddat → tasdiqlash."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import config
from bot.database import db
from bot.keyboards import (
    ct_categories_keyboard,
    ct_confirm_keyboard,
    ct_skills_keyboard,
    paginate,
)
from bot.states import CustomerStates
from bot.utils import (
    EMPTY_MARKUP,
    NO_CATEGORY,
    clean,
    ensure_user,
    safe_answer,
    safe_edit,
    safe_send,
)

log = logging.getLogger(__name__)

router = Router(name="customer")


async def start_order_flow(message: Message, state: FSMContext, edit: bool = False) -> None:
    """Buyurtma berish oqimini boshlaydi."""
    try:
        await state.set_state(CustomerStates.choose_category)
        await state.update_data(
            ct_skill_id=None,
            ct_skill_name=None,
            ct_category_id=0,
            ct_category_name=None,
        )

        categories = await db.get_categories()
        items, page, total = paginate(categories, 0)

        await message.answer(
            "📂 <b>Buyurtma berish</b>\n\n"
            "Avval sohani tanlang 👇\n"
            "<i>Ro'yxatda yo'q yo'nalish kerak bo'lsa — «➕ Boshqa» ni tanlang.",
            reply_markup=ct_categories_keyboard(items, page, total),
        )
    except Exception as exc:
        log.exception("Buyurtma oqimini boshlash xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi. /menu bosing.")


@router.callback_query(F.data == "ct_new")
async def new_order(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await safe_answer(call)
        await start_order_flow(call.message, state, edit=True)
    except Exception as exc:
        log.exception("Yangi buyurtma xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ct_pg:"))
async def categories_page(call: CallbackQuery, state: FSMContext) -> None:
    try:
        page = int(call.data.split(":")[1])
        categories = await db.get_categories()
        items, page, total = paginate(categories, page)
        await state.set_state(CustomerStates.choose_category)
        await safe_answer(call)
        await safe_edit(
            call,
            text="📂 <b>Buyurtma berish</b>\n\nSohani tanlang 👇",
            reply_markup=ct_categories_keyboard(items, page, total),
        )
    except Exception as exc:
        log.exception("Sohalar sahifasi xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ct_cat:"))
async def pick_category(call: CallbackQuery, state: FSMContext) -> None:
    try:
        category_id = int(call.data.split(":")[1])
        category = await db.get_category(category_id)
        if not category:
            await safe_answer(call, "Soha topilmadi", show_alert=True)
            return

        await state.update_data(
            ct_category_id=category_id,
            ct_category_name=category["name"],
            ct_skill_id=None,
            ct_skill_name=None,
        )

        # "Boshqa" — ro'yxatda yo'q yo'nalish
        if category["name"] == config.CUSTOM_CATEGORY_NAME:
            await state.set_state(CustomerStates.custom_skill)
            await safe_answer(call)
            await safe_edit(call, text="✍️ <b>Yo'nalishni o'zingiz yozing</b>")
            await call.message.answer(
                "✍️ Kerakli yo'nalishni yozing.\n\n"
                "Masalan: <code>3D vizualizatsiya</code>, <code>Telegram bot + admin panel</code>",
            )
            return

        skills = await db.get_skills(category_id)
        if not skills:
            await safe_answer(call, "Bu sohada yo'nalish yo'q", show_alert=True)
            return

        items, page, total = paginate(skills, 0)
        await state.set_state(CustomerStates.choose_skill)
        await state.update_data(ct_skpage=page)

        await safe_answer(call)
        await safe_edit(
            call,
            text=(
                f"📂 <b>{clean(category['name'], 60)}</b>\n\n"
                "🛠 Yo'nalishni tanlang (🎯 — tanlangan):"
            ),
            reply_markup=ct_skills_keyboard(items, None, category_id, page, total),
        )
    except Exception as exc:
        log.exception("Soha tanlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ct_pgsk:"))
async def skills_page(call: CallbackQuery, state: FSMContext) -> None:
    try:
        _, category_id, page = call.data.split(":")
        category_id = int(category_id)
        page = int(page)
        category = await db.get_category(category_id)
        if not category:
            await safe_answer(call, "Soha topilmadi", show_alert=True)
            return

        data = await state.get_data()
        selected = data.get("ct_skill_id")
        skills = await db.get_skills(category_id)
        items, page, total = paginate(skills, page)

        await state.set_state(CustomerStates.choose_skill)
        await safe_answer(call)
        await safe_edit(
            call,
            text=(
                f"📂 <b>{clean(category['name'], 60)}</b>\n\n"
                "🛠 Yo'nalishni tanlang (🎯 — tanlangan):"
            ),
            reply_markup=ct_skills_keyboard(items, selected, category_id, page, total),
        )
    except Exception as exc:
        log.exception("Yo'nalishlar sahifasi xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ct_tog:"))
async def toggle_skill(call: CallbackQuery, state: FSMContext) -> None:
    try:
        parts = call.data.split(":")
        skill_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0

        data = await state.get_data()
        category_id = int(data.get("ct_category_id") or 0)
        category = await db.get_category(category_id) if category_id else None
        skill = await db.get_skill(skill_id)

        await state.update_data(
            ct_skill_id=skill_id,
            ct_skill_name=skill["name"] if skill else None,
        )

        skills = await db.get_skills(category_id) if category_id else []
        items, page, total = paginate(skills, page)
        cat_title = clean(category['name'], 60) if category else NO_CATEGORY

        await state.set_state(CustomerStates.choose_skill)
        await safe_answer(call, "🎯 Tanlandi")
        await safe_edit(
            call,
            text=(
                f"📂 <b>{cat_title}</b>\n\n"
                "🛠 Yo'nalishni tanlang (🎯 — tanlangan):"
            ),
            reply_markup=ct_skills_keyboard(items, skill_id, category_id, page, total),
        )
    except Exception as exc:
        log.exception("Yo'nalishni tanlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "ct_next")
async def to_description(call: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        if not data.get("ct_skill_id") and not data.get("ct_skill_name"):
            await safe_answer(call, "Avval yo'nalishni tanlang 🙂", show_alert=True)
            return

        await state.set_state(CustomerStates.description)
        await safe_answer(call)
        await safe_edit(
            call,
            text=(
                f"📂 Soha: {clean(data.get('ct_category_name'), 60)}\n"
                f"🛠 Yo'nalish: {clean(data.get('ct_skill_name'), 60)}\n\n"
                "Endi vazifani yozing 👇"
            ),
            reply_markup=EMPTY_MARKUP,
        )
        await call.message.answer(
            "📝 <b>Vazifani yozing</b>\n\n"
            "Nima qilish kerakligini aniq yozing (natija, hajm, muddat kabi).",
        )
    except Exception as exc:
        log.exception("Vazifaga o'tish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.message(CustomerStates.custom_skill)
async def custom_skill_text(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text:
            await message.answer("✍️ Yo'nalish nomini yozing.")
            return
        await state.update_data(ct_skill_name=text, ct_skill_id=None, ct_is_custom=True)
        await state.set_state(CustomerStates.description)
        await message.answer(
            f"🛠 Yo'nalish: <b>{clean(text, 60)}</b>\n\n"
            "📝 <b>Vazifani yozing</b>\n\nNima qilish kerakligini aniq yozing."
        )
    except Exception as exc:
        log.exception("Maxsus yo'nalish xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(CustomerStates.description)
async def get_description(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text:
            await message.answer("📝 Vazifani yozing (bo'sh bo'lmasin).")
            return
        await state.update_data(ct_description=text)
        await state.set_state(CustomerStates.budget)
        await message.answer(
            "💰 <b>Byudjetni yozing</b>\n\n"
            "Masalan: <code>100$</code>, <code>2 000 000 so'm</code> yoki <code>Kelishiladi</code>"
        )
    except Exception as exc:
        log.exception("Vazifa xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(CustomerStates.budget)
async def get_budget(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text:
            await message.answer("💰 Byudjetni yozing (yoki <code>Kelishiladi</code>).")
            return
        await state.update_data(ct_budget=text)
        await state.set_state(CustomerStates.deadline)
        await message.answer(
            "⏳ <b>Muddatni yozing</b>\n\n"
            "Masalan: <code>3 kun</code>, <code>bugun</code>, <code>1 hafta</code>"
        )
    except Exception as exc:
        log.exception("Byudjet xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(CustomerStates.deadline)
async def get_deadline(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text:
            await message.answer("⏳ Muddatni yozing.")
            return

        data = await state.get_data()
        data.update({"ct_deadline": text})
        await state.update_data(**data)
        await state.set_state(CustomerStates.confirm)

        confirm_text = (
            "🧾 <b>Buyurtmani tasdiqlang</b>\n"
            "\n"
            f"📂 <b>Soha:</b> {clean(data.get('ct_category_name'), 60)}\n"
            f"🛠 <b>Yo'nalish:</b> {clean(data.get('ct_skill_name'), 60)}\n"
            "\n"
            f"📝 <b>Vazifa:</b>\n{clean(data.get('ct_description'), 1200)}\n"
            "\n"
            f"💰 <b>Byudjet:</b> {clean(data.get('ct_budget'), 60)}\n"
            f"⏳ <b>Muddat:</b> {clean(data.get('ct_deadline'), 60)}\n"
            "\n"
            "Hammasi to'g'rimi? Tasdiqlang 👇"
        )
        sent = await message.answer(confirm_text, reply_markup=ct_confirm_keyboard())
        await state.update_data(ct_msg_id=sent.message_id if sent else None)
    except Exception as exc:
        log.exception("Muddat xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.callback_query(F.data == "ct_send")
async def send_order(call: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        description = (data.get("ct_description") or "").strip()
        budget = (data.get("ct_budget") or "").strip()
        deadline = (data.get("ct_deadline") or "").strip()
        skill_name = (data.get("ct_skill_name") or "").strip()
        skill_id = data.get("ct_skill_id")
        category_name = data.get("ct_category_name") or config.CUSTOM_CATEGORY_NAME

        if not description or not budget or not deadline or not skill_name:
            await safe_answer(call, "Ma'lumotlar to'liq emas, oqimni qaytadan boshlang", show_alert=True)
            return

        # --- kunlik limit ---
        today_count = await db.count_today_orders(call.from_user.id)
        if today_count >= config.DAILY_ORDER_LIMIT:
            await state.clear()
            await safe_answer(
                call,
                f"Kunlik limit: {config.DAILY_ORDER_LIMIT} ta buyurtma. Erta ulguradi!",
                show_alert=True,
            )
            await call.message.answer(
                f"🚫 <b>Kunlik limitga yetdingiz</b>\n\n"
                f"Bir kunda ko'pi bilan <b>{config.DAILY_ORDER_LIMIT}</b> ta buyurtma berishingiz mumkin.\n"
                "Ertaga yana urinib ko'ring!"
            )
            return

        is_custom = skill_id is None
        order_id = await db.create_order(
            customer_id=call.from_user.id,
            skill_id=skill_id,
            skill_name=skill_name,
            description=description,
            budget=budget,
            deadline=deadline,
            is_custom=is_custom,
        )

        msg_id = data.get("ct_msg_id")
        if msg_id:
            await db.set_order_customer_message(order_id, call.message.chat.id, int(msg_id))

        order = await db.get_order(order_id)
        await state.clear()
        await safe_answer(call, "✅ Buyurtma yuborildi!")

        await safe_edit(
            call,
            text=(
                f"🆕 <b>Buyurtma #{order_id} yuborildi!</b>\n\n"
                f"📂 Soha: {clean(category_name, 60)}\n"
                f"🛠 Yo'nalish: {clean(skill_name, 60)}\n"
                f"💰 Byudjet: {clean(budget, 60)}\n"
                f"⏳ Muddat: {clean(deadline, 60)}\n\n"
                "🔔 Mos ijrochilarga xabar yuborildi, javobni kutamiz."
            ),
            reply_markup=EMPTY_MARKUP,
        )

        from bot.services.dispatcher import dispatch_order, notify_admin_order

        if is_custom:
            await notify_admin_order(call.bot, order, custom=True)
            await safe_send(
                call.bot,
                call.from_user.id,
                "📨 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
                "Bu yo'nalish ro'yxatda yo'q — buyurtmangiz admin'ga yuborildi. "
                "Biz mos ijrochi topib beramiz ⏳",
            )
        else:
            sent_count = await dispatch_order(call.bot, order)
            if sent_count > 0:
                await safe_send(
                    call.bot,
                    call.from_user.id,
                    f"🔔 <b>Buyurtma #{order_id} yuborildi!</b>\n\n"
                    f"{sent_count} ta ijrochi ogohlantirildi. "
                    "Birinchi bo'lib qabul qilgan ijrochi buyurtmani oladi ✅",
                )
            else:
                await safe_send(
                    call.bot,
                    call.from_user.id,
                    f"😔 <b>Hozircha bu yo'nalishda ijrochi yo'q</b>\n\n"
                    f"Buyurtma #{order_id} admin'ga yuborildi — biz mos ijrochi topamiz ⏳",
                )
            if config.ADMIN_NOTIFY_ALL:
                await notify_admin_order(call.bot, order)
    except Exception as exc:
        log.exception("Buyurtmani yuborish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)
        try:
            await state.clear()
        except Exception:
            pass


@router.callback_query(F.data == "ct_cancel")
async def cancel_order(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await state.clear()
        await safe_answer(call, "❌ Bekor qilindi")
        await safe_edit(call, text="❌ Buyurtma bekor qilindi.", reply_markup=EMPTY_MARKUP)
    except Exception as exc:
        log.exception("Bekor qilish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)

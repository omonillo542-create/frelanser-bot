"""Ijrochi oqimi: soha → yo'nalishlar (ko'p tanlash mumkin) → saqlash."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import db
from bot.keyboards import (
    ex_categories_keyboard,
    ex_skills_keyboard,
    ex_skills_menu_keyboard,
    paginate,
)
from bot.states import ExecutorStates
from bot.utils import EMPTY_MARKUP, NO_CATEGORY, clean, ensure_user, safe_answer, safe_edit

log = logging.getLogger(__name__)

router = Router(name="executor")


async def start_skill_selection(
    message: Message, state: FSMContext, edit: bool = False
) -> None:
    """Yo'nalish tanlashni boshlaydi (yangi yoki tahrirlash)."""
    try:
        user = await ensure_user(message.from_user)
        selected = await db.get_executor_skill_ids(user["user_id"])

        await state.set_state(ExecutorStates.choose_category)
        await state.update_data(ex_selected=selected, ex_catpage=0, ex_catid=0)

        categories = await db.get_categories_with_skills()
        items, page, total = paginate(categories, 0)

        text = (
            "🛠 <b>Yo'nalish tanlang</b>\n\n"
            "Sohani tanlang, keyin undan kasb/yo'nalishni tanlang.\n"
            "Bir nechta yo'nalish tanlash mumkin ✅ belgisi bilan ko'rsatiladi.\n"
            "Tayyor bo'lganda <b>✅ Tayyor</b> tugmasini bosing."
        )
        keyboard = ex_categories_keyboard(items, page, total)
        await message.answer(text, reply_markup=keyboard)
    except Exception as exc:
        log.exception("Yo'nalish tanlashni boshlash xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi. /menu bosing.")


@router.callback_query(F.data == "ex_myskills")
async def my_skills(call: CallbackQuery, state: FSMContext) -> None:
    try:
        user = await ensure_user(call.from_user)
        skills = await db.get_executor_skills(user["user_id"])
        if skills:
            lines = "\n".join(
                f"• {clean(s['category_name'], 40)} → <b>{clean(s['skill_name'], 60)}</b>"
                for s in skills
            )
        else:
            lines = "Hozircha yo'nalish tanlanmagan 😔"

        await safe_answer(call)
        await state.set_state(ExecutorStates.choose_category)
        await state.update_data(
            ex_selected=[int(s["id"]) for s in skills],
            ex_catpage=0,
            ex_catid=0,
        )
        await call.message.answer(
            f"⚙️ <b>Yo'nalishlarim</b>\n\n{lines}\n\n"
            "O'zgartirish uchun quyidagi tugmani bosing 👇",
            reply_markup=ex_skills_menu_keyboard(),
        )
    except Exception as exc:
        log.exception("Yo'nalishlarim xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "ex_edit")
async def edit_skills(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await safe_answer(call)
        await start_skill_selection(call.message, state, edit=True)
    except Exception as exc:
        log.exception("ex_edit xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ex_pg:"))
async def categories_page(call: CallbackQuery, state: FSMContext) -> None:
    try:
        page = int(call.data.split(":")[1])
        categories = await db.get_categories_with_skills()
        items, page, total = paginate(categories, page)
        await state.update_data(ex_catpage=page)
        await safe_answer(call)
        await safe_edit(
            call,
            text="🛠 <b>Yo'nalish tanlang</b>\n\nSohani tanlang 👇",
            reply_markup=ex_categories_keyboard(items, page, total),
        )
    except Exception as exc:
        log.exception("Sohalar sahifasi xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ex_cat:"))
async def pick_category(call: CallbackQuery, state: FSMContext) -> None:
    try:
        category_id = int(call.data.split(":")[1])
        category = await db.get_category(category_id)
        if not category:
            await safe_answer(call, "Soha topilmadi", show_alert=True)
            return

        skills = await db.get_skills(category_id)
        if not skills:
            await safe_answer(call, "Bu sohada yo'nalish yo'q", show_alert=True)
            return

        data = await state.get_data()
        selected = [int(i) for i in data.get("ex_selected", [])]
        items, page, total = paginate(skills, 0)

        await state.set_state(ExecutorStates.choose_skill)
        await state.update_data(ex_catid=category_id, ex_skpage=page)

        await safe_answer(call)
        await safe_edit(
            call,
            text=(
                f"📂 <b>{clean(category['name'], 60)}</b>\n\n"
                "🛠 Yo'nalishni tanlang (✅ — tanlangan):"
            ),
            reply_markup=ex_skills_keyboard(items, selected, category_id, page, total),
        )
    except Exception as exc:
        log.exception("Soha tanlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ex_pgsk:"))
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
        selected = [int(i) for i in data.get("ex_selected", [])]
        skills = await db.get_skills(category_id)
        items, page, total = paginate(skills, page)

        await state.set_state(ExecutorStates.choose_skill)
        await state.update_data(ex_catid=category_id, ex_skpage=page)

        await safe_answer(call)
        await safe_edit(
            call,
            text=(
                f"📂 <b>{clean(category['name'], 60)}</b>\n\n"
                "🛠 Yo'nalishni tanlang (✅ — tanlangan):"
            ),
            reply_markup=ex_skills_keyboard(items, selected, category_id, page, total),
        )
    except Exception as exc:
        log.exception("Yo'nalishlar sahifasi xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("ex_tog:"))
async def toggle_skill(call: CallbackQuery, state: FSMContext) -> None:
    try:
        parts = call.data.split(":")
        skill_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0

        data = await state.get_data()
        selected = [int(i) for i in data.get("ex_selected", [])]
        if not selected:
            selected = await db.get_executor_skill_ids(call.from_user.id)

        if skill_id in selected:
            selected.remove(skill_id)
            action = "➖ O'chirildi"
        else:
            selected.append(skill_id)
            action = "✅ Tanlandi"

        await state.update_data(ex_selected=selected)

        category_id = int(data.get("ex_catid") or 0)
        category = await db.get_category(category_id) if category_id else None
        skills = await db.get_skills(category_id) if category_id else []
        items, page, total = paginate(skills, page)
        cat_title = clean(category['name'], 60) if category else NO_CATEGORY

        await state.set_state(ExecutorStates.choose_skill)
        await safe_answer(call, action)
        await safe_edit(
            call,
            text=(
                f"📂 <b>{cat_title}</b>\n\n"
                "🛠 Yo'nalishni tanlang (✅ — tanlangan):"
            ),
            reply_markup=ex_skills_keyboard(items, selected, category_id, page, total),
        )
    except Exception as exc:
        log.exception("Yo'nalishni tanlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "ex_backcat")
async def back_to_categories(call: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        page = int(data.get("ex_catpage") or 0)
        categories = await db.get_categories_with_skills()
        items, page, total = paginate(categories, page)

        await state.set_state(ExecutorStates.choose_category)
        await safe_answer(call)
        await safe_edit(
            call,
            text="🛠 <b>Yo'nalish tanlang</b>\n\nSohani tanlang 👇",
            reply_markup=ex_categories_keyboard(items, page, total),
        )
    except Exception as exc:
        log.exception("Sohalarga qaytish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "ex_done")
async def save_skills(call: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        selected = [int(i) for i in data.get("ex_selected", [])]

        if not selected:
            await safe_answer(call, "Kamida bitta yo'nalish tanlang 🙂", show_alert=True)
            return

        await db.set_executor_skills(call.from_user.id, selected)
        await state.clear()
        await safe_answer(call, "✅ Yo'nalishlar saqlandi")
        await safe_edit(
            call, text="✅ <b>Yo'nalishlar saqlandi!</b>", reply_markup=EMPTY_MARKUP
        )

        skills = await db.get_executor_skills(call.from_user.id)
        lines = "\n".join(
            f"• {clean(s['category_name'], 40)} → <b>{clean(s['skill_name'], 60)}</b>"
            for s in skills
        )
        await call.message.answer(
            f"✅ <b>Yo'nalishlaringiz saqlandi!</b>\n\n{lines}\n\n"
            "Endi sizga mos buyurtmalar yuboriladi 🔔",
            reply_markup=ex_skills_menu_keyboard(),
        )
    except Exception as exc:
        log.exception("Yo'nalishlarni saqlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)

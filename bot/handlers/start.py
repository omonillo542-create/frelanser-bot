"""/start, /menu, rol tanlash."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import config
from bot.keyboards import main_menu_keyboard, role_keyboard
from bot.states import RoleStates
from bot.utils import EMPTY_MARKUP, ensure_user, safe_answer, safe_edit

log = logging.getLogger(__name__)

router = Router(name="start")

WELCOME = (
    "🤝 <b>Frilans bozori botiga xush kelibsiz!</b>\n"
    "\n"
    "Bu bot buyurtmachi va ijrochini bog'laydi:\n"
    "• Siz ish qidiraysizmi yoki ish berasizmi?\n"
    "\n"
    "Rolni tanlang 👇"
)

HELP = (
    "ℹ️ <b>Yordam</b>\n"
    "\n"
    "<b>Buyurtmachi:</b> 📝 Buyurtma berish → soha → yo'nalish → vazifa → byudjet → muddat\n"
    "<b>Ijrochi:</b> ⚙️ Yo'nalishlarim → soha → yo'nalishlarni tanlang (ko'p tanlash mumkin)\n"
    "\n"
    "Buyurtma yuborilganda mos ijrochilarga xabar boradi. "
    "Birinchi bo'lib <b>✅ Qabul qilaman</b> tugmasini bosgan ijrochi buyurtmani oladi.\n"
    "\n"
    "Buyruqlar: /start /menu /profile /help"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    try:
        user = await ensure_user(message.from_user)

        payload = ""
        if message.text:
            parts = message.text.split(maxsplit=1)
            if len(parts) > 1:
                payload = parts[1].strip()

        # Bot orqali yozish (relay) havolalari
        if payload.startswith("r") and "_" in payload:
            from bot.handlers.orders import handle_relay_start

            await handle_relay_start(message, state, payload)
            return

        if user.get("role"):
            await state.clear()
            await message.answer(
                f"Salom, {user.get('full_name') or 'foydalanuvchi'}! 👋\n"
                "Quyidagi menyudan davom eting 👇",
                reply_markup=main_menu_keyboard(user["role"]),
            )
        else:
            await state.set_state(RoleStates.choosing)
            await message.answer(WELCOME, reply_markup=role_keyboard())
    except Exception as exc:
        log.exception("/start xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi. Iltimos, /start qayta bosing.")


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    try:
        user = await ensure_user(message.from_user)
        if not user.get("role"):
            await state.set_state(RoleStates.choosing)
            await message.answer(WELCOME, reply_markup=role_keyboard())
            return
        await state.clear()
        await message.answer(
            f"🏠 <b>Asosiy menyu</b>\n\n🎭 Rol: {config.ROLE_LABELS.get(user['role'], '—')}",
            reply_markup=main_menu_keyboard(user["role"]),
        )
    except Exception as exc:
        log.exception("/menu xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi. Iltimos, /menu qayta bosing.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    try:
        await message.answer(HELP)
    except Exception as exc:
        log.exception("/help xatosi: %s", exc)


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    try:
        from bot.handlers.orders import send_profile

        await send_profile(message)
    except Exception as exc:
        log.exception("/profile xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


# ---------------------------------------------------------------- rol tanlash
@router.callback_query(F.data.startswith("role:"))
async def choose_role(call: CallbackQuery, state: FSMContext) -> None:
    try:
        role = call.data.split(":", 1)[1]
        if role not in (config.ROLE_EXECUTOR, config.ROLE_CUSTOMER):
            await safe_answer(call, "Noma'lum rol", show_alert=True)
            return

        await db_set_role(call.from_user.id, role)
        await safe_answer(call, "✅ Rol saqlandi")
        await safe_edit(call, text=f"🎭 Rol: <b>{config.ROLE_LABELS[role]}</b>", reply_markup=EMPTY_MARKUP)

        if role == config.ROLE_EXECUTOR:
            from bot.handlers.executor import start_skill_selection

            await start_skill_selection(call.message, state, edit=False)
        else:
            from bot.handlers.customer import start_order_flow

            await start_order_flow(call.message, state, edit=False)
    except Exception as exc:
        log.exception("Rol tanlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


async def db_set_role(user_id: int, role: str) -> None:
    from bot.database import db

    await db.set_role(user_id, role)


# ---------------------------------------------------------------- menyu
@router.callback_query(F.data == "rmenu")
async def role_menu(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await safe_answer(call)
        await state.clear()
        await call.message.answer(
            "🔄 <b>Rolni almashtiring</b>\n\nIsh beruvchi yoki ijrochi sifatida davom eting:",
            reply_markup=role_keyboard(),
        )
    except Exception as exc:
        log.exception("rol menyu xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "home")
async def go_home(call: CallbackQuery, state: FSMContext) -> None:
    try:
        user = await ensure_user(call.from_user)
        await safe_answer(call)
        await state.clear()
        if not user.get("role"):
            await call.message.answer(WELCOME, reply_markup=role_keyboard())
            return
        await call.message.answer(
            f"🏠 <b>Asosiy menyu</b>\n\n🎭 Rol: {config.ROLE_LABELS.get(user['role'], '—')}",
            reply_markup=main_menu_keyboard(user["role"]),
        )
    except Exception as exc:
        log.exception("home xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)

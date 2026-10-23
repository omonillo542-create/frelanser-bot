"""Buyurtmalar: qabul qilish, muddat, yakunlash, baho, shikoyat, relay."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import config
from bot.database import db
from bot.keyboards import (
    contact_keyboard,
    customer_order_keyboard,
    executor_order_keyboard,
    main_menu_keyboard,
    rate_keyboard,
)
from bot.states import ComplaintStates, RelayStates
from bot.utils import (
    EMPTY_MARKUP,
    clean,
    ensure_user,
    format_order_short,
    safe_answer,
    safe_edit,
    safe_send,
    status_label,
    user_label,
)

log = logging.getLogger(__name__)

router = Router(name="orders")


# ==================================================================
#  QABUL QILISH
# ==================================================================
@router.callback_query(F.data.startswith("acc:"))
async def accept_order(call: CallbackQuery) -> None:
    try:
        order_id = int(call.data.split(":")[1])
        executor_id = int(call.from_user.id)

        order = await db.get_order(order_id)
        if not order:
            await safe_answer(call, "Buyurtma topilmadi", show_alert=True)
            return

        if int(order["customer_id"]) == executor_id:
            await safe_answer(call, "Bu buyurtmani o'zingiz bergan ekansiz 🙂", show_alert=True)
            return

        if order["status"] != "open":
            await safe_answer(
                call, "⏰ Kech qoldingiz, buyurtmani boshqa ijrochi oldi.", show_alert=True
            )
            await safe_edit(
                call,
                text="🔒 <b>Band</b>\n\nBu buyurtma boshqa ijrochi tomonidan olindi.",
                reply_markup=EMPTY_MARKUP,
            )
            return

        # Yo'nalish ijrochi profilida tanlanmagan bo'lsa — qabul qilmaydi
        if order.get("skill_id"):
            has_skill = await db.executor_has_skill(executor_id, int(order["skill_id"]))
            if not has_skill:
                await safe_answer(
                    call, "Bu yo'nalish sizning profilida tanlanmagan.", show_alert=True
                )
                return

        # Faol buyurtma limiti
        active = await db.count_active_orders(executor_id)
        if active >= config.MAX_ACTIVE_ORDERS:
            await safe_answer(
                call,
                f"Faol buyurtma limiti to'lgan ({config.MAX_ACTIVE_ORDERS} ta).",
                show_alert=True,
            )
            return

        # --- POYGA HOLATI (race condition) himoyasi: bitta atomik UPDATE ---
        taken = await db.take_order(order_id, executor_id)
        if not taken:
            await safe_answer(
                call, "⏰ Kech qoldingiz, buyurtmani boshqa ijrochi oldi.", show_alert=True
            )
            await safe_edit(
                call,
                text="🔒 <b>Band</b>\n\nBu buyurtma boshqa ijrochi tomonidan olindi.",
                reply_markup=EMPTY_MARKUP,
            )
            return

        await safe_answer(call, "✅ Buyurtma sizga berildi!")
        await finalize_taken_order(call.bot, order, executor_id)
    except Exception as exc:
        log.exception("Buyurtmani qabul qilish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


async def finalize_taken_order(bot: Bot, order: dict, executor_id: int) -> None:
    """Buyurtma olingandan keyin: xabarlarni tahrirlash + tomonlarni xabardor qilish."""
    order_id = int(order["id"])
    customer_id = int(order["customer_id"])

    customer = await db.get_user(customer_id)
    executor = await db.get_user(executor_id)

    # 1) Yuborilgan xabarlarni tahrirlash
    messages = await db.get_order_messages(order_id)
    for row in messages:
        chat_id = int(row["chat_id"])
        message_id = int(row["message_id"])
        try:
            if int(row["executor_id"]) == executor_id:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="✅ <b>Bu buyurtma sizga berildi!</b>\n\nIshni boshlashingiz mumkin ⏳",
                    reply_markup=EMPTY_MARKUP,
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔒 <b>Band</b>\n\nBu buyurtma boshqa ijrochi tomonidan olindi.",
                    reply_markup=EMPTY_MARKUP,
                )
        except TelegramAPIError as exc:
            log.debug("Xabarni tahrirlashda xato: %s", exc)
        except Exception as exc:  # pragma: no cover
            log.debug("Xabarni tahrirlashda xato: %s", exc)

    # 2) Buyurtmachining xabarini yangilash
    if order.get("customer_chat_id") and order.get("customer_message_id"):
        try:
            await bot.edit_message_text(
                chat_id=int(order["customer_chat_id"]),
                message_id=int(order["customer_message_id"]),
                text=(
                    f"🔝 <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
                    f"👷 Ijrochi: {user_label(executor)}\n\n"
                    "Ishni tugatgach <b>✅ Ish tugadi</b> tugmasini bosing va baho bering."
                ),
                reply_markup=EMPTY_MARKUP,
            )
        except Exception as exc:
            log.debug("Buyurtmachi xabarini tahrirlashda xato: %s", exc)

    # 3) Buyurtmachiga xabar
    executor_username = executor.get("username") if executor else None
    try:
        await bot.send_message(
            customer_id,
            f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"👷 <b>Ijrochi:</b> {user_label(executor)}\n"
            f"🆕 Buyurtma: <b>#{order_id}</b>\n\n"
            "Ijrochi bilan bog'laning 👇",
            reply_markup=customer_order_keyboard(
                order_id, executor_username, config.BOT_USERNAME
            ),
        )
    except Exception as exc:
        log.warning("Buyurtmachiga xabar yuborib bo'lmadi: %s", exc)

    # 4) Ijrochiga xabar
    customer_username = customer.get("username") if customer else None
    try:
        await bot.send_message(
            executor_id,
            f"🤝 <b>Yangi buyurtma sizda!</b>\n\n"
            f"🧑 <b>Buyurtmachi:</b> {user_label(customer)}\n"
            f"🆕 Buyurtma: <b>#{order_id}</b>\n\n"
            f"📝 Vazifa:\n{clean(order.get('description'), 800)}\n\n"
            f"💰 Byudjet: {clean(order.get('budget'), 40)}\n"
            f"⏳ Muddat: {clean(order.get('deadline'), 40)}\n\n"
            "Buyurtmachi bilan bog'laning 👇",
            reply_markup=executor_order_keyboard(
                order_id, customer_username, config.BOT_USERNAME
            ),
        )
    except Exception as exc:
        log.warning("Ijrochiga xabar yuborib bo'lmadi: %s", exc)


# ==================================================================
#  MUDDAT: qayta yuborish / bekor qilish
# ==================================================================
@router.callback_query(F.data.startswith("rsend:"))
async def resend_order(call: CallbackQuery) -> None:
    try:
        order_id = int(call.data.split(":")[1])
        order = await db.get_order(order_id)
        if not order:
            await safe_answer(call, "Buyurtma topilmadi", show_alert=True)
            return
        if int(order["customer_id"]) != int(call.from_user.id):
            await safe_answer(call, "Faqat buyurtmachi qayta yubora oladi", show_alert=True)
            return
        if order["status"] != "open":
            await safe_answer(call, "Bu buyurtma allaqachon olindi", show_alert=True)
            return

        await db.reset_order_timer(order_id)

        from bot.services.dispatcher import dispatch_order

        sent = await dispatch_order(call.bot, order)
        await safe_answer(call, "🔁 Qayta yuborildi")
        await safe_edit(
            call,
            text=(
                f"🔁 <b>Buyurtma #{order_id} qayta yuborildi</b>\n\n"
                + (
                    f"{sent} ta ijrochi yana ogohlantirildi. Javobni kutamiz!"
                    if sent
                    else "😔 Hozircha ijrochi topilmadi — admin'ga xabar berildi."
                )
            ),
            reply_markup=EMPTY_MARKUP,
        )
        await safe_send(
            call.bot,
            call.from_user.id,
            f"🔁 Buyurtma #{order_id} qayta yuborildi. Yana {config.ORDER_TIMEOUT_MINUTES} "
            "daqiqa kutamiz ⏳",
        )
    except Exception as exc:
        log.exception("Qayta yuborish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("canc:"))
async def cancel_order(call: CallbackQuery) -> None:
    try:
        order_id = int(call.data.split(":")[1])
        order = await db.get_order(order_id)
        if not order:
            await safe_answer(call, "Buyurtma topilmadi", show_alert=True)
            return
        if int(order["customer_id"]) != int(call.from_user.id):
            await safe_answer(call, "Faqat buyurtmachi bekor qila oladi", show_alert=True)
            return
        if order["status"] in ("done", "cancelled"):
            await safe_answer(call, "Bu buyurtma allaqachon yakunlangan", show_alert=True)
            return

        await db.set_order_status(order_id, "cancelled")
        await safe_answer(call, "❌ Bekor qilindi")
        await safe_edit(call, text=f"❌ <b>Buyurtma #{order_id} bekor qilindi.</b>", reply_markup=EMPTY_MARKUP)

        # Yuborilgan xabarlarni o'chiramiz
        for row in await db.get_order_messages(order_id):
            try:
                await call.bot.edit_message_text(
                    chat_id=int(row["chat_id"]),
                    message_id=int(row["message_id"]),
                    text="❌ <b>Bekor qilindi</b>\n\nBu buyurtma buyurtmachi tomonidan bekor qilindi.",
                    reply_markup=EMPTY_MARKUP,
                )
            except Exception:
                pass
    except Exception as exc:
        log.exception("Bekor qilish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


# ==================================================================
#  YAKUNLASH VA BAHO
# ==================================================================
@router.callback_query(F.data.startswith("done:"))
async def order_done(call: CallbackQuery) -> None:
    try:
        order_id = int(call.data.split(":")[1])
        order = await db.get_order(order_id)
        if not order:
            await safe_answer(call, "Buyurtma topilmadi", show_alert=True)
            return
        if int(order["customer_id"]) != int(call.from_user.id):
            await safe_answer(call, "Faqat buyurtmachi yakunlashi mumkin", show_alert=True)
            return
        if order["status"] == "done":
            await safe_answer(call, "Bu buyurtma allaqachon yakunlangan", show_alert=True)
            return
        if order["status"] != "taken":
            await safe_answer(call, "Buyurtma hali ijrochi topilmagan", show_alert=True)
            return

        await db.set_order_status(order_id, "done")
        await safe_answer(call, "✅ Yakunlandi")
        await safe_edit(
            call,
            text=(
                f"✅ <b>Buyurtma #{order_id} yakunlandi!</b>\n\n"
                "Ijrochiga baho bering ⭐"
            ),
            reply_markup=rate_keyboard(order_id),
        )
    except Exception as exc:
        log.exception("Yakunlash xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("rate:"))
async def rate_executor(call: CallbackQuery) -> None:
    try:
        parts = call.data.split(":")
        order_id = int(parts[1])
        score = int(parts[2])
        if score < 1 or score > 5:
            score = 5

        order = await db.get_order(order_id)
        if not order:
            await safe_answer(call, "Buyurtma topilmadi", show_alert=True)
            return
        if int(order["customer_id"]) != int(call.from_user.id):
            await safe_answer(call, "Faqat buyurtmachi baho qo'yishi mumkin", show_alert=True)
            return
        if not order.get("executor_id"):
            await safe_answer(call, "Ijrochi topilmadi", show_alert=True)
            return

        added = await db.add_rating(
            order_id, int(order["executor_id"]), int(order["customer_id"]), score
        )
        if not added:
            await safe_answer(call, "Bu buyurtma uchun baho allaqachon qo'yilgan", show_alert=True)
            return

        await safe_answer(call, f"⭐ Baho: {score}/5")
        await safe_edit(call, text=f"⭐ <b>Rahmat!</b> Baho: {score}/5 qabul qilindi.", reply_markup=EMPTY_MARKUP)

        rating_sum, rating_count = await db.get_executor_rating(int(order["executor_id"]))
        avg = rating_sum / rating_count if rating_count else 0
        try:
            await call.bot.send_message(
                int(order["executor_id"]),
                f"🎉 <b>Buyurtma #{order_id} yakunlandi!</b>\n\n"
                f"⭐ Yangi reytingingiz: <b>{avg:.1f}</b> ({rating_count} ta baho)\n"
                "Zo'r ish! Davom eting 💪",
            )
        except Exception:
            pass
    except Exception as exc:
        log.exception("Baho qo'yish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


# ==================================================================
#  SHIKOYAT
# ==================================================================
@router.callback_query(F.data.startswith("compl:"))
async def complaint_start(call: CallbackQuery, state: FSMContext) -> None:
    try:
        order_id = int(call.data.split(":")[1])
        await safe_answer(call)
        await state.set_state(ComplaintStates.text)
        await state.update_data(compl_order_id=order_id)
        await call.message.answer(
            "⚠️ <b>Shikoyat matnini yozing</b>\n\n"
            "Shikoyat admin'ga yuboriladi. Iltimos, muammoni aniq yozing."
        )
    except Exception as exc:
        log.exception("Shikoyat boshlanishi xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.message(ComplaintStates.text)
async def complaint_send(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text:
            await message.answer("✍️ Shikoyat matnini yozing.")
            return

        data = await state.get_data()
        order_id = data.get("compl_order_id")
        await state.clear()

        user = await ensure_user(message.from_user)
        await db.add_complaint(order_id, message.from_user.id, text)

        order = await db.get_order(int(order_id)) if order_id else None
        order_info = f"🆕 Buyurtma: <b>#{order_id}</b>" if order else "🆕 Buyurtma: —"
        if order:
            order_info += f"\n🛠 Yo'nalish: {clean(order.get('skill_name'), 60)}"

        if config.ADMIN_ID:
            from bot.keyboards import admin_mute_keyboard

            await safe_send(
                message.bot,
                config.ADMIN_ID,
                "⚠️ <b>Shikoyat</b>\n\n"
                f"👤 Shikoyat qiluvchi: {user_label(user)}\n"
                f"{order_info}\n\n"
                f"📝 <b>Shikoyat matni:</b>\n{clean(text, 1500)}",
                reply_markup=admin_mute_keyboard(message.from_user.id),
            )

        await message.answer("✅ Shikoyat yuborildi. Admin ko'rib chiqadi.")
    except Exception as exc:
        log.exception("Shikoyat yuborish xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


# ==================================================================
#  PROFIL / BUYURTMALARIM
# ==================================================================
async def send_profile(message: Message) -> None:
    user = await ensure_user(message.from_user)
    rating_sum, rating_count = await db.get_executor_rating(user["user_id"])
    avg = rating_sum / rating_count if rating_count else 0.0
    completed = await db.count_completed_orders(user["user_id"])
    skills = await db.get_executor_skills(user["user_id"])

    if skills:
        skills_text = "\n".join(
            f"• {clean(s['category_name'], 40)} → <b>{clean(s['skill_name'], 60)}</b>"
            for s in skills
        )
    else:
        skills_text = "—"

    username = user.get("username")
    text = (
        "👤 <b>Profilim</b>\n"
        "\n"
        f"👨‍💼 <b>Ism:</b> {clean(user.get('full_name'), 64)}\n"
        f"🆔 <b>Username:</b> {'@' + username if username else 'yo‘q'}\n"
        f"🎭 <b>Rol:</b> {config.ROLE_LABELS.get(user.get('role'), 'tanlanmagan')}\n"
        f"⭐ <b>Reyting:</b> {avg:.1f} / 5.0 ({rating_count} ta baho)\n"
        f"✅ <b>Bajarilgan ishlar:</b> {completed}\n"
        "\n"
        f"🛠 <b>Yo'nalishlarim:</b>\n{skills_text}"
    )
    markup = main_menu_keyboard(user["role"]) if user.get("role") else None
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery) -> None:
    try:
        await safe_answer(call)
        await send_profile(call.message)
    except Exception as exc:
        log.exception("Profil ko'rsatish xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "my_ord")
async def my_orders(call: CallbackQuery) -> None:
    try:
        user = await ensure_user(call.from_user)
        await safe_answer(call)

        if user.get("role") == config.ROLE_EXECUTOR:
            orders = await db.get_orders_by_executor(user["user_id"], limit=6)
            title = "📨 <b>Buyurtmalarim</b> (ijrochi sifatida)"
        else:
            orders = await db.get_orders_by_customer(user["user_id"], limit=6)
            title = "📨 <b>Buyurtmalarim</b>"

        if not orders:
            await call.message.answer(f"{title}\n\nHozircha buyurtma yo'q 😔")
            return

        lines = []
        for order in orders:
            lines.append(format_order_short(order))
        text = title + "\n\n" + "\n".join(lines)

        markup = None
        if user.get("role") != config.ROLE_EXECUTOR:
            buttons = []
            for order in orders:
                if order["status"] == "taken":
                    buttons.append(order)
            if buttons:
                from aiogram.types import InlineKeyboardButton
                from aiogram.utils.keyboard import InlineKeyboardBuilder

                kb = InlineKeyboardBuilder()
                for order in buttons:
                    kb.row(
                        InlineKeyboardButton(
                            text=f"✅ Ish tugadi (#{order['id']})",
                            callback_data=f"done:{order['id']}",
                        )
                    )
                markup = kb.as_markup()

        await call.message.answer(text, reply_markup=markup)
    except Exception as exc:
        log.exception("Buyurtmalarim xatosi: %s", exc)
        await safe_answer(call, "Xatolik yuz berdi", show_alert=True)


# ==================================================================
#  RELAY (bot orqali xabar yuborish)
# ==================================================================
async def handle_relay_start(message: Message, state: FSMContext, payload: str) -> None:
    """'https://t.me/bot?start=r123_e' havolasi orqali kirish."""
    try:
        body = payload[1:]  # 'r123_e' -> '123_e'
        parts = body.split("_")
        order_id = int(parts[0])
        role = parts[1] if len(parts) > 1 else "e"

        order = await db.get_order(order_id)
        if not order:
            await message.answer("😔 Buyurtma topilmadi.")
            return

        user_id = int(message.from_user.id)
        customer_id = int(order["customer_id"])
        executor_id = order.get("executor_id")

        if role == "e":
            peer_id = customer_id
        else:
            peer_id = int(executor_id) if executor_id else 0

        if user_id not in (customer_id, int(executor_id or 0)):
            await message.answer("⛔ Bu buyurtma sizga tegishli emas.")
            return
        if not peer_id:
            await message.answer("😔 Hozircha suhbatlashish uchun tomon topilmadi.")
            return

        await state.set_state(RelayStates.chat)
        await state.update_data(
            relay_order_id=order_id, relay_peer_id=peer_id, relay_role=role
        )
        await message.answer(
            "✉️ <b>Bot orqali yozish rejimi yoqildi</b>\n\n"
            "Xabaringizni yozing — men uni buyurtmachinga (yoki ijrochiga) yetkazaman.\n"
            "Bekor qilish uchun /menu yozing."
        )
    except Exception as exc:
        log.exception("Relay boshlanishi xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")


@router.message(RelayStates.chat)
async def relay_message(message: Message, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        order_id = data.get("relay_order_id")
        peer_id = data.get("relay_peer_id")
        role = data.get("relay_role", "e")

        if not order_id or not peer_id:
            await state.clear()
            return

        order = await db.get_order(int(order_id))
        if not order:
            await state.clear()
            await message.answer("😔 Buyurtma topilmadi.")
            return

        # Qarshi tomonning roli (yuboruvchining roligi teskari)
        peer_role = "c" if role == "e" else "e"

        # Xabar yuborish
        try:
            if message.text:
                username = message.from_user.username
                username_text = f"@{username}" if username else "username yo‘q"
                text = (
                    f"💬 <b>{clean(message.from_user.full_name, 64)}</b> ({username_text}):\n"
                    f"{clean(message.text, 3000)}"
                )
                await message.bot.send_message(
                    int(peer_id),
                    text,
                    reply_markup=contact_keyboard(
                        int(order_id),
                        username,
                        peer_role,
                        config.BOT_USERNAME,
                    ),
                )
            else:
                await message.bot.copy_message(
                    int(peer_id), message.chat.id, message.message_id
                )
        except TelegramAPIError as exc:
            await message.answer(f"😔 Yuborib bo'lmadi: {clean(str(exc), 120)}")
            return
        except Exception as exc:
            log.exception("Relay yuborish xatosi: %s", exc)
            await message.answer("😔 Yuborib bo'lmadi.")
            return

        await message.answer("✅ Yuborildi")
    except Exception as exc:
        log.exception("Relay xatosi: %s", exc)
        await message.answer("😔 Xatolik yuz berdi.")

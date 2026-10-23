"""Buyurtmani mos ijrochilarga tarqatish xizmati."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot import config
from bot.database import db
from bot.keyboards import accept_keyboard, admin_dispatch_keyboard
from bot.utils import clean, format_order, safe_send, user_label

log = logging.getLogger(__name__)


async def dispatch_order(
    bot: Bot,
    order: dict,
    all_executors: bool = False,
) -> int:
    """Buyurtmani ijrochilarga yuboradi.

    Qaytaradi: xabar yuborilgan ijrochilar soni.
    Telegram limitlariga rioya qilib xabarlar orasida pauza qo'yadi.
    Bloklagan foydalanuvchilarni nofaol qiladi.
    """
    if not order or order.get("status") != "open":
        return 0

    customer_id = int(order["customer_id"])

    if all_executors or order.get("is_custom"):
        executors = await db.find_all_executors(customer_id)
    else:
        executors = await db.find_executors_for_skill(int(order["skill_id"]), customer_id)

    if not executors:
        await notify_admin_no_executors(bot, order)
        return 0

    category_name = None
    skill_name = order.get("skill_name")
    if order.get("skill_id"):
        info = await db.get_skill_with_category(int(order["skill_id"]))
        if info:
            category_name = info["category_name"]
            skill_name = info["skill_name"]

    text = format_order(order, category_name, skill_name)

    sent = 0
    for executor in executors:
        executor_id = int(executor["user_id"])
        try:
            msg = await bot.send_message(
                executor_id,
                text,
                reply_markup=accept_keyboard(int(order["id"])),
            )
        except TelegramAPIError as exc:
            # Botni bloklagan yoki yozishga ruxsat berilmagan
            if "bot was blocked" in str(exc).lower() or "forbidden" in str(exc).lower():
                await db.deactivate_user(executor_id)
                log.info("Foydalanuvchi botni bloklagan, nofaol qilindi: %s", executor_id)
            else:
                log.warning("Yuborish xatosi (%s): %s", executor_id, exc)
            continue
        except Exception as exc:  # pragma: no cover
            log.exception("Yuborish xatosi (%s): %s", executor_id, exc)
            continue

        await db.save_order_message(int(order["id"]), executor_id, msg.chat.id, msg.message_id)
        sent += 1
        # Telegram limitlariga rioya qilish uchun kichik pauza
        await asyncio.sleep(config.SEND_DELAY)

    if sent == 0:
        await notify_admin_no_executors(bot, order)

    return sent


async def notify_admin_no_executors(bot: Bot, order: dict) -> None:
    """Bu yo'nalishda ijrochi topilmadi — admin'ga xabar beriladi."""
    if not config.ADMIN_ID:
        return
    customer = await db.get_user(int(order["customer_id"]))
    text = (
        "⚠️ <b>Ijrochisiz buyurtma!</b>\n\n"
        f"🆕 Buyurtma: <b>#{order['id']}</b>\n"
        f"🛠 Yo'nalish: {clean(order.get('skill_name'), 60)}\n"
        f"👤 Buyurtmachi: {user_label(customer)}\n"
        f"📝 Vazifa: {clean(order.get('description'), 500)}\n"
        f"💰 Byudjet: {clean(order.get('budget'), 40)}\n"
        f"⏳ Muddat: {clean(order.get('deadline'), 40)}\n\n"
        "📣 <i>Eksecutorlarga qo'lda yuborishingiz mumkin.</i>"
    )
    await safe_send(
        bot,
        config.ADMIN_ID,
        text,
        reply_markup=admin_dispatch_keyboard(int(order["id"])),
    )


async def notify_admin_order(bot: Bot, order: dict, custom: bool = False) -> None:
    """Admin'ga buyurtma haqida xabar (maxsus yo'nalishlar har doim yuboriladi)."""
    if not config.ADMIN_ID:
        return
    if not custom and not config.ADMIN_NOTIFY_ALL:
        return
    customer = await db.get_user(int(order["customer_id"]))
    skill = await db.get_skill_with_category(int(order["skill_id"])) if order.get("skill_id") else None
    category_name = skill["category_name"] if skill else "➕ Boshqa"

    text = (
        "📨 <b>Yangi buyurtma</b>\n\n"
        f"🆕 <b>#{order['id']}</b>"
        + (" <i>(maxsus yo'nalish)</i>" if custom else "")
        + "\n"
        f"📂 Soha: {clean(category_name, 60)}\n"
        f"🛠 Yo'nalish: {clean(order.get('skill_name'), 60)}\n"
        f"👤 Buyurtmachi: {user_label(customer)}\n"
        f"📝 Vazifa: {clean(order.get('description'), 400)}\n"
        f"💰 Byudjet: {clean(order.get('budget'), 40)}\n"
        f"⏳ Muddat: {clean(order.get('deadline'), 40)}"
    )
    keyboard = admin_dispatch_keyboard(int(order["id"])) if custom else None
    await safe_send(bot, config.ADMIN_ID, text, reply_markup=keyboard)

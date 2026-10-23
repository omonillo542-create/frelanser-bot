"""30 daqiqalik muddat nazorati (fon vazifasi)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bot import config
from bot.database import db
from bot.keyboards import timeout_keyboard
from bot.utils import clean, safe_send

log = logging.getLogger(__name__)


async def check_expired_orders(bot: Bot) -> int:
    """Muddati o'tgan `open` buyurtmalarni tekshiradi.

    Bot qayta ishga tushganda ham chaqiriladi — muddat nazorati tiklanadi.
    """
    try:
        orders = await db.get_expired_open_orders(config.ORDER_TIMEOUT_MINUTES)
    except Exception as exc:
        log.exception("Muddati o'tgan buyurtmalarni olish xatosi: %s", exc)
        return 0

    notified = 0
    for order in orders:
        try:
            await safe_send(
                bot,
                int(order["customer_id"]),
                "⌛ <b>Hozircha ijrochi topilmadi</b>\n\n"
                f"Buyurtma #{order['id']} uchun {config.ORDER_TIMEOUT_MINUTES} daqiqa davomida "
                "ijrochi topilmadi.\n"
                "Qayta yuborasizmi yoki bekor qilasizmi?",
                reply_markup=timeout_keyboard(int(order["id"])),
            )
            await db.mark_timeout_notified(int(order["id"]))
            notified += 1
        except Exception as exc:
            log.exception("Muddat xabarini yuborish xatosi: %s", exc)
    return notified


async def timeout_worker(bot: Bot, interval: int = 30) -> None:
    """Ortiqcha fon vazifasi — bot ishlayotgan payt tekshirib turadi."""
    log.info("Muddat nazorati fon vazifasi ishga tushdi (interval=%ss)", interval)
    try:
        while True:
            try:
                await check_expired_orders(bot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Muddat nazorati xatosi: %s", exc)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        log.info("Muddat nazorati fon vazifasi to'xtatildi")

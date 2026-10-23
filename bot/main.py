"""Bot ishga tushirish nuqtasi.

Ishga tushirish:
    python bot/main.py     yoki     python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):  # `python bot/main.py` holati uchun
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, CallbackQuery, ErrorEvent, Message

from bot import config
from bot.database import db
from bot.handlers import admin, customer, executor, orders, start
from bot.services import gist_backup
from bot.services.timeouts import check_expired_orders, timeout_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")


async def setup_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="menu", description="Asosiy menyu"),
        BotCommand(command="profile", description="Profilim"),
        BotCommand(command="help", description="Yordam"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    except Exception as exc:  # pragma: no cover
        log.warning("Buyruqlarni o'rnatib bo'lmadi: %s", exc)


async def error_handler(event: ErrorEvent) -> None:
    """Bot qulashining oldini oladi — xatolar foydalanuvchiga ko'rsatiladi."""
    log.error("Kutilmagan xatolik: %s", event.exception, exc_info=event.exception)
    update = event.update
    try:
        if isinstance(update, Message):
            await update.answer("😔 Xatolik yuz berdi. Iltimos, /menu bosing.")
        elif isinstance(update, CallbackQuery):
            await update.answer("😔 Xatolik yuz berdi", show_alert=True)
    except Exception:
        pass


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Tartib muhim: start -> executor/customer -> orders -> admin
    dp.include_router(start.router)
    dp.include_router(executor.router)
    dp.include_router(customer.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)

    dp.errors.register(error_handler)
    return dp


async def main() -> None:
    if not config.BOT_TOKEN:
        log.error("BOT_TOKEN topilmadi! .env faylni to'ldiring (namuna: .env.example).")
        return
    if not config.ADMIN_ID:
        log.warning("ADMIN_ID ko'rsatilmagan — admin buyruqlari ishlamaydi.")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    me = await bot.get_me()
    config.BOT_USERNAME = me.username
    log.info("Bot ishga tushdi: @%s (id=%s)", me.username, me.id)

    # --- baza (bepul hosting uchun Gist'dan tiklash) ---
    await gist_backup.restore_db(config.DB_PATH)
    await db.init_schema()
    await db.seed_categories(config.INITIAL_CATEGORIES)
    log.info("Baza tayyor: %s", db.path)

    # --- bot buyruqlari ---
    await setup_commands(bot)

    dp = build_dispatcher()

    # --- bot qayta ishga tushganda muddat nazorati tiklanadi ---
    try:
        restored = await check_expired_orders(bot)
        if restored:
            log.info("Muddat nazorati tiklandi: %s ta buyurtma", restored)
    except Exception as exc:  # pragma: no cover
        log.exception("Muddat nazoratini tiklashda xato: %s", exc)

    timeout_task = asyncio.create_task(timeout_worker(bot))
    backup_task = asyncio.create_task(
        gist_backup.backup_worker(db, config.DB_PATH, config.GIST_INTERVAL_MINUTES)
    )
    poll_task = asyncio.create_task(
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False,
        )
    )

    try:
        if config.MAX_RUNTIME_MINUTES > 0:
            log.info(
                "⏱ Maksimal ish vaqti: %s daqiqa (GitHub Actions uchun)",
                config.MAX_RUNTIME_MINUTES,
            )
            await asyncio.sleep(config.MAX_RUNTIME_MINUTES * 60)
            log.info("Vaqt tugadi — bot to'xtatildi")
        else:
            await poll_task
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi")
    finally:
        timeout_task.cancel()
        backup_task.cancel()
        for task in (timeout_task, backup_task):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if not poll_task.done():
            poll_task.cancel()
            try:
                await poll_task
            except (asyncio.CancelledError, Exception):
                pass
        try:
            await gist_backup.save_db(db, config.DB_PATH)
        except Exception:
            pass
        try:
            await bot.session.close()
        except Exception:
            pass
        try:
            await db.close()
        except Exception:
            pass
        log.info("Bot yopildi")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot to'xtatildi.")

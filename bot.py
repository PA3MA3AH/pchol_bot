# bot.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN
from db.pool import db

import repositories.cards_repo as cards_repo
from tasks.farm_tick import farm_tick
from tasks.poll_checker import poll_checker

from handlers.start import router as start_router
from handlers.wallet import router as wallet_router
from handlers.farms_boosts import router as farms_boosts_router
from handlers.cards import router as cards_router
from handlers.nft import router as nft_router
from handlers.duels import router as duels_router
from handlers.transfers import router as transfers_router
from handlers.checks import router as checks_router
from handlers.minigame import router as minigame_router
from handlers.buybee import router as buybee_router
from handlers.polls import router as polls_router
from handlers.admin import router as admin_router
from handlers.messages import router as messages_reactions_router, register_catch_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pchol_bot")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Порядок include_router важен: специфичные хендлеры (команды, шаблоны, callback'и)
# должны идти раньше catch-all счётчика пчол, иначе он их перехватит.
ROUTERS = [
    start_router,
    wallet_router,
    farms_boosts_router,
    cards_router,
    nft_router,
    duels_router,
    transfers_router,
    checks_router,
    minigame_router,
    buybee_router,
    polls_router,
    admin_router,
    messages_reactions_router,  # "пчол" / "ужалить" — тоже узкие фильтры, но идут перед catch-all
]

for r in ROUTERS:
    dp.include_router(r)

# catch-all счётчик пчол — регистрируем последним
register_catch_all(dp)


BOT_COMMANDS = [
    BotCommand(command="start", description="Инструкция"),
    BotCommand(command="pchol", description="Общее количество ПЧОЛ в чате"),
    BotCommand(command="top", description="Топ-10 пользователей по ПЧОЛАМ"),
    BotCommand(command="beefarm", description="Купить авто-ферму"),
    BotCommand(command="beeboost", description="Купить буст"),
    BotCommand(command="buybee", description="Купить пчол за рубли"),
    BotCommand(command="check", description="Создать чек на перевод"),
    BotCommand(command="checkchecks", description="Список активных чеков"),
    BotCommand(command="delcheck", description="Удалить чек"),
    BotCommand(command="getpchol", description="Мини-игра для приумножения пчолов"),
    BotCommand(command="myachivepchol", description="Посмотреть ваши достижения"),
    BotCommand(command="giftnft", description="Укажите @пользователя для передачи пчол-NFT"),
    BotCommand(command="breed_nft", description="Скрещивание трех лучших карт в пчол-NFT"),
    BotCommand(command="beedefend", description="Установить 5 карт пчолов в защиту"),
    BotCommand(command="beeattack", description="Установить 5 карт пчолов в атаку"),
    BotCommand(command="upgradecard", description="Улучшить уровень карты пчола"),
    BotCommand(command="beecards", description="Ваша коллекция карт пчолов"),
    BotCommand(command="beepack", description="Купить пак карт пчолов"),
]


async def on_startup():
    logger.info("Starting up — connecting to DB...")
    await db.connect()
    await cards_repo.init_card_catalog()

    try:
        await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())
    except Exception:
        logger.exception("Failed to set bot commands")

    asyncio.create_task(farm_tick())
    asyncio.create_task(poll_checker(bot))
    logger.info("Bot ready.")


async def on_shutdown():
    logger.info("Shutting down — closing DB and stopping tasks...")
    try:
        await db.close()
    except Exception:
        pass
    try:
        await bot.session.close()
    except Exception:
        pass
    logger.info("Bot stopped.")


async def main():
    try:
        await on_startup()
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())

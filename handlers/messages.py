# handlers/messages.py
import logging

from aiogram import Router, F
from aiogram.types import Message

import repositories.users_repo as users_repo
from services.economy import count_bees_in_message, can_receive_bees, MAX_BEES_PER_WINDOW
from handlers.start import AllChatsFilter

router = Router(name="messages")
logger = logging.getLogger("pchol_bot.messages")


@router.message(lambda m: m.text and m.text.lower().strip() in {"пчол", "Пчол"})
async def react_pchol(message: Message):
    await message.reply("жужжит ✅")


@router.message(F.reply_to_message, F.text.lower() == "ужалить")
async def sting_reply(message: Message):
    stinger = message.from_user.first_name
    victim = message.reply_to_message.from_user.first_name
    await message.reply(f"🐝 {stinger} ужалил {victim}!")
    logger.info(f"{stinger} ужалил {victim}")


async def on_new_message(message: Message):
    try:
        if not message.from_user:
            return
        user_id = message.from_user.id
        try:
            await users_repo.update_username(user_id, message.from_user.username or None)
        except Exception:
            pass

        bees = count_bees_in_message(message)
        if bees > 0 and await users_repo.is_frozen(user_id):
            await message.reply("Вы были заморожены. Ваши отправленные ПЧОЛЫ не будут засчитываться ни в одном из чатов.")
            return
        if bees == 0:
            await users_repo.ensure_zero_message(message.chat.id, message.message_id, user_id)
            return

        ok, accepted = can_receive_bees(user_id, bees)
        if not ok:
            await message.reply(f"Лимит получения пчол за минуту исчерпан (макс {MAX_BEES_PER_WINDOW}). Попробуйте позже.")
            return
        if accepted > 0:
            await users_repo.add_message_count(message.chat.id, message.message_id, accepted, user_id)
            if accepted < bees:
                await message.reply(f"Засчитано {accepted} из {bees} пчол из-за лимита {MAX_BEES_PER_WINDOW}/мин.")
    except Exception:
        logger.exception("Error handling new message")


async def on_edited_message(message: Message):
    try:
        if not message.from_user:
            return
        user_id = message.from_user.id
        bees = count_bees_in_message(message)
        if bees > 0 and await users_repo.is_frozen(user_id):
            return
        ok, accepted = can_receive_bees(user_id, bees)
        if not ok and accepted == 0:
            return
        await users_repo.update_message_on_edit(message.chat.id, message.message_id, accepted, user_id)
    except Exception:
        logger.exception("Error handling edited message")


def register_catch_all(dp):
    """Регистрирует catch-all хендлеры (счётчик пчол) — должны идти ПОСЛЕДНИМИ,
    после всех остальных роутеров, иначе перехватят команды/переводы/шаблоны опросов."""
    dp.message.register(on_new_message, AllChatsFilter())
    dp.edited_message.register(on_edited_message, AllChatsFilter())

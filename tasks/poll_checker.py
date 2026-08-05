# tasks/poll_checker.py
import asyncio
import logging

from aiogram import Bot

import repositories.polls_repo as polls_repo
import repositories.users_repo as users_repo
from config import OWNER_ID
from db.pool import db

logger = logging.getLogger("pchol_bot.tasks.poll_checker")


async def poll_checker(bot: Bot):
    while True:
        try:
            if not db.pool:
                await asyncio.sleep(10)
                continue

            expired_polls = await polls_repo.get_expired_polls()
            for poll in expired_polls:
                try:
                    await bot.stop_poll(chat_id=poll["chat_id"], message_id=poll["message_id"])
                except Exception:
                    pass

                votes = await polls_repo.get_poll_votes(poll["id"])
                correct_ids_set = set(poll["correct_option_ids"].split(",")) if poll["correct_option_ids"] else set()

                winners = []
                for vote in votes:
                    vote_ids_set = set(vote["option_ids"].split(","))
                    is_correct = bool(correct_ids_set) and bool(correct_ids_set.intersection(vote_ids_set))
                    if is_correct and not vote["rewarded"]:
                        await users_repo.add_bees_to_user(vote["user_id"], poll["prize_bees"])
                        await polls_repo.mark_vote_rewarded(vote["id"])
                        try:
                            await bot.send_message(
                                vote["user_id"],
                                f"🎉 Вы получили {poll['prize_bees']} ПЧОЛОВ за правильный ответ в опросе!",
                            )
                        except Exception:
                            pass
                    if is_correct:
                        try:
                            user = await bot.get_chat(vote["user_id"])
                            winners.append(f"@{user.username}" if user.username else user.first_name)
                        except Exception:
                            pass

                await polls_repo.close_poll(poll["id"])

                try:
                    link = f"https://t.me/c/{str(poll['chat_id']).replace('-100', '')}/{poll['message_id']}"
                    text = (
                        f"Опрос ({link}) был завершён.\n"
                        f"Приз получили: {', '.join(winners) if winners else 'никто'}\n"
                        f"Сумма приза: {poll['prize_bees']}"
                    )
                    await bot.send_message(OWNER_ID, text)
                except Exception:
                    logger.exception("Ошибка при отправке уведомления о завершении опроса")

            await asyncio.sleep(30)
        except Exception:
            logger.exception("poll_checker error")
            await asyncio.sleep(30)

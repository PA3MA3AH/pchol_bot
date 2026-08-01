# handlers/polls.py
import json
from datetime import datetime
from typing import Dict

import pytz
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, PollAnswer,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import repositories.polls_repo as polls_repo
from config import OWNER_ID, TIMEZONE
from db.pool import db

router = Router(name="polls")
MSK_TZ = pytz.timezone(TIMEZONE)

poll_creation_sessions: Dict[int, dict] = {}


@router.message(Command(commands=["opros"]))
async def cmd_opros(message: Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("Эта команда доступна только владельцу бота.")
        return

    async with db.pool.acquire() as conn:
        chats = await conn.fetch("SELECT DISTINCT chat_id FROM chats")

    if not chats:
        await message.reply("Бот не состоит ни в одной группе.")
        return

    kb_buttons = []
    for chat_row in chats:
        chat_id = chat_row["chat_id"]
        try:
            chat_info = await bot.get_chat(chat_id)
            chat_name = chat_info.title or f"Чат {chat_id}"
        except Exception:
            chat_name = f"Чат {chat_id}"
        kb_buttons.append([InlineKeyboardButton(text=chat_name, callback_data=f"opros_chat:{chat_id}")])

    await message.reply("Выберите группу для создания опроса:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))


@router.callback_query(lambda c: c.data and c.data.startswith("opros_chat:"))
async def cb_opros_chat(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    chat_id = int(callback.data.split(":")[1])
    poll_creation_sessions[callback.from_user.id] = {"chat_id": chat_id, "step": "template"}

    template_text = (
        "📋 Заполните опрос по шаблону:\n\n"
        "0:(текст опроса):0\n"
        "1:(первый вариант):1\n"
        "2:(второй вариант):2\n"
        "AV: On / Off (можно ли голосовать за все варианты)\n"
        "RV: 1 (правильный вариант, если AV: Off)\n"
        "P: N (приз в пчолах за правильный ответ)\n\n"
        "После заполнения шаблона отправьте его сюда.\n"
        "Затем укажите дату окончания в формате: <code>DD:MM:YYYY HH:MM:SS</code>\n"
        "Пример: <code>12:10:2025 00:00:00</code>"
    )
    try:
        await bot.send_message(callback.from_user.id, template_text)
        await callback.message.edit_text("📨 Инструкция отправлена вам в личные сообщения.")
    except Exception:
        await callback.message.answer("⚠️ Не удалось написать вам в ЛС. Напишите боту /start, чтобы открыть чат.")


@router.message(lambda m: m.chat.type == "private" and m.from_user.id in poll_creation_sessions
                 and poll_creation_sessions[m.from_user.id].get("step") == "template")
async def handle_poll_template(message: Message):
    user_id = message.from_user.id
    session = poll_creation_sessions[user_id]

    try:
        lines = message.text.strip().split("\n")
        options = []
        question = None
        av_mode = False
        correct_ids = []
        prize = 0

        for line in lines:
            line = line.strip()
            if line.startswith("0:"):
                parts = line.split(":")
                question = parts[1] if len(parts) > 1 else ""
            elif line[:1].isdigit() and ":" in line:
                parts = line.split(":")
                options.append(parts[1] if len(parts) > 1 else "")
            elif line.startswith("AV:"):
                av_mode = "on" in line.lower()
            elif line.startswith("RV:"):
                rv_part = line.split(":")[1].strip()
                correct_ids = [int(x.strip()) for x in rv_part.split(",")]
            elif line.startswith("P:"):
                prize = int(line.split(":")[1].strip())

        if not question or not options:
            await message.reply("Ошибка в шаблоне. Убедитесь, что указаны вопрос и варианты.")
            return

        session.update({
            "question": question,
            "options": options,
            "av_mode": av_mode,
            "correct_ids": correct_ids,
            "prize": prize,
            "step": "datetime",
        })
        await message.reply("📅 Укажите дату окончания в формате:\n<code>DD:MM:YYYY HH:MM:SS</code>\nПример: <code>12:10:2025 00:00:00</code>")
    except Exception as e:
        await message.reply(f"Ошибка при обработке шаблона: {e}")


@router.message(lambda m: m.chat.type == "private" and m.from_user.id in poll_creation_sessions
                 and poll_creation_sessions[m.from_user.id].get("step") == "datetime")
async def handle_poll_datetime(message: Message, bot: Bot):
    user_id = message.from_user.id
    session = poll_creation_sessions.get(user_id)
    if not session:
        await message.reply("❌ Сессия создания опроса не найдена. Начните заново с команды /opros.")
        return

    try:
        datetime_str = message.text.strip()
        date_part, time_part = datetime_str.split()
        day, month, year = map(int, date_part.split(":"))
        hour, minute, second = map(int, time_part.split(":"))
        end_time = datetime(year, month, day, hour, minute, second)

        if end_time <= datetime.now():
            await message.reply("❌ Дата окончания должна быть в будущем.")
            return

        poll_msg = await bot.send_poll(
            chat_id=session["chat_id"],
            question=session["question"],
            options=session["options"],
            is_anonymous=False,
            allows_multiple_answers=session["av_mode"],
        )

        correct_ids_str = ",".join(map(str, session["correct_ids"]))
        options_json = json.dumps(session["options"], ensure_ascii=False)

        await polls_repo.create_poll(
            creator_id=user_id,
            chat_id=session["chat_id"],
            poll_id=poll_msg.poll.id,
            message_id=poll_msg.message_id,
            question=session["question"],
            options=options_json,
            correct_ids=correct_ids_str,
            allow_multiple=session["av_mode"],
            prize=session["prize"],
            end_time=end_time,
        )

        await message.reply(f"✅ Опрос создан! Завершится {end_time.strftime('%d.%m.%Y %H:%M:%S')} МСК")
        poll_creation_sessions.pop(user_id, None)
    except ValueError:
        await message.reply("❌ Неверный формат. Используйте <code>DD:MM:YYYY HH:MM:SS</code>")
    except Exception as e:
        await message.reply(f"Ошибка при создании опроса: {e}")
        poll_creation_sessions.pop(user_id, None)


@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    """Сохраняем голос пользователя в БД (привязываясь к internal poll_db_id)."""
    poll = await polls_repo.get_poll_by_id(poll_answer.poll_id)
    if not poll:
        return
    option_ids_str = ",".join(str(x) for x in poll_answer.option_ids)
    await polls_repo.add_poll_vote(poll["id"], poll_answer.user.id, option_ids_str)


@router.message(Command(commands=["oprostime"]))
async def cmd_oprostime(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message or not message.reply_to_message.poll:
        await message.reply("Ответьте реплаем на сообщение с опросом.")
        return

    poll_id = message.reply_to_message.poll.id
    poll_data = await polls_repo.get_poll_by_id(poll_id)
    if not poll_data:
        await message.reply("Опрос не найден в базе.")
        return

    end_time = poll_data["end_time"].astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M:%S")
    await message.reply(f"⏰ Опрос закончится {end_time} МСК")

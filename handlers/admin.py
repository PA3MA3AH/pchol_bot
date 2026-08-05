# handlers/admin.py
import asyncio
import json
import logging
import os
import sys
import tempfile
import zipfile

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
)

import repositories.users_repo as users_repo
from config import OWNER_ID
from db.pool import db
from states import PcholTextStates

router = Router(name="admin")
logger = logging.getLogger("pchol_bot.admin")


@router.message(Command(commands=["owner"]))
async def cmd_owner(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("🚫 Эта команда доступна только владельцу бота.")
        return
    await message.reply(
        "👑 <b>Команды владельца бота:</b>\n\n"
        "/freeze — заморозить пользователя (реплай)\n"
        "/unfreeze — разморозить пользователя (реплай)\n"
        "/frozenlist — список замороженных\n"
        "/opros — создать опрос\n"
        "/resetstatsglobal — сбросить всю базу данных\n"
        "/backup — сохранить базу данных (в JSON)\n"
        "/restartpchol — перезапустить бота\n"
        "/oprostime — время окончания опроса\n"
        "/pcholtext —  отправка сообщения от имени бота",
        parse_mode="HTML",
    )


@router.message(Command(commands=["freeze"]))
async def cmd_freeze(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message:
        await message.reply("Ответьте на сообщение пользователя для заморозки.")
        return
    target_id = message.reply_to_message.from_user.id
    await users_repo.freeze_user(target_id)
    await message.reply(f"Пользователь {message.reply_to_message.from_user.full_name} заморожен.")


@router.message(Command(commands=["unfreeze"]))
async def cmd_unfreeze(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message:
        await message.reply("Ответьте на сообщение пользователя для разморозки.")
        return
    target_id = message.reply_to_message.from_user.id
    await users_repo.unfreeze_user(target_id)
    await message.reply(f"Пользователь {message.reply_to_message.from_user.full_name} разморожен.")


@router.message(Command(commands=["frozenlist"]))
async def cmd_frozenlist(message: Message, bot: Bot):
    frozen = await users_repo.get_frozen_users()
    if not frozen:
        await message.reply("Нет замороженных пользователей.")
        return
    text = "❄ Замороженные пользователи:\n"
    for uid in frozen:
        try:
            user = await bot.get_chat(uid)
            name = user.full_name
        except Exception:
            name = f"ID {uid}"
        text += f"• {name}\n"
    await message.reply(text)


# ---------- глобальный сброс базы ----------

@router.message(Command(commands=["resetstatsglobal"]))
async def cmd_resetstatsglobal(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("🚫 Эта команда доступна только владельцу бота.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚠️ Подтверждаю сброс", callback_data="confirm_reset"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reset"),
    ]])
    await message.reply(
        "⚠️ <b>ВНИМАНИЕ:</b> это действие удалит ВСЕ данные бота!\n\n"
        "Пользователи, сообщения, фермы, опросы, чеки и мини-игры будут утеряны навсегда.\n\n"
        "Вы уверены, что хотите продолжить?",
        reply_markup=kb,
    )


@router.callback_query(lambda c: c.data in {"confirm_reset", "cancel_reset"})
async def cb_reset_db(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    if callback.data == "cancel_reset":
        await callback.message.edit_text("❌ Сброс базы отменён.")
        return

    await callback.message.edit_text("🧹 Выполняется полная очистка базы...")
    tables = [
        "users", "messages", "chats", "top_users", "frozen_users",
        "transfers_log", "buybee_requests", "checks", "pchol_game",
        "polls", "poll_votes",
    ]
    try:
        async with db.pool.acquire() as conn:
            for t in tables:
                try:
                    await conn.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;")
                except Exception:
                    pass
        await callback.message.edit_text("✅ Все таблицы успешно очищены.")
        await bot.send_message(OWNER_ID, "✅ Глобальный сброс базы успешно выполнен.")
    except Exception as e:
        await callback.message.edit_text(f"⚠️ Ошибка при очистке базы: <code>{e}</code>")


# ---------- бэкап ----------

@router.message(Command(commands=["backup"]))
async def cmd_backup(message: Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("🚫 Эта команда доступна только владельцу бота.")
        return

    await message.reply("💾 Создаю JSON-бэкап базы, подождите...")
    tmp_zip = None
    try:
        tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp_zip.close()

        async with db.pool.acquire() as conn:
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )
            with zipfile.ZipFile(tmp_zip.name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for t in tables:
                    name = t["table_name"]
                    rows = await conn.fetch(f"SELECT * FROM {name}")
                    data = [dict(r) for r in rows]
                    zipf.writestr(f"{name}.json", json.dumps(data, ensure_ascii=False, indent=2, default=str))

        doc = FSInputFile(tmp_zip.name, filename="backup_database.zip")
        await bot.send_document(OWNER_ID, document=doc, caption="📦 JSON-бэкап базы данных (все таблицы)")
        await message.reply("✅ JSON-бэкап успешно создан и отправлен вам в ЛС.")
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при создании бэкапа: {e}")
    finally:
        if tmp_zip and os.path.exists(tmp_zip.name):
            os.remove(tmp_zip.name)


# ---------- перезапуск ----------

@router.message(Command(commands=["restartpchol"]))
async def cmd_restartpchol(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("🚫 Эта команда доступна только владельцу бота.")
        return
    await message.reply("🔁 Перезапуск бота...")
    await asyncio.sleep(1)
    logger.info("Бот перезапущен вручную владельцем.")
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ---------- отправка сообщения от имени бота в выбранный чат ----------

async def _get_known_chats(conn):
    columns = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='chats'"
    )
    colnames = [c["column_name"] for c in columns]
    id_field = "chat_id" if "chat_id" in colnames else "id"
    title_field = "title" if "title" in colnames else None

    if title_field:
        rows = await conn.fetch(f"SELECT {id_field} AS chat_id, {title_field} AS title FROM chats ORDER BY {id_field}")
    else:
        rows = await conn.fetch(f"SELECT {id_field} AS chat_id FROM chats ORDER BY {id_field}")

    result = []
    for r in rows:
        chat_id = r["chat_id"]
        title = r.get("title") if "title" in r.keys() else None
        result.append((chat_id, title or f"Чат {chat_id}"))
    return result


@router.message(Command(commands=["pcholtext"]))
async def cmd_pcholtext(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        await message.reply("🚫 Эта команда доступна только владельцу бота.")
        return

    async with db.pool.acquire() as conn:
        chats = await _get_known_chats(conn)

    if not chats:
        await message.reply("⚠️ Бот не найден ни в одном сохранённом чате.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=title[:30], callback_data=f"pcholtext:{chat_id}")]
        for chat_id, title in chats
    ])
    await message.reply("📋 Выберите чат, куда нужно отправить сообщение:", reply_markup=kb)


@router.callback_query(F.data.startswith("pcholtext:"))
async def pcholtext_select_chat(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("🚫 Недостаточно прав.", show_alert=True)
        return
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        f"📝 Введите текст сообщения, которое нужно отправить в чат <code>{chat_id}</code>.",
        parse_mode="HTML",
    )
    await state.set_state(PcholTextStates.waiting_for_text)


@router.message(PcholTextStates.waiting_for_text)
async def pcholtext_send_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    chat_id = data.get("chat_id")

    try:
        if message.text:
            await bot.send_message(chat_id, message.text)
        elif message.photo:
            await bot.send_photo(chat_id, photo=message.photo[-1].file_id, caption=message.caption or "")
        elif message.video:
            await bot.send_video(chat_id, video=message.video.file_id, caption=message.caption or "")
        elif message.animation:
            await bot.send_animation(chat_id, animation=message.animation.file_id, caption=message.caption or "")
        elif message.voice:
            await bot.send_voice(chat_id, voice=message.voice.file_id, caption=message.caption or "")
        elif message.audio:
            await bot.send_audio(chat_id, audio=message.audio.file_id, caption=message.caption or "")
        elif message.document:
            await bot.send_document(chat_id, document=message.document.file_id, caption=message.caption or "")
        elif message.video_note:
            await bot.send_video_note(chat_id, video_note=message.video_note.file_id)
        elif message.sticker:
            await bot.send_sticker(chat_id, sticker=message.sticker.file_id)
        else:
            await message.reply("⚠️ Этот тип сообщения пока не поддерживается.")
            await state.clear()
            return

        await message.reply(f"✅ Сообщение успешно отправлено в чат <code>{chat_id}</code>.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при отправке: <code>{e}</code>", parse_mode="HTML")

    await state.clear()

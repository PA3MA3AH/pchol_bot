# handlers/start.py
from aiogram import Router
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message
from aiogram import types

router = Router(name="start")


class AllChatsFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type in {"private", "group", "supergroup"}


@router.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    if message.chat.type == "private":
        await message.reply(
            "Привет! Это счётчик отправленных ПЧОЛ 🐝\n\n"
            "Добавь меня в групповой чат (сделай меня админом), и я буду считать все 🐝.\n\n"
            "📋 <b>Основные команды:</b>\n"
            "/pchol — количество ПЧОЛ в чате\n"
            "/top — топ 10 пользователей по 🐝\n\n"
            "💰 <b>Экономика:</b>\n"
            "Кошелёк — работает в любых чатах (Кошелек, кошелёк, Кошелок и т.д.)\n"
            "Переводы: используйте inline — напишите в любом чате @pcholcounterbot N и выберите результат,\n"
            "или укажите ID пользователя в ЛС при переводе.\n"
            "Покупка ферм: /beefarm N (1 мёд = 1000 пчол)\n"
            "Покупка бустов: /beeboost N (1 буст = 5 мёда)\n"
            "Покупка пчол за рубли: /buybee N\n\n"
            "🎴 <b>Карточки Пчол:</b>\n"
            "/beepack N — купить пак карточек (1000 пчол за пак)\n"
            "/beecards — посмотреть коллекцию\n"
            "/upgradecard ID — улучшить карточку за мёд\n\n"
            "⚔️ <b>Дуэли и рейды:</b>\n"
            "/beedefend id1,id2,id3,id4,id5 — поставить защитную команду\n"
            "/beeattack id1,id2,id3,id4,id5 — атаковать рейд или соперника\n\n"
            "💎 <b>NFT Пчолы:</b>\n"
            "/breed_nft id1,id2,id3 — скрестить три 5⭐ карты и получить NFT\n"
            "/giftnft @user ID — передать NFT другому игроку\n"
            "/nft_list — список лотов NFT\n"
            "/nft_sell ID PRICE — выставить NFT на продажу\n"
            "/nft_buy LOT_ID — купить NFT с биржи\n\n"
            "🏆 <b>Достижения:</b>\n"
            "/myachivepchol — ваши достижения и награды\n\n"
            "🎟 <b>Чеки:</b>\n"
            "/check N — создать чек\n"
            "/checkchecks — список чеков\n"
            "/delcheck N — удалить чек\n\n"
            "ℹ️ Для владельца бота — команда /owner",
            parse_mode="HTML",
        )
    else:
        await message.reply("Напиши мне в личные сообщения /start, чтобы увидеть инструкцию.")

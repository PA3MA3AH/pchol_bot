# Pchol Bot

Telegram-бот для подсчёта 🐝 (пчол) в чатах с экономикой, фермами, карточками и NFT.

## Технологии

- Python 3.11+
- aiogram 3.x
- PostgreSQL (asyncpg)
- python-dotenv

## Установка

```bash
pip install -r requirements.txt
```

Создайте `.env` файл:

```
BOT_TOKEN=your_token_here
DATABASE_URL=postgresql://user:pass@host/dbname
OWNER_ID=123456789
```

## Запуск

```bash
python bot.py
```

## Команды

- `/start` — инструкция
- `/pchol` — счётчик пчол в чате
- `/top` — топ-10 пользователей
- `/beefarm N` — купить фермы
- `/beeboost N` — купить бусты
- `/buybee N` — купить пчол за рубли
- `/check N` — создать чек
- `/getpchol N` — мини-игра
- `/beepack N` — купить пак карточек
- `/beecards` — коллекция карточек
- `/beedefend` / `/beeattack` — дуэли
- `/breed_nft`, `/giftnft`, `/nft_sell`, `/nft_buy` — NFT
- `/opros` — создать опрос с призом

## Безопасность

- Атомарные операции с балансом (UPDATE ... WHERE bees >= n)
- Rate limiter в PostgreSQL
- Проверка владельца в callback
- HTML escaping пользовательских данных
- Лимиты на аргументы команд

## Лицензия

MIT

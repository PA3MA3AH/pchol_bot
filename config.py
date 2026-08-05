# config.py
"""
Вся конфигурация читается из переменных окружения — НИКАКИХ токенов/паролей в коде.

Перед запуском задай переменные окружения, например через .env + python-dotenv,
или напрямую в Railway / systemd / Docker:

    BOT_TOKEN=...
    DATABASE_URL=postgresql://...
    OWNER_ID=123456789
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # подхватит .env в корне проекта, если он есть (не коммить .env!)
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

DB_MIN_SIZE = int(os.getenv("DB_MIN_SIZE", "1"))
DB_MAX_SIZE = int(os.getenv("DB_MAX_SIZE", "10"))

if not BOT_TOKEN or not DATABASE_URL or OWNER_ID == 0:
    raise RuntimeError(
        "BOT_TOKEN, DATABASE_URL и OWNER_ID обязательны. "
        "Задай их через переменные окружения (или .env файл), не хардкодь в коде."
    )

BEE = "🐝"
TIMEZONE = "Europe/Moscow"

# ---- экономика ----
RATE_WINDOW = 60             # окно лимита получения пчол, сек
MAX_BEES_PER_WINDOW = 25     # макс пчол в окно на юзера
RAID_COOLDOWN_SECONDS = 120  # кулдаун между рейдами/атаками

BEEFARM_BASE_PRICE = 1000    # базовая цена фермы (удваивается за каждую следующую)
BEEBOOST_PRICE = 5000        # цена одного буста в пчолах
PACK_PRICE = 1000            # цена пака карточек
DUPLICATE_CONVERT_BEES = 100 # компенсация за дубликат карточки

BUYBEE_CARD = os.getenv("BUYBEE_CARD", "")
BUYBEE_BANK = os.getenv("BUYBEE_BANK", "Т-Банк")
BUYBEE_RATE = int(os.getenv("BUYBEE_RATE", "100"))  # N пчол за 1 рубль

# ---- рейды / дуэли ----
RAID_STEAL_PERCENT = 0.05  # 5% от баланса проигравшего
RAID_STEAL_MIN = 100       # минимальный угон пчол
RAID_STEAL_MAX = 50000     # максимальный угон пчол

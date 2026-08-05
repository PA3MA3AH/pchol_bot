-- db/schema.sql
-- Полная схема базы данных бота pchol.
-- ВАЖНО: в исходном файле таблица card_catalog нигде не создавалась,
-- хотя user_cards и nfts.metadata на неё ссылаются (FOREIGN KEY на несуществующую
-- таблицу — это упало бы с ошибкой при первом же запуске на чистой базе).
-- Здесь она добавлена и должна создаваться ДО user_cards.

CREATE TABLE IF NOT EXISTS chats (
    chat_id BIGINT PRIMARY KEY,
    total_bees BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    bees BIGINT NOT NULL DEFAULT 0,
    honey DOUBLE PRECISION NOT NULL DEFAULT 0,
    farms INT NOT NULL DEFAULT 0,
    boosts INT NOT NULL DEFAULT 0,
    username TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    chat_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bees_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, message_id)
);

CREATE TABLE IF NOT EXISTS frozen_users (
    user_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS top_users (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    position INT NOT NULL,
    total_bees BIGINT NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS transfers_log (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE DEFAULT now(),
    sender BIGINT,
    recipient BIGINT,
    recipient_username TEXT,
    amount BIGINT
);

CREATE TABLE IF NOT EXISTS buybee_requests (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT,
    amount BIGINT NOT NULL,
    price_rub NUMERIC(10,2) NOT NULL,
    ts TIMESTAMP WITH TIME ZONE DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'pending'
);

-- ВНИМАНИЕ: в оригинале колонка называлась owner_id при INSERT (create_poll),
-- но в CREATE TABLE её не было — только creator_id. Здесь оставлен creator_id
-- и репозиторий поправлен, чтобы INSERT совпадал со схемой (см. repositories/polls_repo.py).
CREATE TABLE IF NOT EXISTS polls (
    id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    poll_id TEXT NOT NULL,
    message_id BIGINT,
    question TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_option_ids TEXT,
    allow_multiple BOOLEAN DEFAULT FALSE,
    prize_bees INT NOT NULL DEFAULT 0,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- ВНИМАНИЕ: в оригинале poll_answer-хендлер писал в колонки poll_id/option_id,
-- которых в этой таблице не было (было poll_db_id/option_ids) — INSERT падал
-- бы в рантайме. Ниже — согласованный вариант, репозиторий использует его.
CREATE TABLE IF NOT EXISTS poll_votes (
    id BIGSERIAL PRIMARY KEY,
    poll_db_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    option_ids TEXT NOT NULL,
    voted_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    rewarded BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS checks (
    id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    recipient_id BIGINT,
    recipient_username TEXT,
    is_used BOOLEAN DEFAULT FALSE,
    used_by BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    used_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS pchol_game (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    bet BIGINT NOT NULL,
    stage INT NOT NULL DEFAULT 0,
    field TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS card_catalog (
    card_id TEXT PRIMARY KEY,
    class TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    base_hp INT NOT NULL DEFAULT 0,
    base_atk INT NOT NULL DEFAULT 0,
    base_heal INT NOT NULL DEFAULT 0,
    base_support INT NOT NULL DEFAULT 0,
    base_defense INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_cards (
    instance_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    card_id TEXT NOT NULL REFERENCES card_catalog(card_id),
    level INT NOT NULL DEFAULT 1, -- 1..5
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nfts (
    nft_id SERIAL PRIMARY KEY, -- 1..150
    owner BIGINT NOT NULL,
    name TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nft_transfers (
    id BIGSERIAL PRIMARY KEY,
    nft_id INT NOT NULL REFERENCES nfts(nft_id),
    from_user BIGINT,
    to_user BIGINT,
    ts TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id BIGINT NOT NULL,
    achv_key TEXT NOT NULL,
    achieved_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    PRIMARY KEY (user_id, achv_key)
);

CREATE TABLE IF NOT EXISTS nft_marketplace (
    id BIGSERIAL PRIMARY KEY,
    nft_id INT NOT NULL REFERENCES nfts(nft_id),
    seller BIGINT NOT NULL,
    price_bees BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_attack_cards (
    user_id BIGINT PRIMARY KEY,
    card_ids BIGINT[] NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_defense_cards (
    user_id BIGINT PRIMARY KEY,
    card_ids BIGINT[] NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raid_cooldown (
    user_id BIGINT PRIMARY KEY,
    last_attack TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_rate_limits (
    user_id BIGINT PRIMARY KEY,
    window_start BIGINT NOT NULL DEFAULT 0,
    total_bees INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions_log (
    id SERIAL PRIMARY KEY,
    user_from BIGINT,
    user_to BIGINT,
    type TEXT, -- 'NFT_SALE', 'TRANSFER', 'BATTLE_REWARD', ...
    nft_id BIGINT,
    amount BIGINT,
    timestamp TIMESTAMP DEFAULT NOW(),
    details TEXT
);

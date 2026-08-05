# services/raid_logic.py
"""
Движок боя атака vs защита (5 карт на 5 карт).

Идея:
- У каждой карты есть база (hp/atk/heal/support/def) из card_catalog,
  усиленная уровнем карты через level_multiplier (1..5 звёзд).
- Команда — это сумма статов всех 5 карт (простая, предсказуемая модель;
  никакой рандомной вариативности урона — чтобы бой был воспроизводим
  и не превращался в казино поверх казино).
- Бой идёт раундами (максимум MAX_ROUNDS), в каждом раунде:
    1. Обе команды наносят друг другу урон одновременно.
    2. Урон = атака_атакующего - защита_цели*DEF_REDUCTION, но не меньше MIN_DAMAGE.
       Support сторона добавляет часть своего support к атаке (баф урона).
    3. После урона обе стороны лечатся на heal (но не выше max_hp команды).
    4. Если чей-то HP <= 0 — бой окончен, эта сторона проиграла.
- Если после MAX_ROUNDS никто не умер — побеждает та сторона, у которой
  осталось больше % HP от максимума (ничья невозможна: команды почти
  никогда не совпадают тик-в-тик, а если совпали — засчитываем ничью явно).
"""
from dataclasses import dataclass, field
from typing import List

from constants import level_multiplier

MAX_ROUNDS = 20
DEF_REDUCTION = 0.5   # какая доля защиты цели гасит входящий урон
SUPPORT_ATK_BUFF = 0.3  # какая доля суммарного support команды добавляется к её атаке
MIN_DAMAGE = 1


@dataclass
class TeamStats:
    hp: float = 0.0
    max_hp: float = 0.0
    atk: float = 0.0
    heal: float = 0.0
    support: float = 0.0
    defense: float = 0.0
    card_names: List[str] = field(default_factory=list)


def build_team_stats(card_rows) -> TeamStats:
    """card_rows — результат cards_repo.get_cards_full(): по одной строке на карту команды."""
    team = TeamStats()
    for r in card_rows:
        mult = level_multiplier(r["level"])
        team.hp += r["base_hp"] * mult
        team.atk += r["base_atk"] * mult
        team.heal += r["base_heal"] * mult
        team.support += r["base_support"] * mult
        team.defense += r["base_defense"] * mult
        team.card_names.append(f"{r['name']} ({r['level']}⭐)")
    team.max_hp = team.hp
    return team


@dataclass
class BattleResult:
    winner: str          # "attacker" | "defender" | "draw"
    rounds_log: List[str]
    attacker_hp_left: float
    defender_hp_left: float
    attacker_max_hp: float
    defender_max_hp: float


def simulate_battle(attacker: TeamStats, defender: TeamStats) -> BattleResult:
    log = []
    a_hp, d_hp = attacker.hp, defender.hp

    a_effective_atk = attacker.atk + attacker.support * SUPPORT_ATK_BUFF
    d_effective_atk = defender.atk + defender.support * SUPPORT_ATK_BUFF

    dmg_to_defender = max(MIN_DAMAGE, a_effective_atk - defender.defense * DEF_REDUCTION)
    dmg_to_attacker = max(MIN_DAMAGE, d_effective_atk - attacker.defense * DEF_REDUCTION)

    for rnd in range(1, MAX_ROUNDS + 1):
        a_hp -= dmg_to_attacker
        d_hp -= dmg_to_defender

        # лечение после обмена ударами
        a_hp = min(attacker.max_hp, a_hp + attacker.heal)
        d_hp = min(defender.max_hp, d_hp + defender.heal)

        log.append(
            f"Раунд {rnd}: атакующий наносит {dmg_to_defender:.0f} (защита ⇒ HP {max(d_hp,0):.0f}/{defender.max_hp:.0f}), "
            f"защитник наносит {dmg_to_attacker:.0f} (атакующий ⇒ HP {max(a_hp,0):.0f}/{attacker.max_hp:.0f})"
        )

        a_dead = a_hp <= 0
        d_dead = d_hp <= 0
        if a_dead or d_dead:
            if a_dead and d_dead:
                winner = "draw"
            elif d_dead:
                winner = "attacker"
            else:
                winner = "defender"
            return BattleResult(winner, log, max(a_hp, 0), max(d_hp, 0), attacker.max_hp, defender.max_hp)

    # никто не умер за MAX_ROUNDS — считаем по % оставшегося HP
    a_pct = a_hp / attacker.max_hp if attacker.max_hp else 0
    d_pct = d_hp / defender.max_hp if defender.max_hp else 0
    if abs(a_pct - d_pct) < 1e-6:
        winner = "draw"
    else:
        winner = "attacker" if a_pct > d_pct else "defender"

    return BattleResult(winner, log, max(a_hp, 0), max(d_hp, 0), attacker.max_hp, defender.max_hp)

# states.py
from aiogram.fsm.state import State, StatesGroup


class PcholTextStates(StatesGroup):
    waiting_for_text = State()


class PollCreationStates(StatesGroup):
    # используем ручной словарь-сессию (как в оригинале), но состояния
    # можно перевести на нормальный aiogram FSM позже — пока оставлено
    # как есть для совместимости поведения.
    pass

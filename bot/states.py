"""aiogram FSM holatlari (StateGroup'lar)."""

from aiogram.fsm.state import State, StatesGroup


class RoleStates(StatesGroup):
    """Rol tanlash."""

    choosing = State()


class ExecutorStates(StatesGroup):
    """Ijrochi yo'nalishlarini tanlash oqimi."""

    choose_category = State()
    choose_skill = State()


class CustomerStates(StatesGroup):
    """Buyurtmachi oqimi (qadamma-qadam)."""

    choose_category = State()
    choose_skill = State()
    custom_skill = State()
    description = State()
    budget = State()
    deadline = State()
    confirm = State()


class ComplaintStates(StatesGroup):
    """Shikoyat matnini yozish."""

    text = State()


class RelayStates(StatesGroup):
    """Bot orqali xabar yuborish (relay) rejimi."""

    chat = State()


class AdminStates(StatesGroup):
    """Admin buyruqlari."""

    addskill_category = State()
    addskill_skill = State()
    broadcast = State()

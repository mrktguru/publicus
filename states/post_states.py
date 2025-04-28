from aiogram.fsm.state import StatesGroup, State

class ManualPostStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_choice = State()
    waiting_for_datetime = State()
    waiting_for_confirm = State()

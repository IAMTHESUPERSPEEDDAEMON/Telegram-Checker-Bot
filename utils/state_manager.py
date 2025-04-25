from typing import Dict, Optional

class StateManager:
    def __init__(self):
        # В простейшем варианте просто словарь в памяти
        self._states: Dict[int, str] = {}

    def set_state(self, user_id: int, state: str) -> None:
        self._states[user_id] = state

    def get_state(self, user_id: int) -> Optional[str]:
        return self._states.get(user_id)

    def clear_state(self, user_id: int) -> None:
        self._states.pop(user_id, None)

    def has_state(self, user_id: int, state: str) -> bool:
        return self._states.get(user_id) == state
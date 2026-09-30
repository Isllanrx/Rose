import unittest

from state import SharedState
from threads.utilities.skin_name_resolver import SkinNameResolver
from ui.chroma.selection_handler import ChromaSelectionHandler


class RandomModeChromaSelectionTests(unittest.TestCase):
    """Log 16-09-2026 18:24: dice drew 21018, user then picked 21069 via chroma wheel, 21018 was injected."""

    def _state_with_random_mode(self) -> SharedState:
        state = SharedState()
        state.locked_champ_id = 21
        state.last_hovered_skin_id = 21069
        state.random_skin_name = "Miss Fortune Feiticeira"
        state.random_skin_id = 21018
        state.random_mode_active = True
        return state

    def test_explicit_chroma_selection_overrides_random_skin(self):
        state = self._state_with_random_mode()

        ChromaSelectionHandler(state, current_skin_id=21069).handle_selection(21069, "Default")

        self.assertFalse(state.random_mode_active)
        self.assertIsNone(state.random_skin_id)
        self.assertEqual(SkinNameResolver(state).resolve_injection_name(), "skin_21069")

    def test_base_skin_selection_overrides_random_skin(self):
        state = self._state_with_random_mode()

        ChromaSelectionHandler(state, current_skin_id=21069).handle_selection(0, "Base")

        self.assertFalse(state.random_mode_active)

    def test_selecting_the_random_skin_keeps_random_mode(self):
        state = self._state_with_random_mode()

        ChromaSelectionHandler(state, current_skin_id=21018).handle_selection(21018, "Default")

        self.assertTrue(state.random_mode_active)
        self.assertEqual(SkinNameResolver(state).resolve_injection_name(), "skin_21018")


if __name__ == "__main__":
    unittest.main()

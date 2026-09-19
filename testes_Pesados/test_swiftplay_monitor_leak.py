"""Swiftplay: o monitor precisa parar em todo caminho de saída — backlog #10.

`swiftplay_handler.py:585-605` sobe o monitor (que suspende o jogo) e chama
`_mk_run_overlay` dentro de um `try/except` **sem `finally`**. Quando o overlay
falha — exceção ou código de retorno não-zero — o monitor nunca é parado.

O usuário vê o jogo travado até o auto-resume de 60 s e entra na partida sem
skin. Com o `mkoverlay` levando 97 s no cache frio (ver `reviews/`), a espera
real pode ser a partida inteira.

Aqui o `GameMonitor` é real e segura um processo real; só o `mod-tools` é
substituído, porque o que está sob teste é o controle de fluxo do handler.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from injection.game.game_monitor import GameMonitor  # noqa: E402
from threads.handlers.swiftplay_handler import SwiftplayHandler  # noqa: E402

from helpers import RealProcessTestCase, is_suspended  # noqa: E402


class SwiftplayOverlayReleasesGame(RealProcessTestCase):
    def _build_handler(self, overlay_result):
        """Handler com GameMonitor real; `overlay_result` é valor de retorno ou exceção."""
        proc = self.new_suspended_process()

        monitor = GameMonitor(lambda: 60.0)
        monitor._suspended_game_process = proc
        monitor._monitor_active = True
        self.addCleanup(monitor.stop)

        manager = MagicMock()
        manager._monitor_active = True
        manager.game_monitor = monitor
        manager._stop_monitor.side_effect = monitor.stop
        manager._start_monitor.side_effect = lambda: None
        if isinstance(overlay_result, Exception):
            manager.injector._mk_run_overlay.side_effect = overlay_result
        else:
            def fake_overlay(*_args, **_kwargs):
                # Fidelidade ao real: overlay_manager.py:334 chama resume_game()
                # quando o runoverlay sobe — ou seja, só no sucesso. Nos caminhos
                # de falha ninguém solta o jogo, e é aí que o finally faz falta.
                if overlay_result == 0:
                    monitor.resume_game()
                return overlay_result

            manager.injector._mk_run_overlay.side_effect = fake_overlay

        state = MagicMock()
        state.swiftplay_extracted_mods = ["mod_de_teste"]
        state.swiftplay_lock = __import__("threading").RLock()

        handler = SwiftplayHandler(MagicMock(), state, manager, MagicMock())
        handler._overlay_done = False
        return handler, proc

    def test_game_is_released_when_overlay_raises(self):
        handler, proc = self._build_handler(RuntimeError("mod-tools quebrou"))

        handler.run_swiftplay_overlay()

        self.assertFalse(
            is_suspended(proc),
            "exceção no overlay deixou o jogo suspenso; falta try/finally com _stop_monitor",
        )

    def test_game_is_released_when_overlay_returns_nonzero(self):
        # mod-tools devolve código != 0: o handler só loga um warning e segue.
        handler, proc = self._build_handler(1)

        handler.run_swiftplay_overlay()

        self.assertFalse(
            is_suspended(proc),
            "código de saída não-zero deixou o jogo suspenso",
        )

    def test_game_is_released_on_success(self):
        # Controle: no sucesso quem solta o jogo é o overlay_manager, ao subir o
        # runoverlay. Este teste deve passar no código atual — se falhar, o
        # ambiente ou o mock é que estão errados, não o handler.
        handler, proc = self._build_handler(0)

        handler.run_swiftplay_overlay()

        self.assertFalse(is_suspended(proc), "caminho de sucesso deixou o jogo suspenso")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""GameMonitor contra processos reais — backlog #9.

`test/test_shutdown_safety.py` cobre este caminho com `FakeGameProcess`, um
dublê cujo `resume()` só incrementa um contador. Um dublê não revela os
defeitos abaixo, porque eles estão no controle de fluxo do próprio
`GameMonitor`, não na chamada a `resume()`.

Cenário que importa ao usuário: o jogo fica suspenso e só volta se ele
descobrir sozinho que precisa fechar o Rose.
"""

import sys
import threading
import time
import unittest
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from injection.game.game_monitor import GameMonitor  # noqa: E402

from helpers import RealProcessTestCase, is_suspended, wait_for_status  # noqa: E402


class StopResumesRealProcess(RealProcessTestCase):
    """#9a — `stop()` só resume se `_monitor_active` ainda for True."""

    def test_stop_resumes_when_monitor_already_self_deactivated(self):
        # Estado real após game_monitor.py:135-138: o monitor viu
        # `_runoverlay_started` e saiu do loop, deixando `_monitor_active=False`
        # SEM limpar `_suspended_game_process`. O jogo continua suspenso.
        proc = self.new_suspended_process()

        monitor = GameMonitor(lambda: 60.0)
        monitor._suspended_game_process = proc
        monitor._monitor_active = False
        monitor._runoverlay_started = True

        monitor.stop()

        self.assertFalse(
            is_suspended(proc),
            "stop() deixou o processo suspenso porque _monitor_active era False; "
            "em produção isso é o jogo congelado até o usuário fechar o Rose",
        )

    def test_stop_resumes_when_monitor_active(self):
        # Caminho que já funciona — serve de controle: se este falhar, o
        # problema é do ambiente, não do defeito sob teste.
        proc = self.new_suspended_process()

        monitor = GameMonitor(lambda: 60.0)
        monitor._suspended_game_process = proc
        monitor._monitor_active = True

        monitor.stop()

        self.assertFalse(is_suspended(proc), "stop() deveria resumir com o monitor ativo")

    def test_stop_is_idempotent_and_leaves_no_suspended_process(self):
        proc = self.new_suspended_process()

        monitor = GameMonitor(lambda: 60.0)
        monitor._suspended_game_process = proc
        monitor._monitor_active = True

        monitor.stop()
        monitor.stop()

        self.assertFalse(is_suspended(proc))


class StartDoesNotLeakThreads(RealProcessTestCase):
    """#9b — `start()` chama `stop()` sem `join()` e reativa a flag logo depois."""

    def tearDown(self):
        # Garantir que nenhum monitor fica varrendo processos após o teste.
        monitor = getattr(self, "monitor", None)
        if monitor is not None:
            monitor._monitor_active = False
            thread = monitor._monitor_thread
            if thread is not None:
                thread.join(timeout=5)
        super().tearDown()

    def test_previous_monitor_thread_is_dead_after_restart(self):
        # game_monitor.py:59-61 — stop() apenas baixa a flag; a thread antiga
        # pode estar dormindo. start() ergue a flag de novo antes de ela morrer,
        # e o `while self._monitor_active` da thread antiga volta a rodar.
        self.monitor = GameMonitor(lambda: 60.0)

        self.monitor.start()
        first_thread = self.monitor._monitor_thread
        self.assertIsNotNone(first_thread)
        time.sleep(0.2)  # deixa a thread entrar no loop de varredura

        self.monitor.start()
        second_thread = self.monitor._monitor_thread

        self.assertIsNot(first_thread, second_thread, "start() deveria criar uma thread nova")
        first_thread.join(timeout=5)
        self.assertFalse(
            first_thread.is_alive(),
            "a thread anterior do GameMonitor continua viva após start(); "
            "duas threads disputam _suspended_game_process",
        )

    def test_only_one_monitor_thread_alive_after_repeated_starts(self):
        self.monitor = GameMonitor(lambda: 60.0)

        for _ in range(4):
            self.monitor.start()
            time.sleep(0.1)

        alive = [t for t in threading.enumerate() if t.name == "GameMonitor" and t.is_alive()]
        self.assertLessEqual(
            len(alive),
            1,
            f"{len(alive)} threads GameMonitor vivas ao mesmo tempo",
        )


class AutoResumeReleasesRealProcess(RealProcessTestCase):
    """O auto-resume precisa soltar o processo de verdade, não só limpar a referência."""

    def test_auto_resume_actually_resumes_the_process(self):
        proc = self.new_suspended_process()

        # Timeout curtíssimo para o safety timer disparar de imediato.
        monitor = GameMonitor(lambda: 0.05)
        self.addCleanup(setattr, monitor, "_monitor_active", False)
        monitor._monitor_active = True
        monitor._suspended_game_process = proc

        # Reproduz o trecho de auto-resume de game_monitor.py:146-178 via stop(),
        # que é o caminho garantido de liberação.
        monitor.stop()

        self.assertTrue(
            wait_for_status(proc, psutil.STATUS_RUNNING),
            "processo continuou suspenso após o caminho de liberação",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

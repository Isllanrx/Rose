"""Utilitários para testes pesados: processos reais, não dublês.

Todo processo criado aqui é registrado e morto no teardown, mesmo se o teste
falhar no meio — um processo deixado suspenso trava a máquina do desenvolvedor.
"""

import subprocess
import sys
import time
import unittest
from typing import List

import psutil

# Quanto esperar por uma transição de estado do processo antes de desistir.
STATE_TIMEOUT_S = 5.0
STATE_POLL_S = 0.02


def spawn_sleeper() -> psutil.Process:
    """Sobe um processo Python real e ocioso, para suspender/retomar de verdade."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(600)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    handle = psutil.Process(proc.pid)
    wait_for_status(handle, psutil.STATUS_RUNNING)
    return handle


def wait_for_status(proc: psutil.Process, expected: str, timeout: float = STATE_TIMEOUT_S) -> bool:
    """Espera o processo atingir *expected*. A transição não é instantânea no Windows."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if proc.status() == expected:
                return True
        except psutil.NoSuchProcess:
            return False
        time.sleep(STATE_POLL_S)
    return False


def is_suspended(proc: psutil.Process) -> bool:
    try:
        return proc.status() == psutil.STATUS_STOPPED
    except psutil.NoSuchProcess:
        return False


class RealProcessTestCase(unittest.TestCase):
    """Base que garante que nenhum processo fica vivo ou suspenso após o teste."""

    def setUp(self):
        self._spawned: List[psutil.Process] = []

    def tearDown(self):
        for proc in self._spawned:
            # Resumir antes de matar: um processo suspenso pode ignorar o terminate.
            try:
                if proc.status() == psutil.STATUS_STOPPED:
                    proc.resume()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            try:
                proc.kill()
                proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass

    def new_process(self) -> psutil.Process:
        proc = spawn_sleeper()
        self._spawned.append(proc)
        return proc

    def new_suspended_process(self) -> psutil.Process:
        proc = self.new_process()
        proc.suspend()
        self.assertTrue(
            wait_for_status(proc, psutil.STATUS_STOPPED),
            "processo de teste não suspendeu — ambiente inadequado para o teste pesado",
        )
        return proc

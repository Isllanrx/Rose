"""Processos externos não podem bloquear para sempre — backlog #12.

`utils/integration/pengu_loader.py:396` chama `subprocess.run` sem `timeout=`.
Se o `Pengu Loader.exe` travar — cliente em estado ruim, disco lento, handle
preso —, a chamada bloqueia indefinidamente.

No caminho de cleanup isso é o Rose que **nunca fecha**: a bandeja some, o
processo fica, e se havia um jogo suspenso ele não volta. O usuário mata pelo
gerenciador de tarefas.

O teste não depende do binário real: substitui `subprocess.run` por um dublê
que honra `timeout` quando ele é passado e trava quando não é — exatamente o
contrato do stdlib. O que se mede é se a chamada retorna em tempo finito.
"""

import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.integration import pengu_loader  # noqa: E402

# Quanto um processo travado "demoraria": muito além de qualquer espera aceitável.
HUNG_PROCESS_SECONDS = 120.0
# Teto de espera derivado do timeout que o próprio módulo declara, com folga
# para o agendamento da thread. Amarrar a um número fixo faria o teste falhar
# na borda exata quando os dois valores coincidem.
CONFIGURED_TIMEOUT_S = getattr(pengu_loader, "_CLI_TIMEOUT_S", None)
ACCEPTABLE_RETURN_S = (CONFIGURED_TIMEOUT_S + 10.0) if CONFIGURED_TIMEOUT_S else 20.0


class FakeCompleted:
    def __init__(self):
        self.stdout = ""
        self.stderr = ""
        self.returncode = 0


def hanging_run(*_args, **kwargs):
    """Dublê de subprocess.run: honra `timeout`, trava quando não recebe um."""
    timeout = kwargs.get("timeout")
    if timeout is None:
        time.sleep(HUNG_PROCESS_SECONDS)
        return FakeCompleted()
    time.sleep(min(timeout, HUNG_PROCESS_SECONDS))
    raise subprocess.TimeoutExpired(cmd="pengu", timeout=timeout)


class PenguCliDoesNotHangForever(unittest.TestCase):
    def test_cli_call_returns_even_when_process_hangs(self):
        with patch.object(pengu_loader, "_is_available", return_value=True), \
             patch.object(pengu_loader.subprocess, "run", side_effect=hanging_run):

            done = threading.Event()
            result_box = {}

            def call():
                try:
                    result_box["result"] = pengu_loader._run_cli_result(["--version"])
                except BaseException as exc:  # noqa: BLE001 - queremos ver qualquer saída
                    result_box["error"] = exc
                finally:
                    done.set()

            worker = threading.Thread(target=call, daemon=True, name="PenguCliProbe")
            started = time.monotonic()
            worker.start()
            returned = done.wait(timeout=ACCEPTABLE_RETURN_S)
            elapsed = time.monotonic() - started

        self.assertTrue(
            returned,
            f"_run_cli_result não retornou em {ACCEPTABLE_RETURN_S:.0f}s com o processo travado; "
            "falta timeout= no subprocess.run (pengu_loader.py:396). No cleanup isso trava o shutdown",
        )
        self.assertLess(elapsed, ACCEPTABLE_RETURN_S)

    def test_timeout_expired_is_handled_and_not_propagated(self):
        # Mesmo com timeout, a exceção precisa ser tratada: um TimeoutExpired
        # subindo pela thread de cleanup aborta as etapas seguintes (ADR-007).
        def always_timeout(*_args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="pengu", timeout=kwargs.get("timeout") or 1)

        with patch.object(pengu_loader, "_is_available", return_value=True), \
             patch.object(pengu_loader.subprocess, "run", side_effect=always_timeout):
            try:
                result = pengu_loader._run_cli_result(["--version"])
            except subprocess.TimeoutExpired:
                self.fail(
                    "TimeoutExpired escapou de _run_cli_result; o cleanup pararia na metade"
                )

        self.assertIsNone(result, "falha de timeout deveria virar None, como os demais erros")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Runner da suíte pesada, com veredito de aptidão para produção.

Diferente de `test/`, uma falha aqui **não** significa teste quebrado: significa
defeito no produto. Os testes foram escritos a partir de defeitos confirmados no
código (backlog #9, #10, #12), então falham até que o código seja corrigido.

Uso:
    .venv\\Scripts\\python testes_Pesados\\run_all.py
"""

import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

# Falha aqui -> item do backlog que ela comprova.
BACKLOG_MAP = {
    "StopResumesRealProcess": "#9a  stop() não resume com o monitor auto-desativado",
    "StartDoesNotLeakThreads": "#9b  start() sem join deixa threads GameMonitor vivas",
    "AutoResumeReleasesRealProcess": "#9   auto-resume não solta o processo",
    "SwiftplayOverlayReleasesGame": "#10  Swiftplay sem try/finally: jogo suspenso",
    "PenguCliDoesNotHangForever": "#12  Pengu CLI sem timeout trava o shutdown",
    "SkinLibraryResolvesAgainstInstalledGame": "--   integridade da biblioteca no patch atual",
}


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(HERE), pattern="test_*.py")

    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    elapsed = time.monotonic() - started

    problems = list(result.failures) + list(result.errors)
    affected = []
    for case, _ in problems:
        name = case.__class__.__name__
        entry = BACKLOG_MAP.get(name, f"--   {name}")
        if entry not in affected:
            affected.append(entry)

    print()
    print("=" * 72)
    print(f"SUÍTE PESADA — {result.testsRun} testes em {elapsed:.1f}s")
    print("=" * 72)

    if not problems:
        print("APTO: nenhum defeito reproduzido pelos cenários cobertos.")
        print()
        print("Ressalva: isto cobre suspend/resume, vazamento de monitor, timeout")
        print("de processo externo e integridade da biblioteca. NÃO cobre o ciclo")
        print("real de mkoverlay/runoverlay nem o Teste C (fechar o Rose em partida).")
        return 0

    print(f"NÃO APTO: {len(problems)} de {result.testsRun} cenários reproduzem defeito.")
    print()
    print("Itens do backlog comprovados:")
    for entry in affected:
        print(f"  {entry}")
    print()
    print("Cada falha acima é um caminho em que o usuário perde a partida:")
    print("jogo congelado, skin ausente sem erro, ou Rose que não fecha.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

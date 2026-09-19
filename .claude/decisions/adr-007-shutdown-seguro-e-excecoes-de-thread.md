# ADR-007 — Shutdown retoma o jogo e exceções de thread vão para o log

- **Status:** aceito (teste in-game de fechar pela bandeja pendente)
- **Data:** 2026-09-17

## Contexto
- `NtSuspendProcess` continua valendo depois que o processo que suspendeu termina. `perform_cleanup` matava o `mod-tools.exe` sem retomar o jogo: fechar o Rose durante o `mkoverlay` deixava o League congelado para sempre.
- `pengu_loader.deactivate_on_exit()` era a primeira etapa do cleanup, fora de try: uma exceção pulava matar o mod-tools e liberar o lockfile.
- O build roda com `console=False` e não havia `threading.excepthook`: uma exceção não tratada matava a thread de fases/ticker/monitor sem nenhum rastro no log.

## Decisão
- Cleanup: `injection_manager.resume_if_suspended()` como primeira etapa, antes de desativar o Pengu e matar o mod-tools; cada etapa com seu próprio try + WARNING.
- `utils.core.logging.install_uncaught_exception_logging()` (chamado após `setup_logging`) registra `threading.excepthook` que loga CRITICAL com traceback e delega ao hook anterior; idempotente; ignora `SystemExit`.

## Alternativas consideradas
- **Try/except dentro dos loops das threads**: muda comportamento (a thread sobrevive e pode repetir a ação — no ticker a 1000 Hz dispararia injeções em série). Fica para a etapa 3, em volta do loop.
- **Retomar só no `GameMonitor.stop()`**: `stop()` não age quando o monitor já saiu (`_monitor_active=False`), exatamente o caso da corrida.

## Consequências
- Fechar o Rose nunca deixa o jogo suspenso quando há referência ao processo suspenso.
- Thread morta passa a aparecer como `Uncaught exception in thread <nome>` no `rose_*.log`.
- Não cobre a corrida suspend/resume dentro do monitor nem os caminhos de custom mod/Swiftplay (etapa 3, backlog).
- Testes: `test/test_shutdown_safety.py` (12).

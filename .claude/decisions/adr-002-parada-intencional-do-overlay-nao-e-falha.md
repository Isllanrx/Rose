# ADR-002 — Parada intencional do overlay não é falha de injeção

- **Status:** aceito
- **Data:** 2026-09-16

## Contexto
Ao fechar o Rose durante a partida, `perform_cleanup` encerra todos os `mod-tools.exe`. `psutil.terminate()` no Windows faz o `runoverlay` sair com código 15, e `overlay_manager` tratava qualquer código ≠ 0 como falha, gerando `INJECTION FAILED` e `report_issue` mesmo com o overlay tendo rodado normalmente.

## Decisão
`ProcessManager` mantém a flag `stop_requested`, ligada sempre que o próprio Rose encerra overlay (`stop_overlay_process`, `kill_all_runoverlay_processes`, `kill_all_modtools_processes`) e zerada antes de cada `runoverlay`. Se o processo sai com código ≠ 0 e a flag está ligada, o resultado é 0 com log INFO `runoverlay stopped by Rose`, mesmo tratamento já dado ao fim de partida via `stop_callback`.

## Alternativas consideradas
- **Ignorar especificamente o código 15**: um crash real com 15 seria mascarado.
- **Reordenar o cleanup para parar a thread de injeção antes de matar processos**: a thread fica bloqueada no loop do overlay; exigiria sinalização equivalente e alteraria o timing de shutdown.
- **Passar `stop_callback` ligado a `state.stop` em todos os caminhos**: não cobre paradas de limpeza de lobby iniciadas fora da thread.

## Consequências
- Sem falsos `INJECTION FAILED`; historic mode registra a skin (o overlay de fato rodou).
- Crash real do `runoverlay` continua reportado (flag zerada antes do start).
- Coberto por `RunOverlayStopTests` e validado com `mod-tools.exe` real (15 → 0).

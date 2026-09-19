---
updated: 2026-09-18
sprint: 2026-09-18 — Hardening etapa 3 (recursos não liberados em caminho de erro)
---

# Sprint atual

## Estado: correções prontas, **não commitadas**, aguardando teste do usuário

As três correções estão no working tree de `main`. Os commits foram feitos e depois revertidos
a pedido do usuário (`git reset --mixed`), então **não existem SHAs** — o histórico segue em
`45b24701`. Backup do patch completo em `scratchpad/backup/todas-as-correcoes.patch`.

```
M  injection/game/game_monitor.py         #9
M  threads/handlers/swiftplay_handler.py  #10
M  utils/integration/pengu_loader.py      #12
?? testes_Pesados/
```

Quando o usuário aprovar: commitar em inglês, Conventional Commits, **sem `Co-Authored-By`**.

## Objetivo
Nenhum caminho de erro deixa o jogo suspenso, o Rose aberto ou uma thread órfã.

## Base de validação
`testes_Pesados/` — 14 cenários com processos reais do Windows, não dublês.
`test/test_shutdown_safety.py` usa 11 mocks para 12 testes e faz
`manager._stop_monitor = MagicMock()`, substituindo justamente o objeto defeituoso.

Rodar: `.venv\Scripts\python testes_Pesados\run_all.py`
Falha ali é defeito no produto, não teste quebrado.

## Correções
| Item | O que mudou | Validação old vs new |
|---|---|---|
| #12 Pengu CLI trava o shutdown | `timeout=15s` + `except TimeoutExpired` (herda de `SubprocessError`, não de `OSError` — só o timeout deixaria a exceção abortar o cleanup) | 2 falhas → OK |
| #10 Swiftplay deixa o jogo suspenso | `try/finally` com `_stop_monitor()`. Só o sucesso soltava o jogo, via `overlay_manager.py:334` | 2 falhas → OK |
| #9 GameMonitor | `stop()` resume fora da guarda `_monitor_active`; `start()` faz `join(3s)` e recusa segunda thread; `RLock` no `_suspended_game_process` (11 pontos de escrita) | 3 falhas → OK |

Placar da suíte pesada: **7 → 5 → 3 → 0 de 14**. Os 107 testes de `test/` sem regressão.
Lint: 66 → 67 (o novo é um `TRY400` deliberado — traceback não agrega num timeout; backlog #34).

## Decisão pendente do usuário
`start()` pode agora retornar **sem ativar o monitor** se a thread anterior não morrer em 3 s.
Os chamadores (`manager.py:180, 316`) não checam retorno, então nesse caso o jogo não é suspenso
e a injeção pode falhar — com WARNING no log. Preferível a duas threads disputando o mesmo
processo, mas é trade-off consciente.

## Build gerado (não testado in-game)
`dist\Rose\Rose.exe` 4,6 MB, 18/09 23:13, `BUILD COMPLETED SUCCESSFULLY`.
Correções confirmadas **dentro do bytecode** (PYZ extraído, não só exit code).
`cslol-dll.dll` e `hashes.game.txt` restaurados após o build limpar o `dist`.

Dois alertas: `Pengu Loader.exe` saiu **sem assinatura** (ADR-003) — com Smart App Control ativo
este build não roda; para teste real, substituir pelo oficial. `Rose.exe` sem VERSIONINFO (#4).

## Pendente
- **Teste C** in-game: fechar o Rose pela bandeja durante a partida. Vale mais agora que o #9 mudou.
- #11 (overlay do Swiftplay na PhaseThread, loop do `loadout_ticker` sem try externo), #13, #25.
- Antes de PR: caminhos absolutos com nome de usuário em `test/test_classic_skins.py:467,478,493`;
  decidir `.claude/` e `.claudeignore` juntos (#2b); atualizar #24.

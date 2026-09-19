---
updated: 2026-09-19
sprint: 2026-09-19 — Consolidação em dev + otimização de memória
---

# Sprint atual

## Fluxo de branches (definido em 2026-09-19)

```
correção → branch própria → validação → merge em dev → (depois) main
```

- **`main`** — espelha o layout do repositório upstream do Rose. Só código-fonte.
  Nada de `.claude/`, `test/` (além de `test_pengu_loader.py`, que já era rastreado
  upstream) ou `testes_Pesados/`. É a branch de onde sai o PR.
- **`dev`** — branch de integração, carrega todo o ferramental local.
- `dev` → `main` **não é prioridade agora** e quando acontecer precisa ser
  **seletiva** (cherry-pick dos commits de fonte), nunca merge inteiro, senão o
  ferramental vaza para a `main`.

Por isso o `.gitignore` é **idêntico nas duas branches** e continua excluindo
`.claude/`, `/test/` e `testes_Pesados/`; na `dev` eles entraram com `git add -f`.
Arquivo **novo** dentro dessas pastas precisa de `-f` para ser rastreado.

## Estado: `dev` em `021ceace`, `main` intacta em `45b24701`

```
021ceace merge(dev): stream the hash table download
 ├ 893565af test(hashes): pin the streamed output to the previous merge
 └ 92df2f25 perf(hashes): stream the hash table instead of merging it in memory
655af3b5 chore(dev): track project context, tests and heavy suites
7326b284 chore(gitignore): ignore local tooling and scratch directories
938bcad5 merge(dev): prod hardening stage 3 after heavy-suite validation
 ├ 09c515e9 fix(monitor): never leave the game suspended or the monitor duplicated
 ├ 392beec9 fix(swiftplay): release the suspended game on every exit path
 └ e51154a4 fix(pengu): bound the CLI call so cleanup cannot hang forever
45b24701 ← main
```

Branches `fix/prod-hardening` e `perf/hashes-memory` foram apagadas após o merge.
Backup do working tree original: `%TEMP%\rose-backup\working-tree-20260919-090408.patch`.

## Hardening etapa 3 — commitado

| Item | O que mudou | Validação |
|---|---|---|
| #12 Pengu CLI trava o shutdown | `timeout=15s` + `except TimeoutExpired` (herda de `SubprocessError`, não de `OSError`) | 2 falhas → OK |
| #10 Swiftplay deixa o jogo suspenso | `try/finally` com `_stop_monitor()` | 2 falhas → OK |
| #9 GameMonitor | `stop()` resume fora da guarda `_monitor_active`; `start()` faz `join(3s)` e recusa segunda thread; `RLock` no `_suspended_game_process` | 3 falhas → OK |

Descartado do working tree: um diff em `classic_skin_builder.py` que removia uma
linha em branco entre funções de topo (quebra E302 do PEP 8, sem relação com as
correções).

### Decisão pendente do usuário
`start()` pode retornar **sem ativar o monitor** se a thread anterior não morrer em
3 s. Os chamadores (`manager.py:180, 316`) não checam retorno, então nesse caso o
jogo não é suspenso e a injeção pode falhar — com WARNING no log. Preferível a duas
threads disputando o mesmo processo, mas é trade-off consciente.

## Otimização de memória — commitado

`download_and_merge_hashes` mantinha **quatro cópias** da tabela de 230 MB vivas ao
mesmo tempo (blobs crus + strings decodificadas + string concatenada + bytes finais).

| Medição no arquivo real (230.694.084 bytes) | Antes | Depois |
|---|---|---|
| Pico de RSS acima da base | **+923 MB** | **+0 MB** |
| SHA-256 da saída | `319c36d2…` | `319c36d2…` (idêntico) |

Ganho extra: escrita via `atomic_write` (`durable=False`, ADR-006) — uma parte que
falha no meio do download não deixa tabela truncada; o arquivo anterior permanece.

Cobertura: `test/test_hashes_streaming.py`, 9 testes / 576 combinações de fragmentos
comparadas contra o algoritmo antigo, em 7 tamanhos de chunk.

## Base de validação
- `.venv\Scripts\python -m unittest discover -s test` → **116 OK** (3 skipped)
- `.venv\Scripts\python testes_Pesados\run_all.py` → **11 OK**, veredito `APTO`

## Pendente
- **Teste C** in-game: fechar o Rose pela bandeja durante a partida. Vale mais agora
  que o #9 mudou. Build atual tem `Pengu Loader.exe` **sem assinatura** (ADR-003) —
  substituir pelo oficial antes de testar.
- Próxima etapa da otimização: **#45**, índice binário persistente (`mmap` + `u64`
  ordenado + `bisect`) para substituir a varredura linear de 6,65 s da tabela de
  hashes. É o que destrava #13 (mkoverlay no cache frio) e #44 (classificador de
  compatibilidade). Decisão sobre camada nativa só **depois** desse número.
- #11 (overlay do Swiftplay na PhaseThread, loop do `loadout_ticker` sem try externo),
  #13, #25.
- Registrar no backlog os oito itens de gap do Padrão 2026 (#48–#55) levantados em
  2026-09-19.

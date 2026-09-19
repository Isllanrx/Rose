---
updated: 2026-09-19
sprint: 2026-09-19 — Hardening etapa 3, otimização e índice de WADs, validados in-game
---

# Sprint atual

## Fluxo de branches (confirmado pelo usuário em 2026-09-19)

```
nova correção → branch própria → validação → merge em dev
dev (pré-validada) → main, quando tudo passar na dev
```

- **Toda correção nasce em branch própria** (`fix/*`, `perf/*`). Nunca commitar
  correção direto em `dev` ou `main`.
- **`dev`** é a área pré-validada: só recebe o que já passou.
- **`main`** recebe a `dev` inteira quando tudo estiver validado. `main` precisa
  respeitar o layout do repositório upstream do Rose para o PR ser aceitável.

### Conflito em aberto neste fluxo

A `dev` carrega `.claude/`, `test/` e `testes_Pesados/` **commitados** (`655af3b5`).
Se a `dev` inteira for para a `main`, esse ferramental vai junto e a `main` deixa de
respeitar o layout upstream. As duas regras não cabem ao mesmo tempo.

Opções, com a recomendação primeiro:

1. **Mover o ferramental para uma branch `tooling` própria**, deixando a `dev` só com
   código-fonte. Aí `dev` → `main` vira merge limpo e o fluxo funciona como descrito.
   Exige reescrever a história local da `dev` (ela não foi publicada, então é seguro).
2. Promoção seletiva (cherry-pick dos commits de fonte). Funciona, mas contraria o
   "a dev inteira vai pra main".
3. Aceitar o ferramental na `main` e não abrir PR upstream.

**Decisão do usuário pendente.**

## Estado

```
dev   3b5180f2   (20 commits à frente)
main  45b24701   intacta, igual a origin/main
```

Branches `fix/prod-hardening` e `perf/hashes-memory` apagadas após o merge.
Backup do working tree original: `%TEMP%\rose-backup\working-tree-20260919-090408.patch`.

## Validação sistemática de 2026-09-19 — passou (rodada 1, antes do #45)

| Verificação | Resultado |
|---|---|
| Estado git (output bruto) | `dev` 11 commits à frente, `main` intacta, working tree limpo |
| Compilação de todo o código | OK |
| Import dos 10 módulos críticos | OK |
| Suíte unitária | **116 OK**, 3 skipped |
| Suíte pesada | **14 testes, 12 OK**, 2 skipped |
| Diferencial hardening contra `45b24701` | **7 falhas no antigo → 0 no novo** |
| Diferencial memória (`tracemalloc`, entrada real de 231 MB) | **692 MB → 2,1 MB** de pico alocado |
| Identidade da saída do streaming | SHA-256 igual em 230.694.084 bytes |
| Resíduos | nenhum `.tmp`; `hashes.game.txt` intacto |

### Armadilhas descobertas durante a validação

- **O rtk filtra o output do git.** `git log main..dev` mostrou 9 commits; o real são
  11 (escondeu os dois merges). E `grep` sobre `git diff --cached` lê o **resumo**, não
  o conteúdo — uma varredura de segredos feita assim não vale nada. Para validação,
  usar `rtk proxy <cmd>`.
- **`get_skins_dir()` cria o diretório** ao ser chamada. Isso mascara a ausência da
  biblioteca e alterou a contagem da suíte pesada de 11 para 14 testes no meio da
  validação (destravou um `setUpClass` que antes pulava a classe inteira).
- **Worktree órfão** de sessão anterior com o commit `4435f694` fora da história da
  `dev`. Conferido arquivo por arquivo: só difere em CRLF, nada perdido. Pode remover.

## Concluído nesta sprint

**Hardening etapa 3** — #9 `GameMonitor`, #10 Swiftplay, #12 Pengu CLI. Validado nos
três níveis: unitário, processos reais e **in-game (Teste C passou em 2026-09-19)**.

**Otimização #48** — `download_and_merge_hashes` mantinha quatro cópias da tabela de
230 MB vivas ao mesmo tempo. Agora faz streaming direto para o arquivo, via
`atomic_write` (`durable=False`, ADR-006). Ganho extra: parte que falha no meio do
download não deixa mais tabela truncada.

### Decisão do usuário ainda pendente
`start()` pode retornar **sem ativar o monitor** se a thread anterior não morrer em
3 s. Os chamadores (`manager.py:180, 316`) não checam retorno, então nesse caso o jogo
não é suspenso e a injeção pode falhar — com WARNING no log. Preferível a duas threads
disputando o mesmo processo, mas é trade-off consciente.

## Otimização — o que falta

| # | Item | Estado |
|---|---|---|
| ~~48~~ | Pico de ~940 MB no download da tabela de hashes | **feito** — 692 MB → 2,1 MB |
| ~~45~~ | Índice de hashes dos WADs | **feito como módulo isolado, sem call site** — 802.652 entradas em 6,4 MB, consulta 3,6 µs vs 0,39 s da varredura linear (104×) |
| 13 | `mkoverlay` no cache frio (97,63 s vs 4,20 s) | **viabilidade não medível agora** — exige cache frio (reboot) |
| 44 | Classificador de compatibilidade de mods | **desbloqueado** pelo #45 |
| 26 | Sync de skins incremental (GitHub compare em vez do ZIP inteiro) | não iniciado |
| 27 | `TIMER_HZ` 1000 → 20–60 Hz | **não é gargalo** — medido 1,6% de um core, e o loop entrega ~650 Hz, não 1000 |

Detalhe do #45 e o critério para camada nativa: ver as notas no fim do `backlog.md`.

## Validação final de 2026-09-19 (dev em `17405bc8`, 19 commits à frente)

| Verificação | Resultado |
|---|---|
| Working tree | limpo |
| `main` == `origin/main` | sim, `45b24701` |
| `.pyc` rastreados | 0 |
| Nome de usuário em `.py` no repo | 0 arquivos |
| Compilação geral | OK |
| Suíte unitária | **137 OK** (eram 116), 3 skipped |
| Suíte pesada | **14 testes, 12 OK**, 2 skipped |
| Call sites do `wad_index` | **nenhum** — comportamento em runtime inalterado |

## Pendente

- **#49** sincronizar a biblioteca de skins — sem ela, 5 testes continuam pulando e o
  Rift Clássico segue sem cobertura. **Precisa de você**, é download.
- **Ligar o índice ao app** — o módulo está pronto mas isolado. Ligar tem efeito
  colateral (thread em background, I/O no start), então é decisão sua.
- **#44** classificador de compatibilidade, agora desbloqueado.
- **Conflito `dev` → `main`** com o ferramental, descrito acima. Decisão sua.


---

# Fechamento do dia (2026-09-19)

`dev` com **44 commits** à frente. `main` intacta em `45b24701`. Working tree limpo.
**187 testes unitários** (eram 107) e 14 pesados, todos passando.

## Entregue e validado in-game

| Correção | Antes | Depois |
|---|---|---|
| Hardening etapa 3 (#9, #10, #12) | 7 falhas / 14 na pesada | 0 |
| Pico de RAM no download de hashes (#48) | 692 MB alocados | 2,1 MB |
| Índice de WADs (#45) | não existia | 802.652 entradas, 6,4 MB, 3,6 µs |
| Classificador de compatibilidade (#44) | não existia | pronto, **sem call site** |
| 3 defeitos da revisão de risco | — | corrigidos, 8 de 11 testes falham no código anterior |

Teste in-game: **5 injeções, 5 sucessos, 1 recusa correta** (skin padrão), 1 saída abrupta
tratada sem resíduo. Zero `INJECTION FAILED`, zero `Traceback`, zero crash de mod, zero
`ERROR` fora da corrida benigna de startup. Skin confirmada visualmente nas 5.
Detalhes em `tasks/completed/2026-09-19-validacao-in-game-indice-wad.md`.

## Decisões pendentes do usuário

1. **`dev` → `main`**: o ferramental (`.claude/`, `test/`, `testes_Pesados/`) está commitado na
   `dev` e iria junto, quebrando o layout upstream. Recomendação: branch `tooling` separada.
2. **`monitor_auto_resume_timeout`** 60 s → 120 s. A 1ª injeção do dia passou com 15,7 s de folga.
3. **Ligar o scanner de compatibilidade** à injeção (muda comportamento: recusa antes de suspender).
4. **`start()` sem ativar o monitor** após 3 s — trade-off da etapa 3, nunca decidido.

## Não verificado

- **Reuso do índice**: o Rose não foi reiniciado no teste. Esperado `Game index ready in 0.0Xs`
  **sem** a linha `Indexed`. É o único item da validação que ficou aberto.
- **#28/#29**: troca na bancada da ARAM, sem cobertura de teste nem in-game.
- **#49**: biblioteca de skins vazia mantém 5 testes pulando.

---

# Investigação #68 — Rift Clássico `Final name 'None'` (2026-09-19, tarde)

- Branch `diag/jade-skin-selection` (a partir da `dev`), **não commitada**: só logs em 4 arquivos
  (`websocket_event_handler`, `skin_processor`, `champion_lock_handler`, `loadout_ticker`).
- Validação: 196 unitários OK (9 novos, 6 falham no código anterior), 14 pesados OK, logs
  confirmados dentro do PYZ do `dist\Rose\Rose.exe`.
- Pendente: log do testador + teste in-game com outro jogador. Detalhes em
  `tasks/active/2026-09-19-classico-final-name-none.md`.
- **Teste in-game 14:33–14:45 com outro jogador: bug não reproduziu** (3 rodadas: escolha cedo,
  nos últimos 5 s, sem mexer; `Final name` sempre preenchido, skins confirmadas no jogo).
  O "volta para default" no fim é visual (reposicionamento do carrossel no GAME_STARTING, após o
  limiar). Próximo: log do testador com o build de diagnóstico. Novo item #71 (overlay em skin possuída no Clássico).
- **ADR-008 aplicada no projeto inteiro** (branch `diag/jade-skin-selection`): 237 `except` sem log →
  0 sem justificativa (~90 com log, ~147 `silent-ok`). Guarda `test/test_no_silent_exceptions.py`
  (acusa 249 no código anterior). 199 unitários + 14 pesados OK, 59 módulos importam.
  Merge na `dev` autorizado pelo usuário. Pendentes: #70 (log só crítico no AppData), #72 (JS).

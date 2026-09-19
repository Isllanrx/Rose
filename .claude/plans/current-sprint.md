---
updated: 2026-09-19
sprint: 2026-09-19 — Hardening etapa 3 validado + otimização de memória
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
dev   c9ac7383   (11 commits à frente)
main  45b24701   intacta, igual a origin/main
```

Branches `fix/prod-hardening` e `perf/hashes-memory` apagadas após o merge.
Backup do working tree original: `%TEMP%\rose-backup\working-tree-20260919-090408.patch`.

## Validação sistemática de 2026-09-19 — passou

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
| ~~48~~ | Pico de ~940 MB no download da tabela de hashes | **feito** |
| 45 | Índice de hashes dos WADs, 1× por patch em background | **próximo** — medido: 392 WADs / 31,5 GB → 898.520 entradas, 5,00 s, 7 MB em disco |
| 13 | `mkoverlay` no cache frio (97,63 s vs 4,20 s) | bloqueado pelo #45 |
| 44 | Classificador de compatibilidade de mods | bloqueado pelo #45 |
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

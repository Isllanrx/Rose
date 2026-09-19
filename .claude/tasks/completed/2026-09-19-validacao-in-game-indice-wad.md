---
created: 2026-09-19
status: concluida
updated: 2026-09-19
---

# Validação in-game — build com índice de WADs e hardening etapa 3

Build `dist\Rose\Rose.exe` de 2026-09-19, `dev` em `3b5180f2`+. Log de referência:
`%LOCALAPPDATA%\Rose\logs\rose_19-09-2026_10-14-04.log`. Acompanhado ao vivo por
monitor filtrando `[WADIDX]`, `[COMPAT]`, `[CLASSIC]`, injeção e assinaturas de crash.

## Resultado: passou

| Verificação | Resultado |
|---|---|
| Injeções bem-sucedidas | **4** (2 chroma no Rift normal, 1 Rift Clássico, 1 ARAM) |
| `INJECTION FAILED` | 0 |
| `ERROR` fora da corrida benigna de startup | 0 |
| `Traceback` / `Missing data` / `Uncaught exception in thread` | 0 |
| Skin visível em jogo | **confirmado pelo usuário** no Clássico (Annie skin 9) e na ARAM (chroma 5058) |

## Índice de WADs (#45) em produção

```
10:15:40 DEBUG [WADIDX] No index at ...\state\wad_index.bin yet
10:15:41 INFO  [WADIDX] Indexed 802652 entries from 392 WADs (0 skipped), 6.4 MB,
                        patch version:16.18.8175716+branch.releases-16-18.content.release
10:15:41 INFO  [WADIDX] Game index ready in 0.94s
```

Bate exatamente com o medido no banco de testes. **Uma única construção por sessão** —
confirma a correção do lock/flag (sem ela, os 3 call sites de `initialize_when_ready`
reconstruiriam a cada chamada). Gravado em `state\`, nunca na pasta do jogo.

**Pendente:** reiniciar o Rose para provar o reuso do arquivo (esperado
`Game index ready in 0.0Xs` **sem** a linha `Indexed`). Não executado.

## `mkoverlay` — A/B de cache na mesma sessão

Mesmo mod (`CHROMA_238070`), mesma máquina, minutos de intervalo:

| | Rodada 1 (frio) | Rodada 2 (quente) | Clássico | ARAM |
|---|---|---|---|---|
| `mkoverlay` | **44,33 s** | **2,36 s** | **1,84 s** | **2,63 s** |
| Jogo congelado | 41 s | ~1 s | ~1 s | ~1 s |
| Margem até auto-resume (60 s) | 15,7 s | 57,6 s | — | — |

Depois do primeiro aquecimento, as três injeções seguintes ficaram entre 1,84 s e 2,63 s,
incluindo mapas diferentes (Rift, Jade/mapId 453, Howling Abyss/mapId 12).

Conclusões no `backlog.md` (seção "#13 — A/B decisivo"): o cache é a variável dominante
(18,8×), **mas ler só as TOCs não aquece** — o índice leu as 392 TOCs 67 s antes da
rodada 1 e ela ainda levou 44,33 s. O #13 é problema de **primeira injeção após o boot**.

## Rift Clássico — cobre a mudança no `WadReader`

```
10:24:16 PREPARING INJECTION >>> SKIN_60001009 <<<
10:24:17 [CLASSIC] Indexed 98 Rift Classic characters from game hash table
10:24:17 [CLASSIC] Prepared Annie skin 9 for ['jade_annie', 'jade_annie_tibbers'], slots [0, 301, 302]
10:24:18 gameMode=JADE, mapId=453, queueId=3262
```

Esta é a **única cobertura real** da refatoração do `WadReader` (`read()` delegando para
`read_hash()`, mais `entry_hashes`/`entry_info`/`is_readable_type`): os 3 testes unitários
do Clássico pulam por falta da biblioteca de skins (#49). Zero `ClassicSkinError`,
`not a PROP file`, `corrupted WAD entry` ou `unsupported WAD entry type`.

Tibbers não testado — exige nível 6 em partida.

## Saída de partida — hardening etapa 3

Os dois ciclos fecharam limpos: `Game ended, stopping overlay process`, diretório de
overlay apagado, `Injection completed - lock released`, histórico gravado. Nenhum
processo suspenso sobrando entre partidas, nenhuma thread órfã.

## ARAM — `queueId=3220`, `mapId=12`

```
10:26:58 ChampSelect — gameMode=ARAM, mapId=12, queueId=3220
10:27:45 [INJECT] Final name variable: 'chroma_5058'
10:27:45 PREPARING INJECTION >>> CHROMA_5058 <<<
10:27:48 mkoverlay completed in 2.63s
```

Fase reconhecida normalmente. Troca na bancada não foi testada, então **#28 e #29
continuam sem cobertura**.

## Achados de log registrados

- **#64** `WinError 10061` do WebSocket logado como ERROR numa corrida de startup que se
  resolve sozinha (reconectou 15 s depois).
- **#63** tela de instalação piscando — observação do usuário, precisa de repro visual.
- **#65** `lifecycle_manager` lê e zera `self.chroma_ui` sem o lock, **8 vezes em 15 min**.
  Causa raiz: `self.lock.acquire(timeout=0.001)` — 1 ms, o que torna o caminho sem
  exclusão mútua a regra e não a exceção. Só apareceu na ARAM porque as transições de
  fase são mais rápidas ali; é pré-existente, exposto pelo teste.
- `Killed all runoverlay processes for Lobby` (INFO) seguido de `No runoverlay processes
  found to kill` (DEBUG): a mensagem afirma sucesso sem ter feito nada. Mesma família do
  #13b. Não registrado como item próprio por ser trivial.

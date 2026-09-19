---
name: systematic-debugging
description: Investigação de causa raiz a partir de logs do Rose (rose_*.log, log_updater_*.log). Use quando o usuário enviar logs, relatar injeção falhando, skin errada/ausente em jogo, erro de conexão LCU/Pengu ou pedir "causa raiz".
---

# Systematic Debugging — Rose

Nunca propor correção antes de a causa raiz estar provada por log + código.

## Fase 1 — Coleta de evidências
1. Logs ficam em `%LOCALAPPDATA%\Rose\logs\`. Correlacione por horário: `log_updater_*` precede `rose_*` em ~10s.
2. Filtrar ruído antes de ler (PowerShell `Where-Object -notmatch`):
   `lockfile is not ready|Analytics ping|Broadcasting phase`
3. Extrair a linha do tempo da sessão com erro:
   `Phase transition|INJECT|RANDOM|HISTORIC|CHROMA\] Chroma selected|Skin detected|mkoverlay|runoverlay|Game suspended|Game resumed|Quit requested|ERROR`

4. Jogo crashou / `InProgress → Reconnect` logo após `runoverlay started`: ler o log do jogo, não só o do Rose.
   - `<League>\Logs\GameLogs\<timestamp>\*_r3dlog.txt` (procurar `ERROR`, `SentryHandleException`, `Build Version`)
   - `<League>\Logs\GameCrashes\last_crash` (horário UTC do crash)
   - Comparar com outras partidas do mesmo patch: se só a skin X crasha, a causa é o `.fantome` dessa skin, não o Rose.
5. Rose não ativa o Pengu com `WinError 4551`: Smart App Control bloqueou binário sem assinatura (CodeIntegrity eventos 3033/3077).
6. Plugin JS não reage numa tela do cliente (ex.: Rift Clássico): não chutar seletores. Criar plugin de diagnóstico só leitura em `%LOCALAPPDATA%\Rose\Pengu Loader\plugins\<Nome>\index.js` que envia `{type: "chroma-log", source, message, data}` pelo `window.__roseBridge`; o resumo do DOM aparece no `rose_*.log`. Remover após o diagnóstico.
7. `Final name variable: 'None'`: procurar na mesma sessão as linhas de diagnóstico (desde a branch `diag/jade-skin-selection`):
   `Skin '.*' ignored|Discarding skin title|No skin to inject at threshold|Failed to handle LCU event|Session view`.
   Título antes do lock = corrida (o JS não reenvia título igual); `Failed to handle LCU event` = exceção que antes era engolida.
8. Dúvida sobre o comportamento de uma tela do cliente: ler o código real em `<League>\Plugins\<rcp-fe-*>\assets.wad` com `WadReader` (`entry_hashes()` + `read_hash()`, filtrar por conteúdo) antes de propor CSS/DOM. Ex.: no Clássico a navegação depende de `session.allowSkinSelection` e `skin-selector-info` reposiciona o carrossel.
9. Reproduzir ao vivo sem mexer no Rose: `.claude/tasks/active/classico-diag-tools/` tem `lcu_monitor.py` (só assina eventos do LCU, horário em ms) e `diagjade_plugin.js` (título/cliques do carrossel do Clássico no `rose_*.log`). Instalar o plugin **depois** que o Rose abre. O WebSocket do LCU não entrega `skin-selector-info`; o reposicionamento do carrossel só aparece pelo DOM. Carrossel voltando à skin padrão no GAME_STARTING é visual e ocorre após o limiar.
10. Validar dados do jogo com a API local: LCU (`lockfile` → `/lol-game-data/assets/v1/...`, `/lol-champions/v1/inventories/...`) e Live Client Data (`https://127.0.0.1:2999/liveclientdata/allgamedata`) — sempre só leitura.

## Fase 2 — Classificar cada ERROR
Para cada ERROR responda: é causa ou consequência? O que aconteceu imediatamente antes (±5 linhas)?

Falsos positivos conhecidos:
| Sintoma | Significado real |
|---|---|
| `runoverlay failed with return code: 15` logo após `Quit requested` / `Killing mod-tools.exe` | `psutil.terminate()` no Windows sai com código 15 (SIGTERM). Foi o cleanup, não o overlay. |
| `Pengu command failed ... League Client UX is not running` no CLEANUP | Cliente fechado/em jogo; restart impossível, esperado. |
| `WinError 10061` logo após `Requested the League Client UX to restart` | Porta LCU fechada durante restart do cliente. |
| `LCU lockfile is not ready` por horas | Cliente do League não aberto. |
| Print/relato de um usuário sem sessão correspondente no log local | O cliente local estava ocioso (`GameflowMonitor: marking None/afk` no `LeagueClient.log`); o caso é da máquina do usuário. Pedir o log dele. |
| Logs sumiram | O Rose apaga logs com mais de 24h no start; a desinstalação apaga `%LOCALAPPDATA%\Rose`. |

## Fase 3 — Rastrear no código
- Localize a mensagem exata com Grep (`glob: *.py`) e leia só o trecho relevante.
- Mapa de fluxo da injeção:
  - Escolha do nome: `threads/utilities/skin_name_resolver.py` (prioridade: historic > random > last_hovered_skin_id)
  - Disparo: `threads/handlers/injection_trigger.py`
  - Execução: `injection/core/injector.py` → `injection/overlay/overlay_manager.py`
  - Processos: `injection/overlay/process_manager.py`; shutdown: `main/core/cleanup.py`
  - Estado de modos: `state/core/shared_state.py` (`random_mode_active`, `historic_mode_active`)
  - Seleção de chroma: `ui/chroma/selection_handler.py`, `pengu/communication/message_handler.py`
- Verifique toda escrita/limpeza do estado envolvido: `grep -rn "random_mode_active\s*=" --include=*.py`.
- Use `git log -S "<símbolo>"` para distinguir regressão de lacuna de design.

## Fase 4 — Hipótese e prova
- Formule uma única hipótese que explique TODAS as linhas da linha do tempo.
- Confirme contra uma sessão de controle que funcionou (ex.: outra injeção no mesmo dia).
- Se a hipótese não explica alguma linha, volte à Fase 1.

## Fase 5 — Relatório
- Causa raiz (arquivo:linha) + evidência de log com horário.
- Separar: causa raiz / consequências / ruído.
- Correção proposta mínima + teste que reproduz. Só implementar se o usuário pedir.

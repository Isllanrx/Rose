---
updated: 2026-09-19
branch: diag/jade-skin-selection
status: teste in-game local sem reprodução; aguardando log do testador
---

# Rift Clássico: `Final name variable: 'None'` em sala com outros jogadores (#68)

## Relato
Testador externo (PR #262, build de `45b24701` = `main`): em custom solo a injeção funcionou;
em sala com outros jogadores as skins não possuídas pareciam bloqueadas, o log mostrava
`[INJECT] Final name variable: 'None'` e o jogo carregava a skin base (`gameMode=JADE`,
`mapId=453`, `queueId=3262`). Outro usuário diz que funcionou no Clássico online com outros.
Os logs do testador **não estão disponíveis**; o print do Lux (`image.png`) é dele, não desta máquina.

## Provado
- `main` e `dev` têm o caminho da seleção **idêntico** (plugins, `pengu/`, lock, ticker, resolver).
- Sessão de controle local (`rose_19-09-2026_10-14-04.log`, 10:23, custom solo, Annie): lock às
  10:23:46 antes do primeiro título; 11 skins não possuídas lidas pelo título; injeção `skin_60001009` OK.
- Código do cliente 16.18 (`Plugins/rcp-fe-lol-jade`, `rcp-fe-lol-champ-select`):
  - `skins-pane.selectSkin` só roda se `session.allowSkinSelection` (LCU) for verdadeiro; a posse
    (`unlocked`) só bloqueia `requestSetSkin`, não a troca de título.
  - Não há `pointer-events: none` em card bloqueado. **A tese do relatório do Agy (CSS/pointer-events) está refutada.**
  - `handleSkinSelectorInfo` reposiciona o carrossel na skin do LCU a cada `/v1/skin-selector-info`
    (o ROSE-UI só filtra o socket do `rcp-fe-lol-champ-select`).
  - A aba de skins abre quando o **próprio pick** conclui (`showFinalization`), ou seja, durante os
    picks dos outros quando há outros jogadores.
- Lacunas no Rose:
  - título que chega antes do lock é descartado (`skin_processor._find_skin_id`), o lock apaga o
    cache (`on_own_champion_locked` → `clear_cache`) e o JS só reenvia se o título mudar;
  - o resync pensado para isso (`champ_thread.py:95`) é código morto: `ChampThread` nunca é instanciado;
  - `websocket_event_handler.handle_message` engolia qualquer exceção do processamento de sessão.

## Hipótese (não provada)
Título inicial perdido na corrida com o lock + carrossel sem gerar título novo depois
(`allowSkinSelection=false` ou reposicionamento por `skin-selector-info`).

## Diagnóstico adicionado (branch `diag/jade-skin-selection`, só logs)
| Linha nova no log | Significa |
|---|---|
| `[WS] Failed to handle LCU event <uri>` + traceback | exceção no lock/timer que antes sumia |
| `[SkinMonitor] Skin 'X' ignored: no locked champion yet (hovered=N)` | título chegou antes do lock |
| `[SkinMonitor] Skin 'X' ignored: could not load skins / loading skins failed / name matching failed` | scrape ou match falhou |
| `[lock:champ] Discarding skin title 'X' received before the lock` | prova da corrida |
| `[lock:champ] Session view: local_cell=…, locks=…` (DEBUG, só na mudança) | o que o Rose viu de lock |
| `[INJECT] No skin to inject at threshold: locked_champ_id=…, ui_last_text=…` | foto do estado quando sai `None` |

Testes: `test/test_jade_selection_diagnostics.py` (9 testes; 6 falham no código anterior).
Suítes: 196 unitários OK, 14 pesados OK.

## Teste in-game (2026-09-19, 14:33–14:45) — bug NÃO reproduziu
Build de diagnóstico (`dist\Rose`), personalizada do Rift Clássico (fila 3262) com **outro jogador
humano**, monitor LCU só leitura + plugin `DiagJade`. Log: `rose_19-09-2026_14-28-44.log`.

| Rodada | Campeão | Escolha | Final name | No jogo |
|---|---|---|---|---|
| 1 | Katarina (60055) | cedo, durante BAN_PICK e FINALIZATION | `skin_60055009` (PROJETO) | skin OK |
| 2 | Malzahar (60090) | só nos últimos ~4 s do FINALIZATION | `skin_60090006` (Chefão, + voidlings) | skin OK |
| 3 | Ezreal (60081) | sem mexer | `skin_60081301` (possuída, forçada no LCU) | sem skin, correto |

- `allowSkinSelection` = `true` em todos os eventos; todo clique mudou o título.
- Lock sempre **antes** do primeiro título (mesmo segundo).
- Zero `Failed to handle LCU event`, `ignored:`, `Discarding skin title`, `No skin to inject`, `Traceback`.
- **Reposicionamento do carrossel observado**: sem clique, o título voltou para a skin do LCU na
  entrada do FINALIZATION (14:34:23) e no GAME_STARTING (14:34:53, 14:40:17). O segundo é o
  "voltou para default" que o usuário viu: **só visual**, ocorre depois do limiar do ticker.
  Hipótese: é isso que o testador descreveu como "skin bloqueada".
- Limitação do monitor: a assinatura `OnJsonApiEvent_lol-champ-select_v1_skin-selector-info` e
  `..._skin-carousel-skins` não recebeu **nenhum** evento; o reposicionamento só foi visto pelo DOM.

Conclusão: nesta máquina, com outro jogador, o fluxo funciona nos 3 cenários. O `None` do
testador depende de condição ausente aqui (ordem de eventos na máquina dele, exceção antes engolida
pelo `except: pass` do WebSocket, ou forma de selecionar). As linhas novas de log identificam qual.

Achado paralelo (#71): skin **possuída** no Clássico ainda monta overlay (`injection_trigger.py:731-738`,
feito para party skins, que não existem no Clássico): ~2 s de jogo suspenso sem efeito.

Ferramentas reutilizáveis: `classico-diag-tools/` (monitor LCU, plugin DiagJade, eventos gravados).

## Próximos passos
1. Enviar o build/branch de diagnóstico ao testador e pedir o `rose_*.log` de uma tentativa que falhe.
2. Com a causa provada: correção em `fix/*` com teste que reproduz.
3. Decidir o destino da branch: o log do `except: pass` do WebSocket é defeito real e deve ficar;
   os demais são diagnóstico e podem ficar (são raros, INFO/WARNING).

## Desdobramento: ADR-008 (2026-09-19)
Pedido do usuário: nenhum erro silencioso no projeto. Aplicado na mesma branch e mergeado na `dev`.
Ver `decisions/adr-008-todo-except-loga-ou-justifica.md`.

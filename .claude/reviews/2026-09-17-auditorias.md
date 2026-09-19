---
updated: 2026-09-17
---

# Auditorias — 2026-09-16/17

Registro consolidado das auditorias feitas no projeto, com status de cada achado.
Legenda: **aplicado** (commitado no `main`), **parcial**, **pendente** (ver `plans/backlog.md`), **descartado**.

## 1. Code review dos 13 commits `origin/main..main` (skill `code-review`, high)
| Achado | Status |
|---|---|
| `_route_logger` forçava DEBUG e descartava TRACE no launcher em modo debug (`launcher/core/launcher.py:45`) | aplicado (`1980a6a1`) |
| Builder do Clássico, `stop_requested`, opt-out de analytics, random mode, `clear_issue` | verificados, sem defeito |

Veredito: aptos para PR após a correção acima.

## 2. Aderência ao padrão Python 2026 (Ruff py313 + basedpyright, 176 arquivos, ~35 mil linhas)
Resultado: **não segue** o padrão; segue parcialmente em nomes, constantes centralizadas e logger próprio.

| Tema | Medição (2026-09-16) | Status |
|---|---|---|
| `except:` puro | 0 | ok |
| `except Exception` (BLE001) | 535 | pendente (não estreitar sem cobertura — ADR-005) |
| `try/except/pass` (S110) | 72 | parcial: histórico e cleanup corrigidos nas etapas 1–2 |
| `log.error` em `except` sem traceback (TRY400) | 195 | pendente |
| Logs com f-string (G004) / sem logging estruturado | 1222 | pendente (baixo valor) |
| `print` em produção | 19 fora de `scripts/` (`window_utils.py` 13, `main/__init__.py` 4, `signals.py` 2) | pendente |
| Type hints ausentes (ANN001/ANN201) | 302 / 291 | pendente |
| basedpyright strict / standard | 10.827 / ~260 reais | pendente |
| Nomes indefinidos (F821) | 3 em `resolution_utils` | aplicado (`7c77381c`) |
| Funções complexas (C901) / arquivos gigantes | 104; `message_handler.py` 2870 linhas, `injection_trigger.py` 1598 | pendente |
| Python 3.13+ | 3.12 (PyInstaller 6.3.0) | pendente (exige atualizar PyInstaller e revalidar build assinado) |
| `pyproject.toml`, Ruff/Pyright configurados, pre-commit, uv | ausentes | pendente |
| pytest + fixtures + cobertura | `unittest`, sem cobertura medida; `test/` ignorado pelo git | pendente |
| CI (lint, type check, testes, build) | inexistente | pendente |
| Pydantic para dados externos (mensagens JS, LCU, GitHub) | não usado | pendente |
| Enums para domínios fechados | 0 `Enum` (fases, modos e mensagens são strings) | pendente |
| Estado global mutável | `SharedState` + 14 `global` | pendente (roadmap) |

Ordem recomendada e aceita: CI + testes (base) → testes de caracterização → segurança → tratamento de erros (só adicionar log) → tipagem incremental pelas fronteiras.

## 3. Review de falhas de produção (skill `prod-risk-review`)
| # | Achado | Status |
|---|---|---|
| 1 | Shutdown não retomava jogo suspenso (`main/core/cleanup.py`) | aplicado (ADR-007) |
| 2 | Corrida suspend/resume no `GameMonitor` (`game_monitor.py` ~135/201) | pendente (backlog #9) |
| 3 | Overlay do Swiftplay bloqueia a PhaseThread | pendente (#11) |
| 4 | `GameMonitor.start()` sem `join` → suspensão dupla | pendente (#9) |
| 5 | `_inject_custom_mod` não para o monitor nos `return` | pendente (#10) |
| 6 | Swiftplay sem `finally: _stop_monitor()` | pendente (#10) |
| 7 | Extração de skins truncava arquivo e gravava SHA | aplicado (ADR-006) |
| 8 | `config.ini` ilegível era sobrescrito | aplicado (ADR-006) |
| 9 | Histórico não atômico e sem lock entre threads | aplicado (ADR-006) |
| 10 | Pengu CLI sem timeout travando o shutdown | parcial: etapas do cleanup isoladas; timeout pendente (#12) |
| 11 | SHA buscado depois do download | aplicado (ADR-006) |
| 12 | `OSError` no sync incremental abortava sem fallback | aplicado (ADR-006) |
| 13 | Recusa por campeão incompatível sem marcar `last_hover_written` → ~300 WARNING a 1000 Hz (`injection_trigger.py:156/175`) | pendente (#25) |
| 14 | Path traversal na extração do ZIP de skins; `is_safe_path` por prefixo | aplicado (`78f5d805`, `45b24701`) |
| 15 | Diálogo nativo da DLL comparava IDYES/IDNO com MB_OKCANCEL | aplicado (`2736a5e6`) |
| 16 | Funções com nomes indefinidos em `resolution_utils` | aplicado (`7c77381c`) |
| 17 | `phase_thread.run()` sem proteção: thread morre sem log | parcial: morte agora é logada (hook); thread ainda morre (#11) |
| 18 | `champ_thread` com `except Exception: pass` na lógica de lock | pendente (#11) |
| 19 | `loadout_ticker` sem try | parcial: morte logada; proteção em volta do loop pendente (#11) |

## 4. Desempenho e reescrita em Rust
Conclusão: **Rust não traz ganho real**.
| Ponto | Medição / análise | Status |
|---|---|---|
| Builder do Clássico | ~12 ms por skin; zstd/xxhash já nativos; índice em cache | descartado (sem gargalo) |
| Injeção | tempo dominado pelo `mod-tools.exe` (já nativo); skins pesadas levam 40–50 s | pendente investigação (#13) |
| Sync de skins | gargalo é rede (ZIP inteiro), não CPU | pendente: baixar só arquivos alterados via GitHub compare (#26) |
| Ticker do champ select | `TIMER_HZ_DEFAULT = 1000` acorda a cada 1 ms disputando o GIL; 20–60 Hz bastam | pendente (#27, muda timing — validar in-game) |
| Escrita atômica | `fsync` por arquivo custaria ~110 s no sync completo; resolvido com `durable=False`; extração final ~5–10% mais lenta | aplicado (ADR-006) |

## 5. Confiança no Windows (skill `windows-trust-review`)
Detalhes em `context/security.md` e backlog #3–#8. Nenhum item aplicado ainda (adiado pelo usuário).
Resumo: execução elevada de binários/scripts em pastas graváveis (Pengu em AppData, staging e `.bat` do update, `[UninstallRun]`), update sem verificação de assinatura, `cmd`/`schtasks` por caminho parcial, `Rose.exe` sem VERSIONINFO, `unins000.exe` sem assinatura, AppId de exemplo, atributos oculto+sistema, escrita em HKLM a cada start. Risco residual inerente: injeção de DLL, suspensão do jogo, IFEO do Pengu.

## 6. Comparação com o PR upstream #184 (`ccccxp`, "Add isolated Classic Mode support")
| Critério | Implementação Rose (ADR-004) | PR #184 |
|---|---|---|
| Fonte das skins | gerada do WAD do jogo instalado | pacotes refeitos à mão no `LeagueSkins#94` (3.180 arquivos, aberto) |
| Manutenção por patch | automática | pacotes podem quebrar (risco tipo 21069) |
| UI no Clássico | mínima (cadeado, "Habilitada") | completa (carrossel, chroma, histórico, random, splash) |
| Isolamento por modo | implícito (IDs deslocados) | explícito (`scope`, preferências de random, gerações de seleção) |
| Tamanho / testes | pequeno, com testes locais | +8.277 linhas, 75 commits, sem testes, 3.670 linhas desativadas (`.js_`) |
| Observação | fila observada 3262 | fallback `CLASSIC_QUEUE_ID = 3260` |

Decisão: manter a implementação própria como base; adotar do #184 em PRs separados → backlog #28–#31. Não adotar os pacotes refeitos (exceto como complemento opcional para skins fora da árvore Jade).

## 7. Incidente de build (2026-09-17 02:03)
- Build rodado com `Rose.exe` do `dist` aberto: `PermissionError [WinError 5]` em `_internal\charset_normalizer\cd.cp312-win_amd64.pyd`, PyInstaller abortou (script saiu com 1), `dist` ficou meio apagado (1.057 arquivos).
- O resultado foi entregue sem ler o log. Sintomas no usuário: launcher com "Update/Hash/Skin download failed" (`certifi\cacert.pem` ausente) e ícone da bandeja genérico/oculto (`assets\tray_*.png` ausentes); skins carregaram porque já estavam baixadas.
- Correção: rebuild às 02:15 com processos fechados; verificados log, arquivos essenciais, binários byte a byte e símbolos das correções dentro do `Rose.exe`.
- Prevenção: regra em `context/coding-standards.md`; script abortar quando não conseguir limpar o `dist` → backlog #32.

## 8. Triagem de issues e PRs abertos no upstream (`Alban1911/Rose`, 2026-09-17)
14 issues e 11 PRs abertos. Critério: impacto no usuário, chance de aceite pelo mantenedor, sobreposição com o que já foi feito aqui.

### Vale esforço
| Prioridade | Item upstream | Motivo | Relação local | Esforço | Backlog |
|---|---|---|---|---|---|
| 1 | Issue #261 (autor: Isllanrx) — código 15 / "timeout" na injeção | Duas causas: skin 21069 crasha no patch 16.18 (conteúdo) e código 15 do cleanup reportado como falha (corrigido no PR, ADR-002) | Atualizar a issue com causa raiz e link do PR; fechar após merge | Baixo | #37 |
| 2 | Issue #250 (não detecta champ select após 1 partida) + #3 (party: skins falham da 2ª partida em diante) | Sintomas batem com a etapa 3: PhaseThread morrendo/bloqueada pelo overlay do Swiftplay, monitor não parado | Pedir log com build novo (hook de exceção de thread mostra a causa) antes de corrigir | Médio | #9–#11, #38 |
| 3 | Issue #255 (mantenedor) — botão para encerrar a injeção na janela de reconexão | Pedido do mantenedor (alta chance de aceite); quebra o loop crash → reconnect → crash (#252, #261) | Combinar com detecção de crash pós-injeção; `stop_overlay_process` já existe | Médio | #21, #39 |
| 4 | Issue #208 (mantenedor) — `core.dll` e `config.ini` do Pengu em perfis de usuário diferentes | Pengu não carrega; mesma raiz do item de confiança no Windows (Pengu em `%LOCALAPPDATA%`, `get_user_data_dir`) | Resolver junto com o backlog #7 | Alto (repro com 2 contas) | #7 |
| 5 | Issue #73 — chroma comprado (Mythic Shop) sem possuir a skin volta para a base | Mantenedor disse que ia olhar; lógica de seleção/posse já conhecida (ADR-001, `injection_trigger.py`) | Precisa de conta com esse caso para validar | Médio | #40 |
| 6 | Issue #7 — "argument injection" no `mod-tools.exe` | Risco real baixo: argumentos em lista sem shell, `/` impossível em nome de arquivo; só `overlay_manager.py:435` junta com `,` (permitido em nome) | Responder com a análise e sanitizar a `,` | Baixo | #41 |
| — | PR #244 (fila 490 Quickplay) | Bug real (código local só trata 480); não conflita com o PR local | Testar e comentar a favor; sem código nosso | Baixo | #42 |
| — | PR #211 (histórico + custom mods, #194) | Conflita em `injection_trigger.py` com o PR local | Se o PR local entrar antes, ajudar a atualizar; não reescrever | Baixo | #43 |
| — | PR #184 (Classic Mode) | Concorrente | Adotar só partes (backlog #28–#31) | — | #28–#31 |

### Não vale esforço de código local
| Item | Motivo |
|---|---|
| #252 MF T1 MVP crasha, #251 Kai'Sa sem assets, #260 ult do Hecarim invisível, #254 pedido de skin Tristana | Conteúdo dos `.fantome` no repositório LeagueSkins, não código do Rose (mesmo caso da 21069). #255/#21 mitigam o sintoma |
| #256 caminho longo em custom mod | Já corrigido por `59922fc` (no `main`), só não saiu em release (última 1.2.14); apenas comentar |
| #257 overlay não aparece | Suporte de instalação antiga (IFEO/`loaderpath`), solução já na própria issue |
| #229 e #3 (parte do relay) — party não conecta | Arquitetura de party disputada pelos PRs #249 (LAN/P2P) e #170 (automático); decisão do mantenedor |
| PRs #231, #196, #178, #175 | Features de UI de outros contribuidores, sem relação com o trabalho local |
| PRs #118 e #77 | Antigos e já em conflito com o upstream |
| PR #249 e #170 | Party mode de outros; #249 conflita com o PR local só em `Rose.spec` e `ROSE-UI/index.js` (este pelo commit de formatação) |

### Conflitos do PR local com PRs abertos (se entrarem antes)
#184 (8 arquivos), #231 (3), #249 (2), #211 (1); #244, #196, #178, #175, #170 sem conflito; #118 e #77 já conflitam com o upstream.

## 9. Avaliação da troca de `except: pass` por log (ADR-005 e etapas 1–2)
Conclusão: **seguro em produção**.
| Risco | Análise |
|---|---|
| Mudança de comportamento | Nenhuma: mesmo tipo de exceção e mesmo retorno; só acrescenta log. Exceções deliberadas e testadas: config ilegível não sobrescrito e SHA não gravado com falha (ADR-006) |
| Volume de log | 51 logs adicionados em `except`; nenhum em laço de alta frequência (gravação de histórico, abertura da roda de mods, launcher, shutdown). Pior caso: sync com disco cheio (~9 mil WARNING uma vez). Arquivo gira a cada 10 MB (`LOG_MAX_FILE_SIZE_MB_DEFAULT`) |
| Ruído para o usuário | 18 são DEBUG; modo `customer` grava INFO+ → invisíveis como antes. WARNING só quando o resultado muda para o usuário |
| Tracebacks | 4 com `exc_info=True` (Pengu no shutdown, tracker de skin base) e o hook de thread, todos raros |
| Dados sensíveis | Só caminhos de arquivo (já presentes no log) e erros de rede da API pública do GitHub; nenhum token/credencial |
| Log falhando no shutdown | `logging` não propaga erro de handler |

Por que existia `pass`: operações de "melhor esforço" (broadcast para plugin possivelmente desconectado, arquivos temporários, histórico), receio de poluir o log e evitar derrubar threads — mas "não derrubar" não exige "não registrar"; o `pass` escondia falhas que mudavam o resultado (histórico apagado, config sobrescrito, log do launcher descartado, Pengu não desativado).

Restante (pendente): 72 S110 e 535 BLE001 fora dos módulos críticos (#23) — manter `pass` só com comentário do porquê; 195 `log.error` sem traceback (#34); spam de ~300 WARNING da recusa por campeão incompatível (#25), anterior a estas mudanças. Estreitar tipos de exceção fica para quando houver cobertura de testes.

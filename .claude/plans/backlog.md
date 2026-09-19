# Backlog — Rose

Ordenado por prioridade. Checklists detalhados: skills `prod-risk-review` e `windows-trust-review`. Origem e status de cada achado: `reviews/2026-09-17-auditorias.md`.

| # | Item | Tipo | Contexto |
|---|---|---|---|
| ~~1~~ | Teste C in-game: fechar o Rose pela bandeja durante a partida (jogo não pode congelar) | validação | ADR-007  — **feito: Teste C passou in-game em 2026-09-19 (current-sprint)** |
| 1b | Retestar com o build de 02:15 (o de 02:03 estava quebrado): launcher sem "failed", ícone da rosa na bandeja, partida normal e Clássico | validação | Auditorias §7 |
| 2 | Abrir PR dos 21 commits `origin/main..main` | chore | Merge e push feitos em 2026-09-17 |
| 2b | Antes do PR: remover `.claudeignore` (ferramenta local, comentários em português) em commit novo, sem reescrever histórico; descrição do PR com evidências de validação e relação com o #184 | chore | Auditorias §8; conflitos com PRs abertos só se entrarem antes |
| 3 | Confiança Windows — caminho completo para `cmd`/`schtasks`; `[UninstallRun]` executar Pengu de `{app}` e não de `{localappdata}` | segurança | Execução elevada de caminho gravável |
| 4 | Confiança Windows — VERSIONINFO no `Rose.exe` (`version=` no spec), AppId único no Inno Setup (hoje GUID de exemplo), assinar `unins000.exe`/instalador | build | Falso positivo; metadados vazios no oficial |
| 5 | Confiança Windows — verificar assinatura Authenticode do update extraído antes do `robocopy` para Program Files | segurança | Update sem verificação de integridade |
| 6 | Confiança Windows — staging e `apply_update.bat` fora de `%LOCALAPPDATA%` (pasta só de admin); substituir batch (`ping`, `del "%~f0"`) por `updater.exe` assinado | segurança | EoP/TOCTOU; `updater.exe` não é distribuído |
| 7 | Confiança Windows — executar CLI do Pengu de `{app}\_internal\Pengu Loader`, manter só `plugins`/`datastore` em AppData | segurança | Rose elevado executa exe/DLL de pasta gravável; resolve junto a upstream #208 (perfis diferentes); testar ativação nos dois modos |
| 8 | Confiança Windows — remover atributo SYSTEM de mods/overlay; gravar `HKLM\...\Uninstall\DisplayVersion` só quando mudar; `hashes.game.txt` fora de Program Files | qualidade | Heurística comportamental / escrita em Program Files em runtime |
| ~~9~~ | ~~`GameMonitor`: `stop()` retomar mesmo inativo, `start()` sem `join`, corrida no processo suspenso~~ | **corrigido e validado** | Commitado na `dev`. `stop()` resume fora da guarda `_monitor_active`; `start()` faz `join` e recusa segunda thread; `RLock` no `_suspended_game_process`. Old vs new: 3 falhas → OK |
| ~~10~~ | ~~Hardening etapa 3 — `_stop_monitor` no Swiftplay (`try/finally`)~~ | **corrigido e validado** | Commitado na `dev`. Só o caminho de sucesso soltava o jogo (via `overlay_manager.py:334`); exceção e código não-zero deixavam suspenso. Old vs new: 2 falhas → OK. Nota: `inject_skin_immediately` já tinha `finally` (`manager.py:359`) — o item citava um `_inject_custom_mod` que não existe mais |
| 11 | Hardening etapa 3 — tirar overlay do Swiftplay da PhaseThread; try em volta (não dentro) do loop do `loadout_ticker`; `except: pass` do `champ_thread` | bug | PhaseThread bloqueada a partida inteira |
| ~~12~~ | ~~Timeout no Pengu CLI (`pengu_loader.py:396`) no caminho de cleanup~~ | **corrigido e validado** | Commitado na `dev`. `timeout=15s` + `except TimeoutExpired` (herda de `SubprocessError`, não de `OSError` — só o timeout deixaria a exceção abortar o cleanup). Old vs new: 2 falhas → OK |
| 13 | Depende do #45. `mkoverlay` no cache frio estoura o auto-resume: medido **97,63 s** (1ª execução) vs **4,20 s** (2ª), mesma entrada. Pré-aquecer o índice dos WADs no start ataca a causa; subir `monitor_auto_resume_timeout` (teto 180 s) só compra margem | bug | Mod não carrega e o usuário não vê erro — Auditorias 2026-09-18 §5 |
| 13b | `runoverlay should have hooked` é emitida sem verificar se o `mkoverlay` terminou — sucesso falso no log | log | ADR-005; mesma sessão do #13 |
| 14 | Rift Clássico: HistoricMode e dado (RandomSkin) reconhecerem a tela; limitar retries de `Rewards element not found` | feature/log | ~270 linhas por partida |
| 15 | Rift Clássico: seleção de chroma (ChromaWheel/FormsWheel reconhecer `.skins-pane`) | feature | Dados de 1196 chromas já validados (ADR-004) **Relatos de usuarios (2026-09-19)** pedindo chroma no Classico: sobe a prioridade. |
| 16 | Rift Clássico: aviso na UI quando a skin não puder ser exibida | UX | Hoje só aparece no log |
| 17 | Testes não criarem `log_updater_*.log` vazios em `%LOCALAPPDATA%` (import de `launcher` cria o arquivo) | qualidade | 71 arquivos vazios gerados por execuções de teste |
| 18 | Rebaixar `Pengu command failed ... League Client UX is not running` no cleanup para WARNING/DEBUG | log | Ruído ao fechar Rose em partida |
| 19 | Reduzir spam de `LCU lockfile is not ready` | log | ~2200 linhas em 9h com cliente fechado |
| ~~20~~ | `build_pengu_loader.py`: suportar `dotnet msbuild -restore` nativamente; opção de reutilizar binários assinados do Pengu | build | ADR-003  — **feito: `dotnet msbuild` com checagem de SDK + `/restore` separado; build validado em clone limpo** |
| 21 | Detectar crash pós-injeção (`InProgress → Reconnect` em < 60s) e reportar skin suspeita | feature | Caso 21069 |
| 22 | Remover hidden import inexistente `websocket_client` do `Rose.spec` | build | `ERROR: Hidden import 'websocket_client' not found` |
| ~~23~~ | Erros silenciosos restantes (S110 fora dos módulos críticos) + opt-out de analytics no painel | qualidade | ADR-005  — **feito: ADR-008 (237 → 0 except sem log ou justificativa, guarda em teste)** |
| 24 | Decidir versionamento de `test/` (hoje ignorado; só `test_pengu_loader.py` rastreado) | chore | Decisão do usuário: manter local por ora |
| 25 | Recusa por campeão incompatível (`injection_trigger.py:156/175`) não marca `last_hover_written`: ~300 WARNING a 1000 Hz | log/bug | Auditorias §3 #13; pode ser retry intencional — analisar timing |
| 26 | Sync de skins: baixar só arquivos alterados via GitHub compare em vez do ZIP inteiro quando acima do limite | desempenho | Auditorias §4 |
| 27 | `TIMER_HZ_DEFAULT` 1000 → 20–60 Hz | desempenho | **Nao e gargalo**: medido 1,6% de um core, e o loop entrega ~650 Hz, nao 1000. Motivo real e a resolucao de timer do Windows elevada para o sistema todo. Muda timing do gatilho; validar in-game |
| 28 | Do PR #184: histórico e random isolados por modo (`scope`) | feature | Auditorias §6 |
| 29 | Do PR #184: proteção contra seleção atrasada (gerações) na trava final | bug | Auditorias §6 |
| 30 | Do PR #184: UI do Clássico (chroma, histórico, random) sobre o builder próprio | feature | Complementa #14–#16 |
| 31 | Do PR #184: endpoints do LeagueSkins derivados de `repo_url` (`1204dcc8`) | refactor | Pequeno e independente |
| 32 | `scripts/build_pyinstaller.py`: abortar se não conseguir remover `dist/` (hoje só loga e segue) | build | Auditorias §7 |
| 33 | Padrão 2026 — base: `pyproject.toml` com Ruff/basedpyright em modo relatório, CI (Windows, Python 3.12) com testes + lint só nos arquivos alterados + smoke do build, pre-commit | qualidade | Auditorias §2  — CI agora detalhado no #74; resto (pyproject/Ruff) segue aqui |
| ~~34~~ | Padrão 2026 — `log.exception` nos módulos críticos (TRY400), `print` → logger em `window_utils.py`/`main/__init__.py`/`signals.py` | qualidade | Só adiciona log  — **absorvido pelo #73 (TRY400) e #72/ADR-008** |
| 35 | Padrão 2026 — tipagem incremental pelas fronteiras (`SharedState`, injector/manager, mensagens), Pydantic para mensagens do Pengu, Enums para fases/modos | qualidade | Após #33 **Meta do usuario (2026-09-19): tipagem 100% explicita em todo o projeto** — anotar todo parametro, retorno e atributo, para cada fronteira dizer o que envia e o que espera (diagnostico de causa). Caminho: a catraca da ADR-009 ja impede os 221 erros do mypy de crescer; baixar por modulo (fronteiras primeiro: `SharedState`, mensagens Pengu, LCU, injector) ate zero, e entao ligar `disallow_untyped_defs`/`strict` por pacote no `pyproject.toml` e promover para bloqueante. **Nao executar ainda** |
| 36 | Padrão 2026 — migrar para pytest, medir cobertura, avaliar Python 3.13 (exige PyInstaller novo + build assinado) | qualidade | Após #33 |
| 37 | Upstream #261 (própria): comentar causa raiz (21069 + código 15 do cleanup, ADR-002) e link do PR; fechar após merge | upstream | Auditorias §8, prioridade 1 |
| 38 | Upstream #250 e #3: pedir log com build novo e correlacionar com etapa 3 (#9–#11) | upstream | Auditorias §8, prioridade 2 |
| 39 | Upstream #255 (mantenedor): botão para encerrar injeção na janela de reconexão, junto com #21 | feature | Auditorias §8, prioridade 3 |
| 40 | Upstream #73: chroma possuído sem a skin (Mythic Shop) volta para a base | bug | Auditorias §8, prioridade 5; precisa de conta com o caso |
| 41 | Upstream #7: responder análise e sanitizar `,` em `overlay_manager.py:435` | segurança | Auditorias §8, prioridade 6; risco baixo |
| 42 | Upstream PR #244 (fila 490): testar e comentar a favor | upstream | Sem código nosso |
| 43 | Upstream PR #211: ajudar a atualizar se o PR local entrar antes | upstream | Conflito em `injection_trigger.py` |
| 44 | **Classificador de compatibilidade de mods** (desbloqueado pelo #45) (`injection/compat/`): detectar link pendurado contra o jogo instalado e recusar injeção antes de suspender o jogo | feature/bug | Crash validado in-game; skill `fantome-compat-rebase` |
| ~~45~~ | ~~Índice de hashes dos WADs do jogo~~ | **feito (módulo), sem call site** | **Medido 2026-09-19** no jogo instalado: 392 WADs / 31,5 GB → 898.520 entradas, construcao em **5,00 s**, pico de 9 MB, indice de **7 MB** em disco (u64 ordenado + mmap + bisect). Pré-requisito do #44; resolve junto o #13 |
| 46 | Reparo determinístico: reconstruir alvo `_Multi_Skins_` a partir dos slots do **jogo** e reescrever a lista `linked` do PROP | feature | Cobre 108 dos 110 casos medidos; supera o gap do Hematite |
| 47 | Aviso na UI quando um mod custom for recusado por incompatibilidade, com o alvo pendurado | UX | Hoje não existe; complementa #16 |
| ~~48~~ | ~~Pico de ~940 MB no download da tabela de hashes~~ | **corrigido e validado** | `perf(hashes)` na `dev`. Quatro copias de 230 MB vivas ao mesmo tempo. Medido com `tracemalloc` na mesma entrada real: **692 MB → 2,1 MB** de pico alocado. Saida SHA-256 identica em 230.694.084 bytes. Ganho extra: `atomic_write`, entao parte que falha no meio nao deixa tabela truncada |
| 49 | Biblioteca de skins vazia em `%LOCALAPPDATA%\Rose\skins`: **5 testes pulam** (3 unitarios + 2 pesados). Rift Classico e integridade da biblioteca ficam sem cobertura | teste | Descoberto na validacao de 2026-09-19. `get_skins_dir()` *cria* o diretorio ao ser chamada, o que mascara a ausencia |
| ~~50~~ | ~~Caminhos absolutos com nome de usuario nos testes~~ | **corrigido** (`get_user_data_dir()`, que não cria `skins/` como efeito colateral) | Era o #2b. Contido na `dev` (o arquivo nao vai para a `main`), mas quebra em qualquer outra maquina |
| 51 | `.gitattributes` ausente com `core.autocrlf=true` → ruido de fim de linha no PR upstream | chore | Descoberto na validacao de 2026-09-19 |
| 52 | `uv` + `pyproject.toml` como fonte unica de dependencias (hoje `requirements.txt` com 11 pins) | qualidade | Padrao 2026; mexe no build assinado |
| 53 | Ruff como **formatter** | qualidade | Padrao 2026. Reformatar 176 arquivos destroi `git blame`: fazer em commit unico e travar em `.git-blame-ignore-revs` |
| 54 | Separacao em camadas (dominio/aplicacao/infra/apresentacao) | refactor | Padrao 2026. Alto risco: `injection/core/manager.py` mistura regra, subprocess e estado. So depois de CI e cobertura |
| 55 | Reduzir estado global mutavel (`SharedState`, 42 modulos) | refactor | Padrao 2026. Alto risco: mexe no timing da injecao |
| 56 | Settings centralizado: 8 `os.environ`/`getenv` espalhados e 2 caminhos `C:\Program Files` fora do `config.py` | qualidade | Padrao 2026; baixo risco |
| 57 | Enums e constantes para numeros magicos (offsets `60000`/`60000000`, `TIMER_HZ`, teto de 180 s, exit code 15). So 3 modulos usam `enum` hoje | qualidade | Padrao 2026; mecanico e testavel |
| 58 | Docstrings nas APIs publicas (1.222 funcoes, 126 classes; 726 com anotacao de retorno = 59%) | qualidade | Padrao 2026; risco nulo |
| 59 | Gate de cobertura no CI | qualidade | Padrao 2026; o #36 preve medir, nao preve minimo |

| 63 | **Tela de instalacao pisca e despeja informacao tecnica** ao usuario. Consolidar numa janela unica com progresso; detalhe so para o log | UX | Observado pelo usuario numa instalacao real em 2026-09-19. **Verificado**: `Rose.spec:423` ja usa `console=False`, e `admin_utils.py` e `pengu_loader.py:400` ja passam `CREATE_NO_WINDOW`; o `installer.iss` usa `runhidden`. Restam sem `creationflags`: `update_installer.py:192` (`cmd /c` do batch) e `:312` (updater standalone) — mas esses sao do caminho de **update**, nao do install limpo. Hipotese mais provavel para o caso observado: o texto de status do launcher durante o primeiro start (download de skins + 230 MB de `hashes.game.txt`). **Precisa de repro visual** antes de mexer. Complementa #16 e #47 |

| 64 | **`WinError 10061` do WebSocket logado como ERROR numa corrida de startup que se resolve sozinha**: LCU conecta (porta ok) mas o WS ainda nao aceita; o retry com backoff reconecta ~15s depois. Rebaixar para WARNING/DEBUG enquanto houver retry pendente e so escalar para ERROR se esgotar | log | Observado em 2026-09-19 10:15:24 (`rose_19-09-2026_10-14-04.log:80`), seguido de `WEBSOCKET CONNECTED` as 10:15:39. Pre-existente, ADR-005. Mesma familia do #18 e #19 |

| 65 | **`lifecycle_manager` le e zera `self.chroma_ui` sem o lock** quando o `acquire` falha (`ui/core/lifecycle_manager.py:202-203`, comentario no codigo: *"risky but necessary"*). **Causa raiz: `self.lock.acquire(timeout=0.001)` na linha 173 — 1 ms.** Com esse teto o caminho sem lock nao e excecao, e o caminho normal sob qualquer contencao | concorrencia | **8 ocorrencias numa sessao de 15 min** in-game em 2026-09-19 (`rose_19-09-2026_10-14-04.log`), nas transicoes de fase (Lobby, InProgress). Sem crash observado, mas roda toda partida. Correcao minima: subir o timeout para algo realista (50-200 ms) e, se ainda falhar, **adiar** a limpeza em vez de fazer sem exclusao mutua. Nao mexer sem teste que reproduza a corrida |

| 66 | **Usuarios relatam erro do interpretador Python ao abrir o Rose apos instalar** | bug/build | Relato recorrente de varios usuarios (2026-09-19). O build e onedir e **empacota o Python** (`python312.dll`, `python3.dll` presentes no `_internal`), entao NAO deveria exigir Python instalado — a hipotese do usuario precisa ser descartada com evidencia. Suspeitos a investigar, em ordem: (a) VC++ Redistributable ausente na maquina (`VCRUNTIME140.dll`/`MSVCP140.dll`); (b) `_internal` incompleto — antivirus em quarentena de algum arquivo durante ou apos a instalacao; (c) caminho > 260 caracteres; (d) instalacao em OneDrive/Known Folder. **Mensagem recebida em 2026-09-19 (print):** `Fatal error detected — Failed to start embedded python interpreter!`. Vem do bootloader do PyInstaller (`Py_InitializeFromConfig` falhou) antes de qualquer codigo do Rose, entao o `rose_*.log` nao existe para esse caso. A janela windowed esconde o detalhe; proximo passo e um build de diagnostico com console (`console=True` ou bootloader debug) para o usuario afetado, mais: versao do Windows, caminho de instalacao, nome do usuario (caracteres especiais), se `_internalase_library.zip` e `python312.dll` existem, e historico do antivirus. Suspeitos ainda nao provados: arquivo do `_internal` em quarentena, caminho com caracteres fora do codepage, `pyinstaller==6.3.0` antigo |
| 67 | **Painel Settings dentro do LoL: check verde nao aparece mesmo com o caminho encontrado**, e o campo do caminho parece bloqueado | bug/UX | Relatado em 2026-09-19 com print (`Settings v1.2.14`, campo com `D:\Riot Games\League of Legends\Game`). **Ja descartado:** nao e incompatibilidade de nome de campo — o Python envia `gamePathValid` (`pengu/communication/message_handler.py:420`) e o JS le `payload.gamePathValid` (`Pengu Loader/plugins/ROSE-SettingsPanel/index.js:1138`). O `valid=` no log e so texto da mensagem. Investigar a partir de: `index.js:1445-1453` (so atualiza se `payload.gamePath === currentPath`, pode perder a resposta se o valor mudou no meio) e `index.js:2600-2607` (ordem entre preencher o input e aplicar o estado). O aspecto 'bloqueado' do campo pode ser so estilo, confirmar se ha `readonly` **Relatos de usuarios (2026-09-19):** alem do check, o Rose as vezes **nao encontra o diretorio do League instalado** (deteccao em `injection/game/game_detector.py` + `config_manager.infer_client_path_from_league_path`, que agora loga a falha em DEBUG pela ADR-008). Pedir: caminho real da instalacao, se e disco diferente de C:, e o `rose_*.log` do start. |
| 68 | **Rift Classico com outros jogadores: `Final name variable: 'None'`, skin base no jogo** | bug | Relato do testador do PR #262 (2026-09-19). `main` e `dev` identicas no caminho da selecao. Tese do Agy (CSS/pointer-events) **refutada** pelo codigo do cliente 16.18. Hipotese: titulo perdido na corrida com o lock + carrossel sem novo titulo. Logs de diagnostico na branch `diag/jade-skin-selection`. **Teste in-game com outro jogador (3 rodadas): nao reproduziu**, `Final name` sempre preenchido. Aguarda log do testador com o build de diagnostico. Detalhes: `tasks/active/2026-09-19-classico-final-name-none.md` |
| 71 | **Skin possuida no Rift Classico ainda monta overlay** e suspende o jogo ~2 s sem efeito | perf/baixa | Medido in-game 2026-09-19 (Ezreal Classico 60081301): `_force_owned_skin` + `inject_skin_immediately` (`threads/handlers/injection_trigger.py:731-738`), mantido de proposito para party skins, que nao existem no Classico. Correcao minima: no JADE, pular a injecao quando a skin e possuida e nao ha mods. Nao mexer sem teste |
| 70 | **Nivel de log configuravel por flag (build/config), para desligar o verbose em producao** | feature/perf | Pedido do usuario em 2026-09-19, **nao fazer agora**. Ja existe meio caminho: modos `customer`/`verbose`/`debug` em `utils/core/logging.py` e flags `--verbose`/`--debug` (`main/setup/arguments.py:28`). Problema: `DEFAULT_VERBOSE = True` fixo em `config.py:346` e `--verbose` e `store_true` com default True, entao **todo build de producao grava DEBUG e nao ha como desligar** (nem por CLI nem por `config.ini`). Proposta: `[General] log_mode = customer|verbose|debug` no `config.ini` + default definido no build (ex.: variavel lida pelo `build_pyinstaller.py`), com `--verbose`/`--debug` sobrepondo. Manter WARNING/ERROR e as linhas de diagnostico do #68 (INFO/WARNING, raras) sempre ativas. Ganho de performance esperado e pequeno (DEBUG do ticker so loga na mudanca); o ganho real e log menor e mais legivel. Medir antes de afirmar ganho. **Criterio do usuario (2026-09-19): no `%LOCALAPPDATA%\Rose\logs` do usuario final so devem aparecer os criticos** (WARNING+); DEBUG/INFO so em build/flag de desenvolvimento. Com a ADR-008 o projeto passou a ter ~90 logs novos, quase todos DEBUG — ficam invisiveis quando este item for feito |
| 73 | **194 `log.error` sem stack trace** (TRY400) | observabilidade | Checklist de 2026-09-19 (`reviews/2026-09-19-checklist-falhas-silenciosas.md`). Trocar por `log.exception`/`exc_info=True` onde o erro muda o resultado para o usuario; comecar por `message_handler` (36), `initialization` (14), `game_monitor` (11) |
| ~~74~~ | **Sem CI**: nenhuma verificacao automatica de testes, da guarda ADR-008 nem da versao de Python | processo | Workflow GitHub Actions com Python 3.12, `unittest discover -s test` e Node 24 (padrao do usuario). Os testes pesados ficam fora (precisam do jogo instalado)  — **feito: ADR-009 (`.github/workflows/quality.yml` + catraca)** |
| 75 | **Engenharia reversa da `cslol-dll.dll` (cs-lol) para alinhar o projeto a ela** | investigacao/risco | Pedido do usuario em 2026-09-19. A DLL e fornecida pelo usuario e validada so por hash (`main/__init__.py` `_check_dll_hash`, `_VALID_DLL_HASHES`); o Rose depende dela via `mod-tools.exe mkoverlay/runoverlay` sem contrato documentado. Levantar: exports e versao, como localiza o jogo e aplica o overlay, formatos WAD aceitos (tipos de entrada, incl. zstd chunked tipo 4, #62), codigos de saida/mensagens (ex.: `runoverlay should have hooked`, #13b), comportamento com mod invalido/link pendurado (#44) e o que muda quando a Riot atualiza o jogo. Entregavel: ADR com o contrato + testes que quebrem se o contrato mudar. So leitura/analise estatica; nunca redistribuir nem alterar a DLL |
| 76 | **Usuarios relatam bugs ao aplicar skin custom** | bug | Relato de 2026-09-19, sem detalhe ainda. Pedir: qual mod (arquivo), campeao/skin alvo, modo de jogo, o que acontece (nao aplica / crash no loading / skin errada) e o `rose_*.log`. Ligacoes conhecidas: mod com link pendurado derruba o jogo no loading (`business-rules.md`, #44 classificador pronto sem call site, #46 reparo, #47 aviso na UI); carrier de skin nao possuida em `injection_trigger._get_custom_skin_carrier_name`. Com a ADR-008, falhas de leitura de manifest/mod agora aparecem no log |
| 77 | **Dependencias com 26 vulnerabilidades conhecidas** (pip-audit 2026-09-19): Pillow 10.4.0 (17, corrigido em 12.3.0), urllib3 2.0.7 (6, em 2.7.0), requests 2.31.0 (3, em 2.33.0); `pyinstaller==6.3.0` defasado (atual 6.22.3) | seguranca | Atualizar em branch propria com build + teste in-game (Pillow e PyInstaller afetam o `.exe`). Ate la o CI trata essas IDs como excecao conhecida em `.github/pip-audit-ignore.txt`; qualquer vulnerabilidade nova barra o merge |
| 78 | **Estrategia de testes por tipo** (lista do usuario filtrada para o Rose) | teste | `plans/estrategia-de-testes.md`: o que se aplica, o que existe, o que falta e a ordem (contrato LCU e mensagens JS/Py primeiro). **Nao executar ainda** |
| 72 | **27 `catch` vazios nos plugins JS** (SettingsPanel 11, FormsWheel 5, ChromaWheel 5, SkinMonitor 4, UI 1, PartyMode 1) | observabilidade | Fora da ADR-008 porque `console.*` vai so para o devtools do cliente, nunca para o `rose_*.log`. Correcao certa: helper que manda erros relevantes pelo bridge (`chroma-log`, nivel warning) e `silent-ok` nos esperados. Exige teste in-game dos plugins antes de ir para a `dev` |
| 69 | **`ChampThread` e codigo morto** (`threads/handlers/champ_thread.py`), inclusive o resync `_try_resolve_cached_skin_after_lock` que cobriria titulo recebido antes do lock | divida | Nunca instanciado (so exportado em `threads/handlers/__init__.py`). Remover ou portar o resync para `ChampionLockHandler` junto com a correcao do #68 |

## Nota sobre Pydantic (#35)

Reavaliar antes de adotar: adiciona dependencia compilada a um bundle PyInstaller que ja
sofre com falso positivo de antivirus (#4), para validar mensagens que vem do proprio plugin
JS do projeto. `TypedDict` + validacao explicita entrega o mesmo contrato sem tocar na
superficie do instalador. Tradeoff: perde coercao automatica e mensagens de erro prontas.

## Nota sobre camada nativa (Rust/C++)

Medido em 2026-09-19: o trabalho pesado ja e nativo (`mod-tools.exe`, cslol C++). O que sobrou
em Python e orquestracao — I/O e espera, menos de 2% de um core em regime. Construir o indice
do #45 custa 5,00 s e 9 MB em Python puro. **Criterio para reabrir:** construcao acima de 10 s
ou consulta virando caminho quente do #44 em tempo de injecao. Se disparar, modulo pequeno e
isolado com **fallback Python obrigatorio** — o app nunca pode depender do binario nativo para
subir. Atencao: `.gitignore` ignora `*.pyd` e `*.c`, entao extensao nativa sumiria do commit.

## Ligar o índice de WADs ao app (sucessor do #45)

O módulo `injection/compat/wad_index.py` está pronto e testado, mas **sem nenhum call
site** — de propósito, para a entrega não poder alterar comportamento. Ligar ao app é
passo separado e tem efeito colateral real:

- construção em background no start (thread a mais, I/O de 392 arquivos);
- onde guardar o índice (`get_state_dir()`, nunca dentro da pasta do jogo);
- o que fazer enquanto não estiver pronto (o caminho atual precisa continuar valendo).

## Viabilidade do #13 (mkoverlay no cache frio) — não medida

A hipótese é que construir o índice no start aqueça o cache de disco e o `mkoverlay`
deixe de levar 97 s. **Não dá para testar sem cache frio**, o que exige reiniciar a
máquina ou descartar o cache do SO. Medições com cache quente não dizem nada sobre isso.
O índice lê só cabeçalho e TOC; o `mkoverlay` lê mais que isso, então o aquecimento pode
ser parcial. Tratar como hipótese até medir depois de um boot.

## Viabilidade do #51 (.gitattributes) — adiar

Adicionar `.gitattributes` com `text=auto` **renormaliza o repositório inteiro** e gera
um diff gigante, justamente no que vai virar PR upstream. Seguro só junto do #53 (Ruff
formatter), no mesmo commit isolado, travado em `.git-blame-ignore-revs`.
| 60 | **Comentarios e docstrings em portugues no codigo** → traduzir para ingles. Producao: `injection/compat/wad_index.py` e `injection/compat/__init__.py` (2 arquivos, ambos vao para a `main`, entao sao os que importam para o PR). Testes: `test/test_hashes_streaming.py`, `test/test_wad_index.py` e os 6 de `testes_Pesados/` (nunca vao para a `main`) | qualidade | Levantado pelo usuario em 2026-09-19. O resto do codigo ja esta em ingles. Nao e prioridade agora, mas **arquivo novo ja nasce em ingles** |
| ~~44~~ | ~~Classificador de compatibilidade de mods~~ | **feito como modulo, sem call site** | `injection/compat/mod_scanner.py`. Link resolve contra jogo UNIAO entradas do proprio mod. `has_dangling_links` = evidencia positiva de crash; `complete` = tudo foi lido. 27 testes |
| 61 | `WadReader.read()` devolve `Optional[bytes]` e `classic_skin_builder.py:326` passa direto para `retarget_skin_bin(source: bytes, ...)` → AttributeError se a entrada faltar | bug | Latente, pre-existente. Caminho do Classico com 3 testes pulando: **nao mexer sem cobertura** (#49) |
| 62 | Suporte a entrada WAD tipo 4 (zstd chunked) no `WadReader` | feature | 227 de 445 entradas medidas em WADs de campeao. Sem isso o scanner do #44 inspeciona menos da metade de um mod de conteudo |

## Ligar o scanner de compatibilidade ao app (sucessor do #44)

`scan_mod` esta pronto e testado, **sem call site**. Ligar significa recusar injecao antes de
suspender o jogo, que e mudanca de comportamento visivel ao usuario. Regras que o call site
precisa respeitar:

- recusar **so** quando `has_dangling_links` for True — evidencia positiva;
- **nunca** recusar por `scan_mod` devolver `None` (ilegivel) nem por `not complete`;
- avisar na UI com os alvos pendurados (backlog #47);
- custo: o scan le todas as entradas legiveis do mod. Mod redirect (99,5% da biblioteca) tem
  1-2 entradas de ~3 KB, entao e irrelevante; mod de conteudo pode ter centenas.

## Pre-requisito do build ao ligar o scanner (#44)

`injection.compat.mod_scanner` **nao entra no build** enquanto nao tiver call site: o
PyInstaller so empacota o que alcanca por import estatico. Confirmado no build de 2026-09-19,
onde `injection.compat.wad_index` esta no PYZ (importado por `manager.py`) e o `mod_scanner`
nao. Ao ligar, conferir que ele aparece no PYZ; se o import for dinamico, adicionar a
`hiddenimports` do `Rose.spec`.

Verificacao correta (grep no `.exe` da falso negativo): extrair `PYZ-00.pyz` do CArchive com
`PyInstaller.archive.readers.CArchiveReader` e listar o TOC do `ZlibArchiveReader`.

## #13 — hipotese do pre-aquecimento REFUTADA (medido 2026-09-19)

A ideia era que construir o indice de WADs no start aqueceria o cache de disco e o
`mkoverlay` deixaria de levar ~97 s. **Nao se sustenta.**

Medido em partida real (`rose_19-09-2026_10-14-04.log`):

```
10:15:41  [WADIDX] Indexed 802652 entries from 392 WADs  (leu a TOC de TODOS os WADs)
10:16:48  mkoverlay iniciado
10:16:52  Game suspended - Auto-resume: 60s
10:17:33  mkoverlay completed in 44.33s
```

Sessenta e sete segundos depois de ler as 392 TOCs, o `mkoverlay` ainda levou **44,33 s**.
Ler cabecalho + TOC nao aquece o que ele precisa: ele le o **conteudo** dos WADs, dezenas de GB.

**Consequencias:**
- o #13 continua aberto e **nao** sai de carona no #45;
- a margem real e estreita: 44,33 s contra 60 s de `monitor_auto_resume_timeout` (15,7 s). Disco
  mais frio ou mais ocupado estoura, e ai o mod nao carrega **sem erro visivel** para o usuario;
- o jogo ficou **41 s congelado** (suspend 10:16:52 -> resume 10:17:33), o que por si so e ruim de UX;
- caminhos que sobram: subir o teto do timeout (compra margem, nao resolve), pre-aquecer lendo o
  conteudo dos WADs relevantes ao mod (caro), ou atacar o lado do `mod-tools`.

## #13 — A/B decisivo na mesma sessao (2026-09-19)

Duas injecoes do **mesmo mod** (`CHROMA_238070`), mesma maquina, mesma sessao do Rose, com
poucos minutos de intervalo. Unica variavel: o cache de disco.

| | Rodada 1 (frio) | Rodada 2 (quente) | Fator |
|---|---|---|---|
| `mkoverlay` | 44,33 s | **2,36 s** | **18,8x** |
| Jogo congelado | 41 s | ~1 s | 41x |
| Margem ate o auto-resume (60 s) | 15,7 s | 57,6 s | |

**Conclusoes, e as duas medicoes sao necessarias para chegar nelas:**

1. O cache de disco **e** a variavel dominante — confirmado (18,8x). Consistente com os 97,63 s
   vs 4,20 s registrados antes.
2. Mas **ler so as TOCs nao aquece**: o indice leu as 392 TOCs 67 s antes da rodada 1, e ela
   ainda levou 44,33 s. Logo, um pre-aquecimento eficaz precisa tocar o **conteudo** dos WADs
   que o `mkoverlay` le, nao o indice deles.
3. Portanto o #13 e um problema de **primeira injecao apos o boot**, nao de toda injecao. Isso
   **rebaixa a prioridade** dele: o caso comum (segunda partida em diante) ja custa ~2 s.
4. O risco residual e real e estreito: na primeira injecao do dia sobram 15,7 s de margem. Disco
   mais lento, antivirus varrendo ou jogo recem-atualizado estouram os 60 s — e ai o mod nao
   carrega **sem erro visivel**.

**Correcao mais barata e honesta:** subir `monitor_auto_resume_timeout` (teto 180 s no codigo)
nao resolve a causa mas elimina o risco residual quase todo, a custo de congelar o jogo por mais
tempo no pior caso. Pre-aquecer conteudo e caro e so ajuda a primeira vez.

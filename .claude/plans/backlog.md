# Backlog — Rose

Ordenado por prioridade. Checklists detalhados: skills `prod-risk-review` e `windows-trust-review`. Origem e status de cada achado: `reviews/2026-09-17-auditorias.md`.

| # | Item | Tipo | Contexto |
|---|---|---|---|
| 1 | Teste C in-game: fechar o Rose pela bandeja durante a partida (jogo não pode congelar) | validação | ADR-007 |
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
| 15 | Rift Clássico: seleção de chroma (ChromaWheel/FormsWheel reconhecer `.skins-pane`) | feature | Dados de 1196 chromas já validados (ADR-004) |
| 16 | Rift Clássico: aviso na UI quando a skin não puder ser exibida | UX | Hoje só aparece no log |
| 17 | Testes não criarem `log_updater_*.log` vazios em `%LOCALAPPDATA%` (import de `launcher` cria o arquivo) | qualidade | 71 arquivos vazios gerados por execuções de teste |
| 18 | Rebaixar `Pengu command failed ... League Client UX is not running` no cleanup para WARNING/DEBUG | log | Ruído ao fechar Rose em partida |
| 19 | Reduzir spam de `LCU lockfile is not ready` | log | ~2200 linhas em 9h com cliente fechado |
| 20 | `build_pengu_loader.py`: suportar `dotnet msbuild -restore` nativamente; opção de reutilizar binários assinados do Pengu | build | ADR-003 |
| 21 | Detectar crash pós-injeção (`InProgress → Reconnect` em < 60s) e reportar skin suspeita | feature | Caso 21069 |
| 22 | Remover hidden import inexistente `websocket_client` do `Rose.spec` | build | `ERROR: Hidden import 'websocket_client' not found` |
| 23 | Erros silenciosos restantes (S110 fora dos módulos críticos) + opt-out de analytics no painel | qualidade | ADR-005 |
| 24 | Decidir versionamento de `test/` (hoje ignorado; só `test_pengu_loader.py` rastreado) | chore | Decisão do usuário: manter local por ora |
| 25 | Recusa por campeão incompatível (`injection_trigger.py:156/175`) não marca `last_hover_written`: ~300 WARNING a 1000 Hz | log/bug | Auditorias §3 #13; pode ser retry intencional — analisar timing |
| 26 | Sync de skins: baixar só arquivos alterados via GitHub compare em vez do ZIP inteiro quando acima do limite | desempenho | Auditorias §4 |
| 27 | `TIMER_HZ_DEFAULT` 1000 → 20–60 Hz | desempenho | **Nao e gargalo**: medido 1,6% de um core, e o loop entrega ~650 Hz, nao 1000. Motivo real e a resolucao de timer do Windows elevada para o sistema todo. Muda timing do gatilho; validar in-game |
| 28 | Do PR #184: histórico e random isolados por modo (`scope`) | feature | Auditorias §6 |
| 29 | Do PR #184: proteção contra seleção atrasada (gerações) na trava final | bug | Auditorias §6 |
| 30 | Do PR #184: UI do Clássico (chroma, histórico, random) sobre o builder próprio | feature | Complementa #14–#16 |
| 31 | Do PR #184: endpoints do LeagueSkins derivados de `repo_url` (`1204dcc8`) | refactor | Pequeno e independente |
| 32 | `scripts/build_pyinstaller.py`: abortar se não conseguir remover `dist/` (hoje só loga e segue) | build | Auditorias §7 |
| 33 | Padrão 2026 — base: `pyproject.toml` com Ruff/basedpyright em modo relatório, CI (Windows, Python 3.12) com testes + lint só nos arquivos alterados + smoke do build, pre-commit | qualidade | Auditorias §2 |
| 34 | Padrão 2026 — `log.exception` nos módulos críticos (TRY400), `print` → logger em `window_utils.py`/`main/__init__.py`/`signals.py` | qualidade | Só adiciona log |
| 35 | Padrão 2026 — tipagem incremental pelas fronteiras (`SharedState`, injector/manager, mensagens), Pydantic para mensagens do Pengu, Enums para fases/modos | qualidade | Após #33 |
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

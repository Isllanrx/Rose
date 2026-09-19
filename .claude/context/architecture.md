# Arquitetura — Rose

Changer de skins de League of Legends para Windows. Roda na bandeja do sistema, detecta a skin escolhida na seleção de campeão e injeta um overlay de mod quando a partida inicia.

## Stack
| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11+ (build local: 3.12 — pyinstaller 6.3.0 não suporta 3.13+); `xxhash`/`zstandard` para ler WADs no Rift Clássico |
| Empacotamento | PyInstaller (`Rose.spec`, `uac_admin=True`) via `scripts/build_pyinstaller.py`; instalador Inno Setup (`installer.iss`) |
| UI no cliente | Plugins JS carregados pelo Pengu Loader (`Pengu Loader/plugins/ROSE-*`) |
| Loader | Pengu Loader 2.0.0 compilado de `vendor/PenguLoader-1.1.6` (C#, net472 + WPF) |
| Injeção | `mod-tools.exe` (CSLOL) `mkoverlay` / `runoverlay` + `cslol-dll.dll` (fornecida pelo usuário, validada por hash) |
| Party mode | Cloudflare Worker `relay-worker/` (Durable Object `PartyRoom`) |

## Fluxo principal
1. **Launcher** (`launcher/`): atualização do app (GitHub Releases, pede confirmação) → hashes do jogo (CommunityDragon, sem confirmação) → sync de skins (`Alban1911/LeagueSkins`, incremental por SHA de commit).
2. **Startup** (`main/`): threads Phase, WebSocket (LCU), LCU Monitor, Pengu Skin Monitor (servidor HTTP/WS local na porta 50000+), Analytics.
3. **LCU conectado** → ativa Pengu Loader pela CLI oficial → plugins JS conectam ao bridge local.
4. **ChampSelect**: plugins enviam skin/chroma → `SharedState`; `ui/` gerencia modos random/historic/chroma.
5. **Gatilho de injeção** (`threads/handlers/injection_trigger.py`): no fim do timer, `SkinNameResolver` escolhe o alvo → `injection/core/injector.py`.
6. **Overlay** (`injection/overlay/overlay_manager.py`): suspende o jogo → `mkoverlay` → `runoverlay` → retoma o jogo; overlay ativo até o fim da partida.

### Variante Rift Clássico (`gameMode=JADE`, fila 3262)
- Detecção em `threads/handlers/game_mode_detector.py` → `state.current_game_mode = "JADE"`.
- Plugins: `ROSE-SkinMonitor` lê `.skins-pane__skin-title`; `ROSE-UI` esconde o cadeado do `.skins-pane` e troca o subtítulo "Desabilitada" pelo rótulo localizado de habilitada.
- `InjectionManager.inject_skin_immediately` → `SkinInjector.prepare_classic_mod` (antes do monitor que suspende o jogo) → `injection/classic/classic_skin_builder.py`:
  1. normaliza IDs do cliente (`60000 + campeão`, `60000000 + skin`);
  2. alias do WAD via qualquer arquivo da biblioteca do campeão (`champion_alias_from_library`, cache em memória);
  3. índice de personagens `jade_*` do `hashes.game.txt` (cache em `state/classic_characters.json`);
  4. lê `jade_*/skins/skinN.bin` do WAD **instalado** (`WadReader`) e gera `skin0/301/302.bin` para campeão e auxiliares;
  5. entrega a pasta do mod para `SkinInjector.inject_skin(prepared_mod=...)`.

## Módulos
| Pasta | Responsabilidade |
|---|---|
| `launcher/` | Update do app, hashes, sync de skins (janela Win32) |
| `main/` | Entry point, argumentos (`--dev`, `--logs`), instância única, cleanup |
| `lcu/` | Cliente LCU (lockfile, REST, cache de skins) |
| `threads/` | Threads de fase/WS/monitor + handlers (injection trigger, reset de ChampSelect) |
| `state/` | `SharedState` (dataclass mutável compartilhada entre threads) |
| `ui/` | Chroma, random, historic mode, exibição de skin |
| `pengu/` | Bridge WebSocket com plugins JS (`message_handler`, `broadcaster`) |
| `injection/` | Resolução de `.fantome`, overlay, processos, monitor do jogo |
| `party/` | Compartilhamento P2P de skins via relay |
| `utils/` | Download, logging, integração Pengu/tray, paths, extração segura |

## Diretórios em runtime
- App instalado: `C:\Program Files\Rose\` (`_internal\injection\tools`, `_internal\Pengu Loader`)
- Dados do usuário: `%LOCALAPPDATA%\Rose\` — `skins\`, `injection\mods|overlay`, `logs\`, `state\`, `Pengu Loader\` (cópia sincronizada do bundle a cada start)
- Jogo: via LCU/`config.ini`, ex. `D:\Riot Games\League of Legends\Game`
- Logs do jogo: `<League>\Logs\GameLogs\<timestamp>\*_r3dlog.txt`, `<League>\Logs\GameCrashes\`

## Padrões
- Estado global via `SharedState` + threads; async apenas no servidor WS do Pengu.
- Python ↔ JS por mensagens tipadas (`chroma-selection`, `random-mode-state`, ...).
- Processos externos com `CREATE_NO_WINDOW` e prioridade elevada (psutil).
- Persistência de estado (config, histórico, SHA das skins) com troca atômica (`utils/core/atomic_file.py`, ADR-006).
- Shutdown (`main/core/cleanup.py`): retomar jogo suspenso → desativar Pengu → matar mod-tools → bandeja → threads → lockfile, cada etapa isolada (ADR-007).
- Sync de skins registra o SHA fixado antes do download e só quando todos os arquivos foram gravados.

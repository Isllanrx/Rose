# Padrões e armadilhas — Rose

## Padrões locais
- Logger: `utils.core.logging.get_logger()`; prefixos por domínio: `[INJECT]`, `[RANDOM]`, `[HISTORIC]`, `[CHROMA]`, `[SkinMonitor]`, `[WS]`, `[UI]`.
- Falhas visíveis ao usuário: `report_issue(code, level, msg, details, hint)`.
- Broadcast de estado para JS sempre em `try/except` com log DEBUG (plugins podem não estar conectados).
- Resets de `SharedState` centralizados em funções (ex.: `_clear_random_mode`), sem duplicar atribuições.
- Testes: `unittest` em `test/`; rodar de `Rose/` com `.venv\Scripts\python -m unittest discover -s test`.

## Armadilhas conhecidas
- **Exit code 15**: `psutil.Process.terminate()` no Windows encerra com 15. Não tratar como crash sem checar `ProcessManager.stop_requested`.
- **`mod-tools runoverlay` sem stdin** (shell de automação) sai na hora com 0. Em testes com binário real, manter stdin aberto.
- **`mkoverlay` é lento só no cache frio**: mesma entrada mediu 97,63 s na primeira execução e 4,20 s na segunda. A variável dominante é o cache de disco do WAD do jogo, não o tamanho do mod. Quando `mkoverlay completed in` aparece **depois** de `Stopping monitor after auto-resume`, o overlay perdeu a janela de hook e o mod não carrega — sem erro visível ao usuário, que só vê "a skin não apareceu". A mensagem `runoverlay should have hooked` não verifica nada e pode afirmar sucesso falso. `monitor_auto_resume_timeout` é lido em runtime do `config.ini` (sem rebuild) e tem teto de 180 s no código (`injection/core/manager.py:59`).
- **Links de um BIN resolvem contra jogo ∪ próprio mod**, nunca só contra o jogo — o mod costuma trazer seus próprios alvos como assets novos. Medir só contra o jogo inflou a contagem de 110 para 513 no mesmo arquivo.
- **Dois caminhos de seleção de chroma** em `pengu/communication/message_handler.py` (ChromaSelector e fallback headless). Regras de seleção devem cobrir ambos; o fallback é o usado em produção.
- **Mensagens JS alteram estado Python**: confirmar que a mensagem é disparada só por ação do usuário antes de atrelar regras a ela.
- **Build local**:
  - Python 3.12 (pyinstaller 6.3.0 não suporta 3.13+).
  - `scripts/build_pyinstaller.py` chama `pyinstaller` do PATH → ativar o venv.
  - MSBuild do VS Build Tools sem SDK .NET → `MSBUILD_EXE` apontando para wrapper `.cmd` com `dotnet msbuild -restore %*`.
  - Pengu Loader compilado localmente sai sem assinatura → bloqueado pelo Smart App Control (`WinError 4551`). Substituir pelos binários assinados da instalação oficial.
  - `cslol-dll.dll` e `hashes.game.txt` não estão no repo: copiar de `C:\Program Files\Rose\_internal\injection\tools\`.
- **`Rose.exe` exige admin** (`uac_admin=True`): não inicia de shell não elevado ("Permission denied").
- **UI do cliente difere por modo**: seletores do champ select normal (`.skin-selection-*`, `.skin-name-text`) não existem no Rift Clássico (`.skins-pane*`). Antes de adaptar plugins a uma tela nova, capture o DOM real com um plugin de diagnóstico temporário em `%LOCALAPPDATA%\Rose\Pengu Loader\plugins\` (enviando `chroma-log` pelo `window.__roseBridge`) em vez de chutar seletores; remova após o uso.
- **IDs do Rift Clássico** são deslocados (`60000 + campeão`, `60000000 + skin`). Qualquer busca na biblioteca de skins precisa normalizar com `to_regular_*` de `injection/classic`.
- **Escrita de estado**: usar `utils/core/atomic_file.atomic_write`/`write_text_atomic`, nunca `open(path, "w")` direto em config/histórico/estado. `durable=False` só para gravação em massa (skins) — `fsync` custa ~12 ms por arquivo (ADR-006).
- **Histórico**: ler-modificar-gravar dentro de `_write_lock` do módulo (`historic.py`, `mod_historic.py`).
- **Threads**: exceção não tratada aparece como `Uncaught exception in thread <nome>` (hook global, ADR-007). Não colocar try/continue dentro de loops de alta frequência (ticker a 1000 Hz) — erro repetiria a ação em série; proteger em volta do loop.
- **Testes locais**: `test/` está no `.gitignore` (decisão do usuário, só `test_pengu_loader.py` rastreado). Importar `launcher` cria `log_updater_*.log` vazio em `%LOCALAPPDATA%\Rose\logs` — não confundir com aberturas do Rose.
- **Testes com `hashes.game.txt`**: 4 testes do Clássico pulam se `dist\Rose\_internal\injection\tools\hashes.game.txt` não existir (o build limpa o `dist`; copiar de novo).
- **Build**: fechar todo `Rose.exe`/`mod-tools.exe`/`Pengu Loader.exe` que rode do `dist` antes de buildar (arquivo travado aborta o PyInstaller e deixa o `dist` meio apagado). Considerar o build pronto só após: log com `BUILD COMPLETED SUCCESSFULLY` e `Removed dist/`, presença de `_internal\certifi\cacert.pem` e `_internal\assets\tray_*.png`, binários do Pengu/DLL/hashes idênticos aos instalados. Não confiar no código de saída de um comando que embrulha o build.
- **Validação old vs new**: `git worktree add --detach <scratchpad>/old HEAD`, copiar `test/` e rodar a mesma suíte nos dois; cada teste novo deve falhar no old e passar no new.
- **`pass` intencional** só com comentário explicando por que o erro é esperado (ex.: cache ausente em `load_jade_characters`).
- **Pylance/mypy** acusam imports não resolvidos quando o workspace é `projeto_rose/` em vez de `Rose/` — falso positivo.

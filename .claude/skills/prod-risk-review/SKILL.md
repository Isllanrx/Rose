---
name: prod-risk-review
description: Review sistemático do Rose focado em falhas que quebram em produção e erros silenciosos (threads que morrem, except engolindo erro, processos externos, rede, arquivos, estado compartilhado, shutdown). Ignora tipagem, estilo e formatação. Use quando pedirem "code review", "está apto para produção", "o que pode quebrar em prod", "erros silenciosos" ou antes de uma release.
---

# Prod Risk Review — Rose

Objetivo: achar defeitos que o usuário final sente (injeção não acontece, skin errada, jogo congelado, app travado/fechando, dados corrompidos) ou que somem sem rastro no log.
Fora de escopo: type hints, PEP 8, nomes, formatação, docstrings, micro-otimização.

## Regras
- Só reportar achado com **cenário concreto de falha** (entrada/estado → resultado errado) e `arquivo:linha`.
- Ler o código em volta antes de concluir; confirmar chamadores com Grep.
- Descartar o que já é intencional e documentado (`.claude/context/coding-standards.md`, ADR-002, ADR-005).
- Classificar: **crítico** (quebra fluxo principal / congela jogo / perde dados), **alto** (falha frequente ou silenciosa em fluxo importante), **médio** (caso de borda), **baixo** (diagnóstico/ruído).
- Não corrigir sem pedido; propor correção mínima + teste que reproduz.

## Varredura por ferramenta (ponto de partida, não conclusão)
```
uvx ruff@latest check . --exclude .venv,vendor,build,dist,relay-worker,skin-key-worker \
  --select S110,S112,BLE001,TRY400,B904,F821,F841,B023,B006,B008,PLW0603,SIM115,S603,S607,S108,S324,S202 --output-format concise
```
basedpyright em modo `standard`, considerando só: `reportPossiblyUnbound`, `reportOptionalMemberAccess`, `reportOptionalSubscript`, `reportUndefinedVariable`, `reportCallIssue`, `reportAttributeAccessIssue` (os demais são tipagem).

Guarda automática de erro silencioso (ADR-008): `python -m unittest test.test_no_silent_exceptions` lista todo `except` sem log, `raise` ou `# silent-ok: <motivo>`. Rodar sempre; revisar se cada `silent-ok` novo é mesmo fluxo esperado e se log novo não está em loop quente (DEBUG é gravado em produção enquanto o #70 não for feito).

## Checklist por categoria

### 1. Threads e concorrência
- `run()` de thread sem try/except externo: exceção mata a thread sem log e o recurso para (phase, WS, LCU monitor, ticker, Pengu bridge).
- Leitura-e-escrita de `SharedState` entre threads sem lock (check-then-act: `if not state.x: state.x = True`).
- Lock adquirido sem `with`/`finally`; flags "in progress" não liberadas em caminhos de erro/return antecipado.
- Loops `while` sem condição de parada ligada a `state.stop`; `join()` sem timeout no shutdown.
- asyncio: tarefa criada sem guardar referência ou sem tratar exceção; chamada bloqueante dentro do loop.

### 2. Tratamento de erro silencioso
- `except ...: pass/continue/return None` sem log em fluxo que o usuário depende.
- `except Exception` que engloba o caminho feliz inteiro e converte falha em "sucesso" (retorna True/valor padrão).
- Log em DEBUG para falha que muda o resultado para o usuário (deveria ser WARNING/ERROR).
- Valor de retorno de erro ignorado pelo chamador (`False`/`None` não checado).
- `raise` dentro de `except` sem `from` perdendo a causa.

### 3. Processos externos (mod-tools, Pengu Loader)
- `subprocess`/`Popen` sem timeout, sem leitura de stdout/stderr (pipe cheio trava), sem checar returncode.
- Jogo suspenso sem garantia de resume em todos os caminhos (exceção, timeout, shutdown).
- Kill de processo errado (match por nome amplo); tratar código 15 como crash (ADR-002).

### 4. Rede e LCU
- `requests` sem `timeout`; retry sem limite/backoff; exceção de rede subindo até a thread.
- Resposta JSON assumida (`resp.json()["x"]`) sem checar status/forma; lockfile/porta mudando após restart do cliente.
- Download parcial aceito como completo; estado de sync (SHA) gravado antes da extração terminar.

### 5. Arquivos e dados
- Escrita não atômica de estado/config (crash no meio corrompe; próximo start falha).
- JSON/INI corrompido derrubando o startup em vez de cair no padrão.
- Extração de ZIP fora de `utils/core/safe_extract.py` (path traversal); caminhos relativos ao CWD.
- `open()` sem `with`; arquivo travado por outro processo no Windows (`PermissionError`) não tratado.

### 6. Estado e fluxo de negócio
- Estado de modo (random/historic/custom mod/party) não limpo em algum caminho de saída de ChampSelect.
- Injeção disparada duas vezes ou nunca (threshold, ticker id, `last_hover_written`).
- IDs deslocados do Rift Clássico (`60000+`) usados sem `to_regular_*`.
- Mensagens do JS com campos ausentes/tipos errados causando `KeyError`/`TypeError` no handler.

### 7. Startup, shutdown e empacotamento
- Import que só falha no build PyInstaller (hiddenimports, `__file__`, recursos fora de `sys._MEIPASS`).
- Cleanup que lança e impede as etapas seguintes (desativar Pengu, matar mod-tools, resume do jogo).
- Instância única/lockfile não liberado após crash.

## Relatório
Tabela ordenada por severidade: `severidade | arquivo:linha | defeito | cenário de falha | correção mínima`.
Separar no final: **confirmados** (cenário verificado no código) e **plausíveis** (dependem de condição de runtime não verificada).

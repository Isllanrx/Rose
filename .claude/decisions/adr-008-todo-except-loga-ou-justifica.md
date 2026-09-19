# ADR-008 — Todo `except` loga, relança ou justifica o silêncio

- **Status:** aceito
- **Data:** 2026-09-19
- **Sucede em parte:** ADR-005 (triagem por severidade)

## Contexto
Investigando o #68 (Rift Clássico, `Final name 'None'`), o `websocket_event_handler.handle_message`
envolvia todo o processamento da sessão do LCU (lock, timer) num `except Exception: pass`: qualquer
exceção ali sumia sem rastro. A varredura por AST achou **237 handlers sem log** no projeto
(148 só engolindo com `pass`/`continue`/`return` padrão). A ADR-005 tinha triado os críticos,
mas sem regra que impedisse novos.

## Decisão
- Todo `except` no código de produção deve: chamar log, relançar, **ou** marcar a linha do
  `except` com `# silent-ok: <motivo>`.
- Níveis: falha que muda o resultado para o usuário = WARNING/ERROR; fallback/diagnóstico = DEBUG.
- Caminho quente (ticker a 1000 Hz, polling de janela, loops async) não loga a cada iteração:
  loga uma vez (flag) ou fica `silent-ok`.
- `silent-ok` é para fluxo esperado: `CancelledError`/timeout em loop async, dependência opcional
  (`ImportError`), processo que sumiu durante iteração, `RuntimeError` de "sem loop rodando",
  infraestrutura do próprio logging, código antes do logging existir.
- Guarda: `test/test_no_silent_exceptions.py` falha listando `arquivo:linha` de qualquer handler novo
  sem log nem marcador (escopo: `git ls-files *.py` fora de `vendor/ test/ testes_Pesados/ scripts/`
  e workers).

## Alternativas consideradas
- **Log em todos os 237, mecanicamente**: o Rose grava DEBUG em produção (`DEFAULT_VERBOSE = True`,
  #70); log em loop quente inundaria o arquivo e viraria bug novo.
- **Só Ruff S110 em CI**: não pega `continue`/`return` padrão nem aceita justificativa por linha.

## Consequências
- Resultado: 237 → 0 sem justificativa (≈90 ganharam log, ≈147 marcados com motivo).
- O arquivo do usuário só fica enxuto quando o #70 (modo de log por flag, padrão = críticos) for feito.
- JS dos plugins fora do escopo: 27 `catch` vazios; `console.*` não chega ao `rose_*.log` (#72).

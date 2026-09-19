# ADR-005 — Triagem de erros silenciosos por severidade

- **Status:** aceito
- **Data:** 2026-09-16

## Contexto
Ruff apontou 109 `try/except/pass` (S110) e 542 `except Exception` (BLE001). Investigando logs reais, havia perda de informação crítica: falha ao desativar o Pengu no shutdown, falha ao gravar o estado de update, e **todo o log do `repo_downloader` durante o launcher era descartado** (o logger `tracer` ainda não tem handler nessa fase).

## Decisão
- Corrigir por severidade, sem alterar fluxo: manter o tipo de exceção capturado e adicionar log com contexto.
  - **Crítico** (WARNING): desativação do Pengu em sinais/sessão, persistência do estado de update, checagem de release, amostras do base skin tracker, início do tracking de base skin, seleção salva de mods/histórico, threshold não aplicado.
  - **Alto/diagnóstico** (DEBUG): limpeza de arquivos temporários, respostas de diagnóstico, handles de mutex, issue_reporter.
- Manter silenciosos (intencionais): exceções estreitas esperadas (`ValueError` de parse, `psutil.NoSuchProcess`, `relative_to`) e UI best-effort (MessageBox, `tk.destroy`).
- Launcher: `_route_logger` encaminha o logger `tracer` para o `log_updater` enquanto o launcher roda.
- `issue_reporter.clear_issue` removido (sem chamadores e nunca removia linhas).
- Analytics: opt-out em runtime por `[General] analytics_enabled = false` no `config.ini`; timeout 30s → 5s.

## Alternativas consideradas
- **Substituir todos os 214 handlers**: alto risco de mudança de comportamento em áreas sem teste.
- **Estreitar os tipos de exceção**: melhora semântica, mas pode propagar exceções hoje contidas; adiado para quando houver cobertura.

## Consequências
- S110 no projeto: 109 → 72; nos módulos críticos/altos restam 7, todos intencionais.
- Testes: `test/test_silent_failure_logging.py`, `analytics/tests/test_analytics.py` (red sem a correção, green com).
- Recomendado ativar `S110`/`BLE001` do Ruff em CI apenas para arquivos alterados.

# ADR-009 — CI com regras bloqueantes e catraca de qualidade

- **Status:** aceito
- **Data:** 2026-09-19
- **Resolve:** backlog #74 (sem CI) e a parte de CI do #33

## Contexto
O projeto não tinha nenhuma verificação automática: testes, a guarda da ADR-008 e boas práticas
dependiam de alguém lembrar de rodar. Há dívida existente (mypy: 221 erros; Ruff: 194 TRY400,
22 `print`, 23 `global`...). Bloquear tudo trava qualquer mudança; só relatar deixa crescer.

## Decisão
`.github/workflows/quality.yml` (push/PR em `dev` e `main`, `windows-latest`, Python 3.12,
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`) roda três passos:
1. **Ruff bloqueante** (`pyproject.toml`): só regras com **zero** violações hoje — sintaxe, nome
   indefinido, default mutável, `return` em `finally`, `eval`/`exec`, `pickle`, `shell=True`,
   `requests` sem timeout, `raise e`, `assert` em produção, task async sem referência, etc.
2. **Testes unitários**, incluindo a guarda da ADR-008.
3. **Catraca** (`scripts/quality_gate.py`): mypy + regras Ruff com dívida. Falha se qualquer
   contagem **subir** em relação a `.github/quality-baseline.json`. Quando descer, a mudança roda
   `--update` para travar a melhora.

Ferramentas fixadas em `requirements-dev.txt` (`ruff==0.16.8`, `mypy==2.3.1`) para a linha de base
ser comparável. Testes pesados ficam fora (precisam do jogo instalado).

## Alternativas consideradas
- **mypy/Ruff completos bloqueantes**: 221 + ~300 violações travariam todo PR.
- **Só relatório (`continue-on-error`)**: ninguém lê; a dívida cresce.
- **Lint só nos arquivos alterados**: pega arquivo tocado inteiro, pune quem mexe em arquivo antigo.

## Consequências
- Validado em clone limpo + venv novo: Ruff OK, 205 testes OK (4 pulam sem a biblioteca de skins),
  catraca OK; e cada passo **falha** com violação injetada (`eval`, `print`, `except: pass`).
- Nova regra zerada pode ser promovida da catraca para o bloqueio no `pyproject.toml`.
- Rodar local: `python -m pip install -r requirements-dev.txt`, depois os três comandos do workflow.

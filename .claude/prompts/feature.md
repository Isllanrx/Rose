# Template — Nova feature (Rose)

## 1. Definição
- Problema do usuário:
- Comportamento esperado (fase do gameflow em que ocorre):
- Fora de escopo:

## 2. Impacto
- [ ] Estado novo ou alterado em `SharedState`? Quem cria, quem limpa (ChampSelect reset, pós-injeção, shutdown)?
- [ ] Interação com prioridade do `SkinNameResolver` (historic > random > seleção)? Atualizar `context/business-rules.md`.
- [ ] Nova mensagem Python ↔ JS? Definir `type`, payload e se é disparada só por ação do usuário.
- [ ] Plugin JS afetado (`Pengu Loader/plugins/ROSE-*`)?
- [ ] Processo externo / arquivos em `%LOCALAPPDATA%\Rose`? Usar `safe_extract` e paths de `utils/core/paths`.
- [ ] Config nova em `config.py`/`config.ini` com default seguro?

## 3. Implementação
- Seguir `context/coding-standards.md` (logger com prefixo, `report_issue` para falhas visíveis).
- Sem dead code; comentários apenas para o "porquê".

## 4. Testes
- Teste em `test/` reproduzindo o cenário (falhar antes, passar depois).
- `.venv\Scripts\python -m unittest discover -s test`
- Build `dist\Rose` e validação in-game descrita (fase, ação, linha de log esperada).

## 5. Registro
- Decisão arquitetural → `decisions/adr-NNN-*.md`.
- Atualizar `plans/current-sprint.md`.

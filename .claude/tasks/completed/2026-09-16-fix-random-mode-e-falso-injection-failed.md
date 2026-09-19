---
created: 2026-09-16
completed: 2026-09-16
---

# Fix: random mode ignorando seleção de chroma + falso INJECTION FAILED

## Resultado
- Causa 1: seleção de chroma não cancelava random mode → skin sorteada injetada no lugar da escolhida (ADR-001).
- Causa 2: `runoverlay` encerrado pelo cleanup saía com 15 e era logado como falha (ADR-002).
- Testes: `test/test_injection_selection_regressions.py` (6), red → green; validação com `mod-tools.exe` real (15 → 0).
- Build local `dist\Rose\Rose.exe` gerado (Python 3.12, Pengu assinado — ADR-003).

## Pendências
- Validação in-game A–D e commit → `plans/current-sprint.md`.

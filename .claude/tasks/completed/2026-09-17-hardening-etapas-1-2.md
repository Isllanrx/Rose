---
created: 2026-09-17
completed: 2026-09-17
---

# Hardening de produção — etapas 1 e 2 + commits e merge

## Resultado
- Etapa 1 (ADR-007): cleanup retoma jogo suspenso e isola etapas; `threading.excepthook` loga CRITICAL; diálogo nativo da DLL compara IDOK; removidas 3 funções com nomes indefinidos em `resolution_utils`.
- Etapa 2 (ADR-006): `atomic_file` (troca atômica + retry em `PermissionError`, `fsync` opcional); histórico com lock; config ilegível não é sobrescrito; sync de skins com SHA fixado antes do download, gravado só sem falhas, extração atômica e bloqueio de caminhos fora da pasta; `is_safe_path` por componentes.
- `_route_logger` preserva TRACE em modo debug.
- Old vs new: 12 + 22 + 1 testes novos; no old falhavam 9, 12 e 1. Suíte final: 107 (`test/`) + 5 (`analytics/tests`) verdes.
- Efeito colateral encontrado e corrigido antes do commit: `fsync` por arquivo deixaria o sync completo ~110 s mais lento; extração final ~5–10% mais lenta.
- In-game (build de teste): partida normal e Rift Clássico com `INJECTION COMPLETED`, histórico salvo, sem ERROR.
- Commits (convencionais, sem co-autor) em `fix/prod-hardening`, cada um validado isoladamente (compila, importa, suítes existentes verdes); os 13 commits anteriores do `main` também validados; merge fast-forward no `main` (`45b24701`, 21 à frente de `origin/main`).
- Build final `dist\Rose\Rose.exe` a partir do `main`, com Pengu/DLL/hashes idênticos aos instalados.

## Pendências
- Teste C (fechar pela bandeja em partida) e abertura do PR → `plans/backlog.md` #1–#2.
- Etapa 3 e confiança no Windows → backlog #3–#12.

# ADR-010 — Pipeline de CI endurecido para não quebrar produção no merge

- **Status:** aceito. Em 2026-09-19 o usuário ativou Code security (dependency graph, Dependabot, CodeQL via workflow) e **decidiu não criar o ruleset por enquanto** (único contribuidor). Enquanto isso o CI só avisa: conferir a última execução verde na `dev` antes de promover para a `main`. Criar o ruleset quando houver outro contribuidor ou PR externo.
- **Data:** 2026-09-19
- **Amplia:** ADR-009

## Contexto
A ADR-009 criou um job único (lint, testes, catraca). Para um app desktop que se distribui como
`.exe`, os erros que já chegaram ao usuário não eram de lint: build quebrado (`websocket_client`,
workarounds de MSBuild), arquivo faltando no `_internal` (#66, "Failed to start embedded python
interpreter"), plugin JS que só falha dentro do cliente do LoL, dependência vulnerável (26
advisories em Pillow/urllib3/requests, #77) e o próprio workflow como vetor de ataque
(ações com tag mutável, caso tj-actions).

Referências 2026: pin por SHA + Dependabot com comentário de versão, `permissions` mínimas,
`persist-credentials: false`, zizmor/actionlint, pip-audit + dependency-review, `merge_group`
para merge queue, rulesets com checks obrigatórios.

## Decisão
`.github/workflows/ci.yml` (push/PR em `dev`/`main`, `merge_group`), cada job é um check:

| Job | Barra quando |
|---|---|
| Workflow security | actionlint acha erro de sintaxe/expressão; zizmor acha ação sem pin, permissão larga, injeção, cooldown ausente |
| Pengu plugins | algum `.js` rastreado dos plugins não parseia (`node --check`, Node 24) |
| Python | regra Ruff bloqueante, teste unitário (inclui guarda ADR-008) ou catraca (mypy/dívida Ruff sobe) |
| Dependency audit | vulnerabilidade nova fora de `.github/pip-audit-ignore.txt` |
| Dependency review | PR introduz dependência com severidade ≥ moderate |
| Build | `scripts/build_pyinstaller.py` falha, ou `scripts/verify_build.py --fresh-build` não acha `python312.dll`/`base_library.zip`/assets/Pengu/mod-tools, módulo-chave fora do PYZ, ou `cslol-dll.dll` empacotada |

`codeql.yml`: Python e JavaScript (plugins), em push/PR e semanal.
`dependabot.yml`: actions e pip, semanal, alvo `dev`, cooldown de 7 dias, agrupado.
Todas as actions fixadas por SHA com `# vX` (checkout v7.0.1, setup-python v7.0.0,
setup-node v7.0.0, dependency-review v5.0.0, codeql v4.38.1).

## Alternativas consideradas
- **Rodar o `Rose.exe` no CI**: exige admin (UAC), bandeja e cliente do LoL; verificação estrutural
  do build pega as falhas reais sem isso.
- **pip-audit bloqueando tudo**: travaria agora (26 advisories); a lista de exceções amarrada ao #77
  só pode encolher.
- **Harden-runner / egress**: útil, mas mais um terceiro no pipeline; reavaliar quando o GitHub
  entregar o firewall de egress nativo (roadmap 2026).

## Passo manual (GitHub, feito pelo dono do repositório)
Settings → Rules → Rulesets → New branch ruleset, alvo `dev` e `main`:
1. Require a pull request before merging (em `main` também exigir aprovação).
2. Require status checks to pass: `Workflow security (zizmor, actionlint)`, `Pengu plugins (JS syntax)`,
   `Python (lint, tests, quality ratchet)`, `Dependency audit (pip-audit)`, `Build (PyInstaller smoke)`,
   `CodeQL (python)`, `CodeQL (javascript-typescript)`; marcar "require branches to be up to date".
3. Block force pushes; restrict deletions.
4. Opcional: Require merge queue (o workflow já escuta `merge_group`).
Sem isso o CI só avisa; não impede o merge.

## Consequências
- Validação local: actionlint e zizmor sem achados; `node --check` nos 19 arquivos de plugin;
  pip-audit passa com as 26 exceções e falha ao remover uma; `verify_build.py` passa no build real e
  acusa a DLL copiada à mão com `--fresh-build`; build completo num clone limpo sem os workarounds. **O job de build já pagou o custo na validação:** num clone limpo o Pengu quebrava com `MSB3644` porque `/t:Restore,Build` restaura e compila na mesma avaliação; só funcionava localmente por causa de um `obj/` antigo. Corrigido com `/restore` (branch `fix/build-without-workarounds`).
- Tempo: o job de build é o mais lento (~minutos, `needs: python`).
- O que não cobre: comportamento in-game (continua manual, `plans/estrategia-de-testes.md`).

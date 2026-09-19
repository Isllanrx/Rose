# Roadmap — Rose

Visão de longo prazo (não é sprint).

## Confiabilidade da injeção
- Logs sem falsos positivos: todo ERROR deve indicar ação necessária (shutdown, cliente fechado e retries não são erro).
- Detectar crash do jogo pós-injeção (fase `Reconnect` + `last_crash`) e associar à skin injetada.
- Sinalizar ao usuário skins conhecidas como incompatíveis com o patch atual em vez de injetá-las silenciosamente.

## Build e distribuição
- Build local reproduzível sem ajustes manuais (Python 3.12, MSBuild/.NET, binários assinados do Pengu).
- CI no GitHub Actions (Node 24 nos runners, `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`) rodando `test/` e o build PyInstaller.

## Confiança no Windows
- Nenhum binário ou script executado com privilégio de administrador a partir de pasta gravável por usuário comum.
- Updates verificados por assinatura Authenticode do publisher antes de instalar.
- Todos os PE distribuídos assinados e com VERSIONINFO; reputação SmartScreen com certificado estável.

## Qualidade
- Ampliar cobertura de testes para `SkinNameResolver`, handlers de ChampSelect e ciclo de vida do overlay.
- Reduzir estado mutável compartilhado em `SharedState` com transições centralizadas por modo (random/historic/custom mod).

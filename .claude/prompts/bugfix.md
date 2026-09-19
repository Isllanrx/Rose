# Checklist — Bugfix (Rose)

Processo detalhado: skill `systematic-debugging` (`.claude/skills/systematic-debugging/SKILL.md`).

## Coleta
- [ ] `rose_*.log` e `log_updater_*.log` da sessão (`%LOCALAPPDATA%\Rose\logs`)
- [ ] Se o jogo caiu: `<League>\Logs\GameLogs\<ts>\*_r3dlog.txt` e `GameCrashes\last_crash`
- [ ] Se Pengu não ativou: evento CodeIntegrity (3033/3077) e assinatura dos binários
- [ ] Versão do Rose (`APP_VERSION`) e do jogo (`Build Version` no r3dlog)

## Diagnóstico
- [ ] Linha do tempo filtrada (fases, INJECT, RANDOM/HISTORIC/CHROMA, mkoverlay/runoverlay, ERROR)
- [ ] Cada ERROR classificado como causa, consequência ou ruído (tabela de falsos positivos na skill)
- [ ] Mensagem localizada no código (`file:line`) e todos os escritores do estado envolvido identificados
- [ ] Sessão de controle que funcionou comparada
- [ ] `git log -S` para regressão vs. lacuna de design
- [ ] Descartar causa externa: skin desatualizada upstream, Smart App Control, cliente fechado

## Correção
- [ ] Teste que falha sem a correção
- [ ] Correção mínima cobrindo todos os caminhos de entrada
- [ ] Testes verdes + imports do módulo alterado ok
- [ ] Validação com binário real quando envolver `mod-tools`/processos
- [ ] ADR se a correção muda regra de negócio; atualizar `context/business-rules.md`

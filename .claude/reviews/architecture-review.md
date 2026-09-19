# Architecture Review — Rose

- **Data:** 2026-09-16 (atualizado 2026-09-17)
- **Escopo:** fluxo de seleção → injeção → overlay, observado a partir de incidentes reais (logs de 16-09-2026)

## Pontos fortes
- Separação clara launcher / runtime / injeção / integração com cliente.
- Extração segura de arquivos e validação de hash da DLL.
- Pausa do processo do jogo garante que o overlay é aplicado antes do carregamento.
- Logs detalhados por domínio permitem reconstruir a linha do tempo de uma partida.

Auditorias detalhadas com status por achado: `reviews/2026-09-17-auditorias.md`.

## Riscos e dívidas
| Risco | Impacto | Evidência | Encaminhamento |
|---|---|---|---|
| `SharedState` mutável sem transições centralizadas entre modos (random/historic/custom mod/seleção) | Regras de prioridade quebram quando um novo caminho de entrada não reseta o modo | ADR-001 | Centralizar transições de modo; ampliar testes do resolver |
| Caminhos duplicados de seleção de chroma (ChromaSelector vs fallback) | Correções aplicadas em um caminho não chegam ao outro | ADR-001 | Unificar em um único handler |
| Resultado do overlay baseado apenas em exit code | Falsos positivos/negativos de falha | ADR-002 | Manter flag de parada intencional; considerar enum de resultado |
| Sem detecção de crash do jogo pós-injeção | Skin incompatível parece "funcionar" no log do Rose (`INJECTION COMPLETED`) | Skin 21069, patch 16.18 | Backlog #7 |
| Build depende de ambiente não documentado | Builds locais falham ou geram binários bloqueados | ADR-003 | Backlog #5, #6, #9 |
| Ruído de log em ERROR/WARNING | Dificulta diagnóstico | Lockfile retries, Pengu restart no cleanup | Backlog #3, #4 |
| Sem CI | Regressões só aparecem em uso real | — | Roadmap |
| Jogo suspenso depende de todos os caminhos chamarem resume (monitor, custom mod, Swiftplay) | Jogo congelado até auto-resume ou até fechar o Rose | Review 2026-09-17 (`prod-risk-review`) | Shutdown coberto (ADR-007); demais caminhos backlog #9–#11 |
| Rose elevado executa binários/scripts de pastas graváveis pelo usuário (Pengu em AppData, update staging) | Escalonamento de privilégio; heurística de antivírus | Review 2026-09-17 (`windows-trust-review`) | Backlog #3–#8 |
| Persistência sem atomicidade | Perda de config/histórico, skins corrompidas permanentes | Review 2026-09-17 | Corrigido (ADR-006) |

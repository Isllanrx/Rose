---
updated: 2026-09-19
origem: lista de tipos de teste enviada pelo usuário (modelo fullstack/Supabase), filtrada para o Rose
status: planejado, não executar ainda (backlog #78)
---

# Estratégia de testes — o que se aplica ao Rose

Rose = app desktop Windows (Python + PyInstaller), plugins JS dentro do cliente do LoL (Pengu),
falando com a API local do cliente (LCU), com o jogo (mod-tools/cs-lol) e com GitHub/relay.
Sem banco, sem backend HTTP próprio, sem login.

## Aplica — com o que já existe e o que falta

| Tipo | No Rose significa | Hoje | Falta |
|---|---|---|---|
| Unitário | funções puras: resolver de skin, IDs do Clássico, builder de mod, parser WAD | 213 testes | cobrir `skin_processor`, `lcu/data/utils.compute_locked` |
| Integração | Python ↔ LCU (mock de sessão/eventos), Python ↔ plugins (bridge WS), injector ↔ mod-tools | parcial (testes pesados com processos reais) | harness de eventos gravados do LCU (`classico-diag-tools/lcu_events_*.log`) reproduzindo uma champ select inteira |
| Contrato (API/consumidor) | formato das respostas do LCU (`/lol-champ-select/v1/session`, skins, inventário) e das mensagens JS↔Py (`skin`, `chroma-log`, `phase-change`...) | nenhum | fixtures JSON reais + schema; teste falha se o campo usado sumir. Plugin JS e Python validam o mesmo schema |
| Regressão | todo bug corrigido ganha teste que falha no código antigo | prática adotada (ADR-005/008, #25, #64, #68) | manter |
| Smoke | o `.exe` gerado tem os arquivos e módulos certos; plugins JS parseiam | manual | job de build no CI (#79) + `node --check` nos plugins |
| Sanity / aceitação (UAT) | roteiro in-game curto por release: normal, ARAM, Clássico com outro jogador, custom mod, fechar Rose em partida | roteiros em `tasks/completed/*validacao-in-game*` | checklist fixo em `prompts/` para toda release |
| E2E | seleção → injeção → skin no jogo | só manual, com monitor LCU + plugin DiagJade | não automatizável sem o cliente; manter manual guiado |
| Concorrência / race | `SharedState` entre threads, ticker vs WS, `lifecycle_manager` (#65), monitor suspenso | parcial (GameMonitor) | testes com threads e barreiras para #65, lock vs título (#68) |
| Idempotência | gatilho de injeção chamado N vezes, cleanup repetido, sync de skins reexecutado | parcial | teste explícito de dupla injeção e cleanup duplo |
| Serialização | `config.ini`, histórico, manifests de mod, cache de personagens Jade, baseline | parcial | JSON/INI corrompido cai no padrão **com log** |
| Persistência | escrita atômica (ADR-006) | coberta | — |
| Configuração | `config.ini` inválido, caminho do jogo inexistente, env ausente | pouca | casos de #67 (caminho não detectado) e #70 (modo de log) |
| Logging | nenhum `except` silencioso; mensagens-chave presentes | guarda ADR-008 + testes de log | testes do #70 (nível por modo) |
| Timeout / retry / fallback | LCU offline, WS recusando, download falhando, relay caído | parcial | backoff do WS, retry do downloader com falha parcial |
| Falha controlada | jogo nunca fica suspenso; mod incompatível recusado sem crash | GameMonitor, #44 | ligar #44 à injeção com teste |
| Build / CI | build do PyInstaller, workflow válido e seguro | testes dos scripts de build | job de build + zizmor/actionlint (#79) |
| Segurança aplicável | "upload malicioso" = `.fantome`/zip com path traversal; "XSS/CSRF" = origem e caminhos do servidor HTTP/WS local do Pengu | `safe_extract`, `is_loopback_origin`, `_is_safe_path` | testes de zip malicioso e origem não-loopback; DLL do cs-lol (#75) |
| Performance | `mkoverlay` frio/quente (#13), CPU do ticker, memória do download de hashes | medições pontuais | benchmark repetível nos testes pesados, com limite |
| Fluxo crítico / jornada | lock → título → resolver → gatilho → overlay → skin no jogo | coberto por partes | teste de fluxo com eventos gravados (mesmo harness da integração) |
| Edge cases | skin padrão, possuída, chroma, campeão trocado, Clássico sem árvore Jade, IDs deslocados | vários | tabela de casos por modo |

## Não se aplica
Supabase/Postgres (persistência CRUD, FKs, constraints, migrations, RLS, multi-tenancy, transações,
triggers), autenticação/autorização JWT/RBAC, SQL injection, DTO/class-validator, controllers/
interceptors HTTP, validação de formulário Zod, a11y e cross-browser (a UI roda dentro do cliente do
LoL), geração de PDF, relatórios/KPIs, tracing distribuído, métricas/alertas de servidor, carga/
stress/spike/soak/throughput/latência de API, deploy/rollback de servidor, SLA/SLO.

## Ordem sugerida
1. Contrato LCU + mensagens JS↔Py (maior risco: a Riot muda o cliente sem aviso).
2. Harness de integração com eventos gravados (destrava fluxo crítico, E2E parcial e #68).
3. Concorrência (#65) e idempotência do gatilho.
4. Checklist de aceitação por release.

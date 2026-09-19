---
updated: 2026-09-19
base: dev ce265ee4 (após ADR-008)
escopo: git ls-files *.py fora de .claude/ vendor/ test/ testes_Pesados/ scripts/ e workers
---

# Checklist de falhas silenciosas — análise do projeto inteiro

Método: Ruff (~50 regras mapeadas para os itens), buscas no código e leitura do contexto de
cada ocorrência de baixa contagem. "Falso positivo" = lido e confirmado correto.

## Zero ocorrências (medido)
`except:`/`except Exception: pass` sem justificativa (guarda da ADR-008), `finally` com return
(B012), default mutável (B006/B008), `== None` (E711/E712), `is` com literal (F632),
`raise e` (TRY201), `assert` em produção (S101), `eval`/`exec` (S307/S102), `pickle` (S301),
`shell=True` (S602/S605), `requests` sem timeout (S113), `create_task` sem referência (RUF006),
closure em loop (B023), `warnings.filterwarnings`, `__del__`, `if False`, `setdefault`,
`defaultdict`, `NotImplementedError`, `TODO/FIXME/HACK`, monkey patching de módulo.

## Falsos positivos (lidos)
| Achado | Por que está correto |
|---|---|
| `except BaseException` (2): `wad_index.py:256`, `atomic_file.py:63` | limpam recurso e relançam |
| 4 `requests.*` | todos com `timeout` e `raise_for_status()` |
| `subprocess.run` sem `check` (4) | todos verificam `returncode` logo depois |
| S110 (32) | são os `# silent-ok` da ADR-008; o Ruff não lê o marcador |
| S603/S607 (29) | comandos fixos (`explorer`, `tasklist`, `schtasks`), sem input externo |
| S104 bind 0.0.0.0 (5) | party UDP/STUN precisa escutar em todas as interfaces |

## Achados reais
| # | Item do checklist | Ocorrências | Severidade | Onde |
|---|---|---|---|---|
| A | Log de erro sem stack trace (`log.error(f"...{e}")`) | 194 (TRY400) | médio | message_handler 36, initialization 14, game_monitor 11, lifecycle_manager 10, injection_trigger 9 |
| B | Sem CI; versão de Python e dependências não verificadas | — | médio | não há `.github/workflows`; só `requirements.txt` |
| C | `open()` sem `with` e/ou sem `encoding` | 10 + 10 | baixo | `main/core/lockfile.py` (a maioria intencional: handle do lock mantido aberto), `hash_updater`, `hashes_downloader`, `console.py` |
| D | `raise` sem `from` dentro de `except` | 6 | baixo | `lockfile.py:54`, party (`token_codec` 3, `message_types`, `party_manager`) |
| E | `print()` em produção | 22 | baixo | a maioria em logging/console antes do logger existir |
| F | Estado global mutável (`global`) | 23 | baixo | caches e singletons; ADR-007 cobre shutdown |
| G | `errors="ignore"` | 6 | baixo | leitura/escrita de log em `issue_reporter` e diagnóstico; aceitável para texto de log |
| H | `# noqa` (39) e `# type: ignore` (12, 4 sem código) | — | baixo | revisar se escondem algo real |
| I | `datetime` naive | 4 | baixo | timestamps locais de log; intencional |
| J | `zip()` sem `strict` | 2 | baixo | `stun_client.py:173`, `smart_skin_downloader.py:136` |
| K | `sys.path.insert` | 1 | baixo | `main.py:16`, bootstrap de dev |
| L | Código comentado | 18 (ERA001) | baixo | limpeza |

## Não verificável por ferramenta (exige leitura caso a caso)
`dict.get()`/`getattr(..., default)` mascarando ausência, `or 0`/`or ""` (25) com 0 válido,
`if value:` com 0 válido. Amostra lida: IDs do LCU usam 0 como "nenhum" por contrato, então
`or 0` é correto nesses casos. Sem prova para o conjunto; tratar em review de cada arquivo tocado.

## Não se aplica ao Rose
SQL/transações/rowcount/N+1, pandas, `Decimal`, mensageria/ACK/DLQ, health/readiness check,
migração de schema, percentuais/totais financeiros, circuit breaker, process pools.

## Recomendação
1. **A (TRY400)** por lote, no mesmo padrão da ADR-008: `log.exception`/`exc_info=True` onde o erro
   muda o resultado para o usuário. É o item com maior ganho de diagnóstico.
2. **B**: workflow de CI rodando `unittest` + a guarda da ADR-008 em Python 3.12 (Node 24 nos runners,
   padrão do usuário).
3. C–L só quando o arquivo for tocado por outro motivo.

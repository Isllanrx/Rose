---
created: 2026-09-19
tipo: resumo de resultados
uso: base para a descrição do PR
branch: dev (a29b1f18, 45 commits à frente de main 45b24701)
---

# Resultados — 2026-09-19

Hardening etapa 3, otimização de memória, índice de WADs e classificador de
compatibilidade. Tudo validado por suíte automatizada e por teste in-game.

## Correções de produção

| # | Defeito | Antes | Depois |
|---|---|---|---|
| 12 | Pengu CLI sem timeout travava o shutdown | 2 falhas | 0 |
| 10 | Swiftplay só soltava o jogo no caminho de sucesso | 2 falhas | 0 |
| 9 | `GameMonitor`: resume dentro da guarda errada, `start()` sem `join`, corrida no processo suspenso | 3 falhas | 0 |
| — | **Suíte pesada total** | **7 falhas / 14** | **0** |

Validado com worktree no código antigo: cada teste novo falha antes e passa depois.

## Otimização

| # | Item | Antes | Depois | Ganho |
|---|---|---|---|---|
| 48 | Pico de RAM no download da tabela de hashes | 692 MB alocados | 2,1 MB | **330×** |
| 45 | Consulta "esse caminho existe no jogo?" | 0,39 s (varredura linear) | 3,6 µs (índice de 6,4 MB) | **104×** |
| 45 | Construção do índice | não existia | 0,94 s, 802.652 entradas, 392 WADs | — |

O streaming produz saída **byte a byte idêntica**: SHA-256 igual em 230.694.084 bytes.
Ganho extra: escrita via `atomic_write`, então uma parte que falha no meio do download
não deixa mais tabela truncada.

## Defeitos encontrados pela revisão de risco de produção

| Defeito | Antes | Depois |
|---|---|---|
| Índice reconstruído a cada call site de `initialize_when_ready` | até 3 reconstruções (392 WADs cada) | 1 por sessão |
| `mmap` vazava se `WadIndex` falhasse ao construir | índice congelado num patch para sempre, sem log | fechado em qualquer erro |
| Download truncado aceito como completo | tabela quebrada **e** SHA salvo como sucesso | recusado via `Content-Length` |

Dos 11 testes que reproduzem esses defeitos, **8 falham no código anterior**.

## Cobertura de testes

| | Antes | Depois |
|---|---|---|
| Testes unitários | 107 | **187** |
| Testes pesados (processos reais) | 14 | 14 |

Novos: `wad_index` (21), `mod_scanner` (27), fiação do índice (12), achados de risco (11).

## Validação in-game

| Modo | Injeção | `mkoverlay` | Skin em jogo |
|---|---|---|---|
| Practice Tool (cache frio) | `CHROMA_238070` | 44,33 s | — |
| Practice Tool (quente) | `CHROMA_238070` | 2,36 s | confirmada |
| Rift Clássico personalizada | `SKIN_60001009` | 1,84 s | confirmada |
| ARAM | `CHROMA_5058` | 2,63 s | confirmada |
| ARAM (2ª) | `CHROMA_887056` | 1,97 s | confirmada |
| ARAM sem skin | recusada corretamente | — | — |

**5 injeções, 5 sucessos, 0 falhas, 0 traceback, 0 crash de mod, 0 `ERROR` real.**
Também validados: 1 saída abrupta de partida sem resíduo e o fechamento do Rose pela
bandeja durante a partida (Teste C, ADR-007), sem congelar o jogo.

## Descobertas que mudaram o plano

| Achado | Impacto |
|---|---|
| Cache frio × quente: **44,33 s → 2,36 s (18,8×)**, mesma sessão e mesmo mod | #13 é problema da **1ª injeção após o boot**, não de toda injeção — prioridade cai |
| Pré-aquecer lendo TOCs **não funciona**: o índice leu as 392 TOCs 67 s antes e a injeção ainda levou 44,33 s | hipótese do #13 **refutada**; não sai de carona no #45 |
| `lock.acquire(timeout=0.001)` em `ui/core/lifecycle_manager.py:173` | #65 — o caminho sem exclusão mútua é a regra, não a exceção: 12× em 15 min |
| Metade das entradas WAD é zstd chunked, que o `WadReader` nunca leu (227 de 445 medidas) | #62 — o scanner inspeciona menos de metade de um mod de conteúdo |
| `Rose.exe` roda de pasta excluída do Defender | nenhum teste local prova nada sobre falso positivo |

## Segurança e confiança no Windows

Revisado com a skill `windows-trust-review`.

| Verificação | Resultado |
|---|---|
| Primitivas de risco novas no diff (`subprocess`, `winreg`, `SetFileAttributes`, `ctypes`, `OpenProcess`, `VirtualAlloc`, `WriteProcessMemory`) | **nenhuma** — único casamento foi `except subprocess.TimeoutExpired`, um handler |
| Assinaturas e metadados | inalterados (`Rose.exe` segue sem assinatura — backlog #4, pré-existente) |
| Superfície do Vanguard | inalterada — o novo código só **lê** arquivos do disco, sem handle nem memória do processo do jogo |
| Comportamento novo | thread de background lendo ~29 MB (cabeçalho + TOC de 392 WADs), somente leitura, na pasta do jogo |

Ponto a favor: o streaming **eliminou** um pico de alocação de ~940 MB, que é um padrão
pior para heurística comportamental do que ler 29 MB.

**Ressalva:** o teste local não produz evidência de antivírus, porque o `Rose.exe` roda de
`C:\Projetos_Pessoais`, que está na lista de exclusão do Defender. Evidência real exigiria
rodar de fora das exclusões ou em VM limpa.

## Novos itens de backlog

**#48–#65**, dos quais **#44, #45 e #50 já foram entregues**. Os demais cobrem padrão
2026, biblioteca de skins vazia, `.gitattributes`, suporte a WAD tipo 4, o lock da UI,
ruído de log e a UX da instalação.

## Pendente

- Reuso do índice entre sessões (exige reiniciar o Rose uma vez).
- `monitor_auto_resume_timeout` 60 s → 120 s: a 1ª injeção do dia passou com 15,7 s de folga.
- Ligar `mod_scanner` à injeção — muda comportamento (recusa antes de suspender o jogo),
  e ele **não entra no build** enquanto não tiver call site.
- #28/#29: troca na bancada da ARAM, sem cobertura de teste nem in-game.
- #49: biblioteca de skins vazia mantém 5 testes pulando.

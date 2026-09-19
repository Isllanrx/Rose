---
created: 2026-09-16
status: concluida
updated: 2026-09-19
---

# Validação in-game (build `dist\Rose`)

Abrir `dist\Rose\Rose.exe` como administrador (Rose instalado fechado). Evitar skin 21069.

## Partida normal
| Teste | Passos | Log esperado | Status |
|---|---|---|---|
| A | Travar campeão → dado → escolher outra skin/chroma | `[RANDOM] Random mode DISABLED due to chroma selection` + injeção da escolhida | reportado ok pelo usuário; não aparece no log de 2026-09-17 |
| B | Travar campeão → dado → não mexer | `[RANDOM] Injecting random skin` + `INJECTION COMPLETED` | reportado ok pelo usuário; não aparece no log de 2026-09-17 |
| C | Em partida, fechar Rose pela bandeja | `runoverlay stopped by Rose`, sem `INJECTION FAILED`; jogo continua rodando (ADR-007) | **ok (2026-09-19)** — com skin injetada, fechado pela barra de tarefas durante a partida: jogo seguiu normal, sem crash |
| D | Partida completa | `INJECTION COMPLETED` + `Game ended, stopping overlay process` | **ok (log 2026-09-17 01:45, build do main)** |

## Rift Clássico (personalizada, fila 3262)
Skins de Katarina disponíveis na árvore Jade e na biblioteca: 55001, 55009, 55029, 55047, 55048.

| Teste | Passos | Log esperado | Status |
|---|---|---|---|
| E | Annie Gótica (60001001) | `[CLASSIC] Prepared Annie skin 1 for ['jade_annie', 'jade_annie_tibbers']` → skin e Tibbers visíveis | **ok (21:39); repetido ok em 2026-09-17 01:46** |
| F | Subtítulo do card bloqueado | "Habilitada" em vez de "Desabilitada" | reportado ok pelo usuário |
| F2 | Skin exclusiva/chroma do Clássico ou Lee Sin 60064040 | `[CLASSIC] Prepared ...` (antes era recusada) | reportado ok pelo usuário |
| G | Conferir no r3dlog/Live Client API o `skinID` carregado | 0, 301 ou 302 (todos cobertos) | **ok: SkinID(0)** |

## Launcher / erros silenciosos
| Teste | Log esperado | Status |
|---|---|---|
| H | `log_updater_*.log` passa a conter `Remote skin SHA` / `Downloading skins from repository ZIP` | **ok (`Remote skin SHA: f52a5346`, 2026-09-17 01:41)** |

## Fechamento (2026-09-19)

Todos os cenarios executados. O Teste C, ultimo pendente, validou o caminho que a
etapa 3 do hardening alterou (#9 GameMonitor, #10 Swiftplay, #12 Pengu CLI): com
skin injetada e partida em andamento, fechar o Rose pela barra de tarefas deixa o
jogo rodando normalmente, sem crash. E o comportamento que a ADR-007 define.

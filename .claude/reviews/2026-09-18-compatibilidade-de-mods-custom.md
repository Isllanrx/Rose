# Investigação — compatibilidade de mods custom entre patches (2026-09-18)

Pergunta de origem: por que um `.fantome` do Runeforge para de funcionar quando a Riot lança um
patch, e dá para o Rose consertar isso sozinho?

Ambiente: patch instalado **16.18** (`16.18.8175716+branch.releases-16-18`), biblioteca do Rose com
8.995 `.fantome`.

## 1. Como o jogo trata skins — duas camadas

- **Cliente (LCU)**: a skin é um inteiro (`id: 1001`) mais um `contentId` GUID. Estável entre
  patches; a seleção do Rose nunca quebra por isso.
- **Jogo (WAD/BIN)**: onde os dados moram e onde tudo quebra.

O patcher usa content-defined chunking: `Game.db` (SQLite) lista 402 arquivos e **1.082.570 chunks**
(alvo 250 KB); `Game.manifest` é RMAN v2 em zstd. Os WADs são reescritos a cada patch.

## 2. A quebra não é hash

Nenhum hash de caminho muda entre patches — `xxhash64(path.lower())` é determinístico. No mod de
teste, 256 das 580 entradas ainda casam com o jogo e as outras 324 são assets novos do autor.

A causa é **link pendurado**: a Riot deduplicou os dados de skin, esvaziando `Skins/SkinN.bin` e
movendo o conteúdo para `<Char>_Multi_Skins_SkinA_Skins_SkinB_….bin` (5.789 desses caminhos hoje).
O antigo arquivo-base `Skins/Skin-1.bin` foi **removido**, e todo BIN de mod antigo ainda aponta
para ele.

Contado contra **jogo ∪ próprio mod** (contra o jogo apenas, o número infla de 110 para 513):

| Mod | Links | Pendurados |
|---|---|---|
| Spirit Blossom Rift (16.16) | 1228 | **110 (9,0 %)** — 108 são `Skins/Skin-1.bin` |
| Old Summoners Rift V2 (16.18) | 177 | 0 |

## 3. Duas famílias de mod

| | Redirect (LeagueSkins/Rose) | Conteúdo (Runeforge) |
|---|---|---|
| WAD | ~3 KB (mediana), 1 entrada | dezenas a centenas de MB |
| Conteúdo | nenhum — só um link para `Skins/SkinN.bin` do jogo | cópia integral dos BINs e assets |
| Sobrevive a patch | sim | não |

Amostra de 400 mods da biblioteca: **99,5 % são redirect** e todos declaram o patch corrente.
`injection/classic/classic_skin_builder.py::retarget_skin_bin` já produz essa forma resiliente.

Fragilidade correlaciona com a composição do override, não com o tamanho:

| Mod | Override | Composição | Pendurados |
|---|---|---|---|
| WinterRift 2025 (16.18) | 123 | 120 `.tex`, 2 `.bin` | 0 |
| Old SR V2 (16.18) | 1068 | 411 `.scb`, 293 `.anm`, 241 `.tex`, 51 `.bin` | 0 |
| Spirit Blossom (16.16) | 256 | **252 `.bin`** | 9 % |

`.tex/.scb/.anm/.skn/.skl` são conteúdo opaco sem referências — estáveis. `.bin` (PROP) é grafo de
objetos com links, e é a única fonte real de incompatibilidade.

## 4. Validação in-game (a conclusão)

Controle natural na mesma sessão, mesmo mod e mesmo patch:

| Sessão | Overlay aplicado | Resultado |
|---|---|---|
| 21:56:24 | não (`mkoverlay` 97,63 s > auto-resume 60 s) | partida normal, sem crash |
| 22:03:17 | **sim** (`mkoverlay` 4,20 s) | **crash em 2,2 s** |

```
000002.042| ALWAYS|  FLOW| Loading Started
000002.192|  ERROR| ALE-9B39AA45 FATAL ERROR. Missing data: 0x0
000002.194|  ERROR| SentryHandleException
```

Crash no **loading screen**, não no spawn dos minions — o jogo resolve o grafo inteiro ao carregar
o mapa. O `r3dlog` tem 73 linhas e apenas esses dois erros. Falha imediata e determinística, o que
torna a recusa preventiva viável e sem degradação parcial a tolerar.

## 5. Achado colateral — `mkoverlay` e cache de disco

Mesma entrada, duas execuções seguidas: **97,63 s** (frio) e **4,20 s** (quente). A variável
dominante é o cache de disco do WAD do jogo, não o peso do mod — reenquadra o backlog #13.

Na execução fria, `[monitor] Stopping monitor after auto-resume - runoverlay should have hooked`
foi emitida enquanto o `mkoverlay` ainda rodava, afirmando um sucesso que não ocorreu (ADR-005).
O usuário vê apenas "a skin não apareceu", sem erro.

## 6. Prior art — Hematite (RitoShark), Rust, AGPL-3.0 com exceção de dependência

Confirma o diagnóstico de forma independente: `detect/dead_links.rs` afirma "such dead links crash
the client at runtime", e `find_game_multi_skins_bin` reconstrói o nome do combo BIN a partir dos
slots que o **jogo** tem, ordenados lexicograficamente.

Gaps medidos contra o 16.18:

1. `combo_bin_pattern` aceita só slots numéricos (`data/gragas_skins_0_1.bin`) e **rejeita** a forma
   real `data/nexus_skins_skin0_skins_skin1_….bin`. Para `turretrubble` o alvo relocado existe no
   jogo — conserto perdido.
2. Inconsistência interna: `dead_links.rs` reconstrói do jogo (robusto), `combo_relocate.rs` exige
   match exato dos slots do mod. Como a lista muda a cada patch, `nexus` e `inhibitor` não resolvem.
3. O gate `mod_ships_per_skin_bins` desliga a relocação inteira se o mod embarcar qualquer
   `skins/skinN.bin`; o Old SR V2 embarca 45.

**Não utilizável como dependência**: o `hematite-cli.exe` v0.7.0 é não assinado e, nesta máquina,
morre em ~0,1 s com exit 1 e zero saída em qualquer via que chame `run_with_cli` (flags, drag-drop e
menu). Persiste com Smart App Control desligado, Defender off, rede OK e `RUST_BACKTRACE=full` sem
backtrace — não é panic, é terminação abrupta. O dicionário LMDB nunca chega a ser criado. Fica como
**referência de regras** (o `fix_config.toml` e a tabela de 385 pares de migração), não como binário
embarcado.

## 7. Conclusões acionáveis

- Link pendurado é impeditivo absoluto de injeção, verificado em jogo.
- Recusar **antes** de suspender o jogo (ADR-004), com `report_issue` (ADR-005).
- A biblioteca própria não precisa de nada disso — filtrar redirects antes de analisar.
- Resolver links contra **jogo ∪ mod**, nunca só contra o jogo.
- Reconstruir nomes de combo BIN a partir dos slots do jogo instalado dá imunidade a patch.

Método completo e primitivas em `.claude/skills/fantome-compat-rebase/SKILL.md`.

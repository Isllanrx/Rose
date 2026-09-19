---
name: fantome-compat-rebase
description: Diagnostica por que um .fantome (skin/mapa custom do Runeforge) parou de funcionar após um patch do LoL e avalia se dá para rebasear o mod automaticamente contra o jogo instalado. Use quando pedirem "skin desatualizada", "mod parou depois do patch", "crash pós-injeção", "Character record is null", "atualizar mod automaticamente" ou ao projetar a compatibilidade automática de mods.
---

# Compatibilidade de mods entre patches — Rose

Objetivo: dizer, para um `.fantome` específico, **o que exatamente quebrou** entre a versão em que foi publicado e o jogo instalado, e se o conserto é mecanizável pelo Rose.
Fora de escopo: qualidade visual do mod, direitos autorais, UI.

## Modelo mental

Um `.fantome` é um ZIP com `META/Info.json` (campo `Version` = patch de publicação) e `WAD/*.wad.client`.
`mod-tools mkoverlay` **não** casa o WAD do mod pelo nome — ele indexa os WADs de `--game:` por hash de caminho (xxhash64 do path minúsculo) e distribui cada entrada do mod para o WAD do jogo que contém aquele hash. Entradas com hash desconhecido são adicionadas como assets novos.

Consequência: cada entrada do mod é uma **substituição de arquivo inteiro**, não um patch. Se o patch do LoL mudou aquele arquivo, o conteúdo novo é perdido silenciosamente.

## Classificação das entradas do mod

Para cada entrada do WAD do mod, classificar em uma de quatro:

| Classe | Como detectar | Risco |
|---|---|---|
| **Asset novo** | hash não existe em nenhum WAD do jogo | nenhum — o mod só adiciona |
| **Override idêntico** | existe no jogo e é byte-a-byte igual | nenhum |
| **Override divergente de conteúdo** | existe, difere, mas o esquema do bin bate | médio — perde o que o patch adicionou |
| **Override de esquema quebrado** | existe, difere, e a estrutura do bin do jogo mudou de forma | **alto — crash** |

O quarto caso é o que gera `Character record is null` no spawn.

## Procedimento

1. **Metadados**: ler `META/Info.json` → `Version`. Comparar com o patch instalado
   (`<League>\Game\DATA\FINAL\Maps\Shipping\*.wad.client` + `hashes.game.txt` de
   `C:\Program Files\Rose\_internal\injection\tools\`).
2. **TOC do WAD do mod**: header WAD v3 = 272 bytes, contagem em `<I` no offset 268, entradas de 32 bytes
   (`<QIIIB` = hash, offset, comprimido, descomprimido, tipo&0x0F; 0=raw, 1/2=gzip, 3=zstd).
   Reaproveitar `WadReader` de `injection/classic/classic_skin_builder.py`.
3. **Cruzar** os hashes do mod com o TOC de cada `*.wad.client` do jogo → separar asset novo × override.
4. **Resolver** os hashes em caminhos via `hashes.game.txt` (só os do mod; a tabela tem 220 MB, não carregar inteira).
5. **Comparar bin a bin** com `_parse_prop_entries`: versão PROP, **lista de links**, chaves e class hashes.
   A lista de links é o sinal mais forte de mudança de esquema.
6. **Concluir** com contagem por classe + os caminhos de maior risco.

## Sintoma confirmado in-game

Um mod com link pendurado derruba o jogo **no loading screen**, ~150 ms após `Loading Started`:

```
000002.192|  ERROR| ALE-9B39AA45 FATAL ERROR. Missing data: 0x0
000002.194|  ERROR| SentryHandleException
```

Não é no spawn — o jogo resolve o grafo de dados inteiro ao carregar o mapa. Validado em
2026-09-18 (patch 16.18) com controle natural na mesma sessão: overlay atrasado (mod não aplicado)
→ partida normal; overlay aplicado → crash em 2,2 s. Mesmo mod, mesma máquina, mesmo patch.

Consequência de projeto: a falha é imediata e determinística, então **recusar antes de injetar é
seguro** e não existe degradação parcial a tolerar. `Character record is null` (glossário) é o
sintoma irmão, no spawn, para incompatibilidade de dados de personagem.

## Duas famílias de mod — a distinção que decide tudo

| | **Redirect** (LeagueSkins / Rose) | **Conteúdo** (Runeforge) |
|---|---|---|
| Tamanho do WAD | ~3 KB (mediana; p90 7 KB) | dezenas de MB |
| Entradas | 1–2 (mediana 1) | centenas |
| O que contém | um PROP mínimo cujo link aponta para `Skins/SkinN.bin` **do jogo** | cópia integral dos bins e assets |
| Onde mora o conteúdo | no jogo instalado, resolvido em runtime | congelado no patch de publicação |
| Sobrevive a patch | sim — o jogo resolve o alvo com os dados novos | não |

Medido: 400 mods amostrados da biblioteca do Rose → 99,5% são redirect e todos declaram o patch corrente.
`injection/classic/classic_skin_builder.py` já produz exatamente a forma redirect (`retarget_skin_bin`) a partir do
jogo instalado — é a prova de que a técnica resiliente já existe no projeto.

Primeira pergunta de todo diagnóstico: **o mod é redirect ou conteúdo?** Só a segunda família precisa de rebase.

## Padrão conhecido — deduplicação `*_Multi_Skins_*` (patch ≥ 16.x)

Riot passou a **esvaziar** os `Skins/SkinN.bin` e mover o conteúdo real para arquivos compartilhados
`<Char>_Multi_Skins_SkinA_Skins_SkinB_….bin`, referenciados pela lista de links.

Sintomas em um mod antigo:
- o `SkinN.bin` do mod é ordens de grandeza **maior** que o do jogo (ex.: 384 KB × 4 KB);
- os links do mod apontam para `Skin-1.bin`/`Animations/SkinN.bin`; os do jogo apontam para vários `_Multi_…`;
- o mod tem dezenas de entradas que o jogo não tem mais nesse arquivo.

Ao sobrescrever o stub, o mod **desliga** os arquivos `_Multi_` — todo o conteúdo que hoje mora neles some.
Pior: o nome desses arquivos embute a lista de skins agrupadas, então **muda a cada patch** que adiciona ou
remove uma skin do grupo. Nenhum caminho hardcoded sobrevive.

### Sinal decisivo — link pendurado para `Skins/Skin-1.bin`

No esquema antigo, `Skin-1.bin` era o arquivo-base compartilhado entre as skins de um personagem.
A deduplicação **removeu** esse arquivo. Todo bin de mod antigo ainda linka para ele.

Verificação direta e barata: extrair a lista de links de cada bin do mod e testar o hash contra o índice
global do jogo instalado. Link que não resolve = o jogo vai procurar um registro de personagem que não existe →
`Character record is null` → crash no spawn.

Medido no `Spirit_Blossom_Rift_by_Moga_v16.16.2.26.0.fantome` contra o patch 16.18:
1.228 links, **513 pendurados**, em 9 alvos distintos — 8 deles `<Char>/Skins/Skin-1.bin` de minions e 1 `Turret/Skins/Skin2.5.bin`.
Nenhum hash de caminho mudou; 256 das 580 entradas ainda existem e as outras 324 são assets novos do autor.

Corolário: a quebra **não é hash remapeado**, é link pendurado por remoção de arquivo.
Um mod publicado antes dessa mudança não pode ser consertado remapeando hashes.

## Fragilidade por tipo de arquivo sobrescrito

Medido em três mods de mapa contra o patch 16.18:

| Mod | Entradas | Override | Assets novos | Composição do override | Links pendurados |
|---|---|---|---|---|---|
| WinterRift 2025 (16.18) | 241 | 123 | 118 | 120 `.tex`, 2 `.bin`, 1 `.mapgeo` | 0 |
| Old Summoners Rift V2 (16.18) | 3139 | 1068 | 2071 | 411 `.scb`, 293 `.anm`, 241 `.tex`, 51 `.bin`, 28 `.skn`/`.skl` | 0 % |
| Spirit Blossom Rift (16.16) | 580 | 256 | 324 | **252 `.bin`**, 4 `.tex` | **9 %** |

A regra que sai daí:

- `.tex`, `.scb`, `.anm`, `.skn`, `.skl`, `.dds`, `.mapgeo` — conteúdo opaco, sem referências a outros arquivos.
  Substituir é estável entre patches; o formato praticamente não muda.
- `.bin` (PROP) — grafo de objetos com lista de links e class hashes. Substituir **congela a estrutura**
  no patch de publicação e é a única fonte real de incompatibilidade.

**Índice de risco de um mod** = fração de `.bin` no conjunto de override × taxa de link pendurado.
O Spirit Blossom sobrescreve 98 % em `.bin`; os dois mods atualizados sobrescrevem majoritariamente assets opacos.
Um mod pesado em textura é quase imune a patch mesmo com centenas de MB.

### Armadilha de medição

Ao contar links pendurados, resolver contra **jogo ∪ próprio mod**, nunca só contra o jogo — o mod costuma
trazer seus próprios alvos de link como assets novos. Contando só contra o jogo, o Spirit Blossom aparenta
513 links quebrados de 1228; contra o índice combinado são **110 (9 %)**, dos quais 108 são `Skins/Skin-1.bin`.

## Armadilha ao testar in-game

Antes de concluir "o mod é incompatível" a partir de um teste, confirmar que o overlay **chegou a
ser aplicado**. Se `mkoverlay completed in` aparecer depois de `Stopping monitor after auto-resume`
no log do Rose, o mod nunca entrou e o teste não testou nada — o sintoma é "não carregou e não
crashou". Medido: 97,63 s no cache frio contra 4,20 s no quente, mesma entrada.

Um teste válido precisa de: `mkoverlay completed` **sem** linha de auto-resume antes, `runoverlay
started` antes de o processo do jogo iniciar (comparar com o timestamp da pasta em `GameLogs/`),
e `CUSTOM MOD INJECTION COMPLETED`.

## Viabilidade de rebase automático

Rebase = reaplicar a intenção do mod sobre a base nova, não reinstalar o arquivo antigo. Exige um 3-way:

- **base antiga** (o arquivo como era no patch de `Info.json`) — não vem no `.fantome`; precisa de fonte externa
  (CommunityDragon expõe assets extraídos por patch; validar cobertura de `.bin` antes de assumir);
- **mod** (o arquivo do `.fantome`);
- **base nova** (lida do jogo instalado com `WadReader`).

Merge por **entrada do PROP**, nunca por arquivo: entrada só no mod → adicionar; só na base nova → preservar;
nas duas → o mod vence se diferir da base antiga, senão a base nova vence. Conflito real → recusar o mod.

Sem a base antiga não há 3-way: diferença entre mod e base nova é ambígua (pode ser edição do autor ou mudança do patch).
Nesse caso o máximo honesto é **detectar e avisar**, não consertar.

## Regras

- Nunca injetar um mod classificado como "esquema quebrado" — recusar e reportar via `report_issue`, seguindo ADR-005.
- Rebase é caro (ler WADs de GBs): fazer fora do caminho que suspende o jogo, como `prepare_classic_mod` já faz (ADR-004).
- Resultado do diagnóstico é cacheável por (hash do `.fantome`, versão do jogo) — invalidar quando o patch mudar.
- WAD/PROP malformado vira `ClassicSkinError`, nunca exceção não tratada na thread de injeção.


## Prior art — Hematite (RitoShark), Rust, AGPL-3.0 com exceção de dependência

Resolve o problema deste documento de forma sob demanda. Confirma o diagnóstico de forma independente:
`detect/dead_links.rs` afirma "such dead links crash the client at runtime" e
`find_game_multi_skins_bin` reconstrói o nome do combo BIN a partir dos slots que o **jogo instalado** tem,
ordenados lexicograficamente — a mesma conclusão a que a medição acima chegou.

Arquitetura relevante: 6 crates, ~24,6 mil linhas, 287 testes, CI Windows com `clippy -D warnings`.
`hematite-core` é puro e fala só com traits (`BinProvider`, `HashProvider`, `WadProvider`, `GameProvider`);
`hematite-live` lê WADs do jogo TOC-only (xxh64 + zstd, equivalente ao `WadReader` do Rose);
`hematite-orchestrate` existe explicitamente para embedders. 20 fixes em `config/fix_config.toml`
(v2.3.5) atualizado do GitHub sem rebuild — entre eles `merge_linked_bins`, `gear_pull`, `cac_pull`,
`entry_validator`, `resolve_dead_refs`, `combo_bin_relocate` e `file_ref_migration` (385 pares string→file hash).
O repath move assets do mod para um prefixo próprio, o que importa ao Rose porque o Clássico injeta dezenas de mods juntos.

### Gaps medidos (verificados contra o patch 16.18)

1. `combo_bin_pattern` aceita apenas slots numéricos (`data/gragas_skins_0_1.bin`). Os combo BINs reais do
   Old SR V2 têm a forma `data/nexus_skins_skin0_skins_skin1_….bin` e são **rejeitados**. Para `turretrubble`
   o caminho relocado existe no jogo — é um conserto perdido.
2. Inconsistência interna: `dead_links.rs` reconstrói o combo BIN a partir do jogo (robusto a patch), enquanto
   `combo_relocate.rs` exige que os slots do mod batam exatamente com os do jogo. Como a lista de slots muda a
   cada patch, `nexus` e `inhibitor` não resolvem — falha em segurança (deixa intacto), mas não conserta.
3. O gate `mod_ships_per_skin_bins` desliga a relocação inteira se o mod embarcar qualquer `skins/skinN.bin`;
   o Old SR V2 embarca 45, então a regra nunca roda nesse mod.

Limitações que os próprios autores declaram em `docs/repath-and-ltk-review.md`: a tabela de migração não é
validada contra o build instalado; a regra de `bnk` é version-only e pode remover bank órfão válido; perda de
chave do ResourceResolver não é coberta — e eles argumentam de propósito que assar dados do resolver dentro do
mod o amarraria a um patch. A validação é sintética; in-game fica fora dos testes.

### O que falta para o uso que o Rose quer

O Hematite roda **sob demanda** (drag-and-drop ou CLI): não tem gatilho por troca de patch, cache por versão do
jogo, nem reparo no momento da injeção. A automação é a parte a construir; o motor de reparo não.

Integração preferida: chamar `hematite-cli.exe --check --json` para classificar e o modo de fix para reparar.
A exceção de licença cobre explicitamente chamar a CLI de uma aplicação fechada, o contrato JSON
(`CheckInfo`: champion, skin_number, is_binless, detected_issues, mais `repath_reports`) já existe, e as regras
se atualizam sozinhas do GitHub. Linkar o crate exigiria FFI Python↔Rust e mudaria o build (ADR-003).

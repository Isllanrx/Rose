# ADR-004 — Rift Clássico: skins geradas a partir dos dados do jogo instalado

- **Status:** aceito (validado in-game em 2026-09-16: Annie Gótica + Tibbers)
- **Data:** 2026-09-16

## Contexto
A fila 3262 "Rift Clássico" (`gameMode=JADE`, mapa 453, partida personalizada) spawna o personagem `Jade_<Alias>` (ex.: `Jade_Katarina`, SkinID 301 confirmado via Live Client Data API). Esse personagem tem árvore própria no WAD do campeão (`data/characters/jade_<alias>/...`, entradas `Characters/Jade_<Alias>/Skins/SkinN`, slots base 0/301/302). Os `.fantome` do Rose sobrescrevem `data/characters/<alias>/skins/skin0.bin`, que o Clássico nunca carrega — a injeção era um no-op silencioso. A árvore Jade espelha só parte das skins normais (Katarina 24 bins de 78; MissFortune 14 de 76).

## Decisão
Em `JADE`, `InjectionManager` chama `SkinInjector.prepare_classic_mod` antes de iniciar o monitor:
1. Resolve o `.fantome` normal da skin e extrai o alias do nome do WAD (`WAD/<Alias>.wad.client`).
2. Lê `jade_<alias>/skins/skinN.bin` do WAD **instalado** (`injection/classic/classic_skin_builder.py`, WAD v3 + zstd).
3. Gera `skin0/301/302.bin` renomeando apenas as chaves `SkinN` e `SkinN/Resources` e linkando `SkinN.bin` — mesma estrutura dos mods da comunidade (verificado byte a byte no `.fantome` 21031).
4. Escreve um mod em pasta (`WAD/<Alias>.wad.client/...`) e segue o fluxo normal `mkoverlay`/`runoverlay`.
Se a skin não existe na árvore Jade, registra `[CLASSIC] ... cannot be shown in Rift Classic` e não suspende o jogo.

## Alternativas consideradas
- **Converter o `.fantome` da comunidade para paths Jade**: exige reescrever bins inteiros (campos, assets, animações) de dados potencialmente desatualizados; alto risco de crash (ver skin 21069).
- **Apenas detectar e bloquear**: seguro, mas não entrega skins no modo.
- **Aproveitar o LeagueSandbox (Lol_2.0)**: emulador de servidor para cliente 4.20 (RAF/inibin, skin escolhida pelo servidor); arquitetura incompatível.

## Revisão 2026-09-16 (análise de escala)
- O nome Jade nem sempre é `Jade_<Alias>` (`MonkeyKing` → `jade_wukong`) e há personagens auxiliares com árvore própria (`jade_annie_tibbers`, `jade_nidaleecougar`, `jade_shyvanadragon`...). O builder passou a usar o índice de personagens `jade_*` extraído do `hashes.game.txt` (varredura 0,74s, cache em `state/classic_characters.json` invalidado por tamanho/mtime) e retargeta todo personagem Jade presente no WAD do campeão que tenha a skin N.
- Endurecimento: alias restrito a `[A-Za-z0-9_]+`, TOC do WAD lido uma vez (`WadReader`), erros de `struct`/zstd/zlib convertidos em `ClassicSkinError`, PROP < v2 recusado, `info.json` via `json.dumps`.
- Cobertura medida no patch 16.18: 67 de 174 campeões têm versão Clássica; 374 de 1945 skins da biblioteca (19,2%) existem nas árvores Jade.

## Revisão 2026-09-16 (teste in-game)
- A tela de seleção do Clássico usa `.skins-pane` (título `.skins-pane__skin-title`, cadeado `.skins-pane__locked-overlay`), capturado com um plugin de diagnóstico temporário. SkinMonitor e ROSE-UI passaram a suportar esses seletores.
- O cliente expõe campeões como `60000 + id` e skins como `60000000 + id`; `SkinInjector.prepare_classic_mod` normaliza antes de resolver o `.fantome`.
- O jogo carregou `Jade_Annie SkinID(0)` após o Rose forçar a skin base `60001000`; o slot 0 gerado exibiu a skin corretamente.

## Revisão 2026-09-16 (validação exaustiva)
- O alias do WAD passou a vir de qualquer arquivo da pasta do campeão na biblioteca (`champion_alias_from_library`), sem exigir o arquivo da skin escolhida. Antes, 40 skins e 61 chromas exclusivos do Clássico (números ≥ 300), e a skin Lee Sin 60064040 ausente da biblioteca, eram recusados sem necessidade.
- Validação contra o catálogo real do cliente e o jogo instalado (patch 16.18): 68/68 campeões, 419/419 skins não-base e 1196/1196 chromas geram mod com chaves corretas; `mkoverlay` real com 68 mods simultâneos (87 personagens, 19 auxiliares) sem slots inválidos; preparo médio 11,7 ms por skin.

## Revisão 2026-09-16 (seleção voltava para a skin padrão)
- Sintoma in-game: perto do fim do timer o carrossel voltava para a skin padrão, embora a skin escolhida carregasse.
- Causa (código do cliente `Plugins/rcp-fe-lol-jade/assets.wad`): o `skins-pane` cria sua própria `DataBinding("/lol-champ-select", getProvider().getSocket())` e observa `/v1/skin-selector-info`. O ROSE-UI só intercepta o socket do `rcp-fe-lol-champ-select`; ao forçar a skin base (`PATCH my-selection 60001000`), o evento chega sem filtro ao Jade e o carrossel reposiciona.
- Decisão: no Clássico o Rose **não força a skin base**. Só skins possuídas podem ser selecionadas nessa tela, então o mod passa a sobrescrever também o slot da skin atualmente selecionada (`selectedSkinId % 1000`), além de 0/301/302. Sem mudança de seleção não há evento, e não é preciso interceptar sockets de outro plugin.
- Alternativa descartada: interceptar `WebSocket.prototype`/o socket do `rcp-fe-lol-jade` — frágil (API interna do plugin) e afeta todos os sockets.

## Consequências
- Dinâmico por patch: dados vêm sempre do jogo instalado; nada a atualizar manualmente quando a Riot mudar o Clássico, desde que o formato WAD v3/PROP se mantenha.
- Só skins presentes na árvore Jade funcionam; as demais são recusadas com log.
- Party skins e mods customizados não são aplicados no Clássico.
- Novas dependências: `xxhash==4.0.1`, `zstandard==0.25.0` (hiddenimports no `Rose.spec`).
- Slot confirmado in-game: após forçar a skin base o jogo carrega `SkinID(0)`; 301/302 continuam cobertos.
- Pendência: seleção de chroma na UI do Clássico (dados já suportados).

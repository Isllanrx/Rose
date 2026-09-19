# Glossário — Rose

| Termo | Significado |
|---|---|
| **LCU** | League Client Update — API REST/WebSocket local do cliente do LoL |
| **Lockfile (LCU)** | Arquivo do cliente com porta/token; "lockfile is not ready" = cliente fechado |
| **Pengu Loader** | Framework que injeta plugins JS no `LeagueClientUx` |
| **Bridge / SkinMonitor** | Servidor HTTP/WS local do Rose (porta 50000+) usado pelos plugins |
| **Phase** | Fases do gameflow: Lobby, Matchmaking, ReadyCheck, ChampSelect, FINALIZATION, GameStart, InProgress, Reconnect, WaitingForStats, EndOfGame |
| **Reconnect** | Fase do cliente quando o processo do jogo cai/reinicia durante a partida |
| **.fantome** | Pacote ZIP de mod (`META/info.json` + `WAD/*.wad.client`) |
| **WAD** | Arquivo de dados do jogo; entradas indexadas por xxhash64 do caminho em minúsculas |
| **.bin (PROP)** | Propriedades do jogo (skin/personagem); campos por hash FNV-1a |
| **mkoverlay / runoverlay** | Comandos do `mod-tools.exe`: montar overlay a partir dos mods / aplicar ao jogo em execução |
| **Overlay** | WADs modificados montados sobre os originais em runtime |
| **hashes.game.txt** | Tabela hash → caminho (CommunityDragon), necessária ao `mkoverlay` |
| **Skin ID** | `championId * 1000 + skinNum` (21069 = Miss Fortune skin 69) |
| **Chroma** | Variação de cor de uma skin, com ID próprio (21070 é chroma da 21069) |
| **Form** | Variante especial de skin (Elementalist Lux, Sahn Uzal Mordekaiser, ...) |
| **Random mode** | Dado que sorteia a skin a injetar |
| **Historic mode** | Reusa a última skin injetada para o campeão |
| **Character record is null** | Erro do jogo no spawn quando dados de skin injetados são incompatíveis com o patch → crash |
| **Missing data: 0x0** | `ALE-… FATAL ERROR` no loading screen quando um BIN injetado referencia arquivo removido pela Riot (link pendurado) → crash em ~2 s |
| **Link pendurado** | Entrada da lista `linked` de um PROP que não resolve em nenhum WAD do jogo nem no próprio mod |
| **`_Multi_Skins_`** | BIN compartilhado entre várias skins de um personagem; substituiu o antigo `Skins/Skin-1.bin`. O nome embute a lista de slots e muda a cada patch |
| **Mod redirect × mod de conteúdo** | Redirect só aponta para dados do jogo (~3 KB, imune a patch); de conteúdo copia BINs/assets (congelado no patch de publicação) |
| **Rift Clássico / JADE** | Fila 3262 (personalizada, mapa 453); `gameMode=JADE` no LCU |
| **Jade_<Campeão>** | Personagem separado usado no Rift Clássico (`jade_annie`, `jade_wukong`), com skins próprias e slots base 0/301/302 |
| **Auxiliar Jade** | Personagem secundário do campeão com árvore própria (`jade_annie_tibbers`, `jade_nidaleecougar`) |
| **ID deslocado (Clássico)** | Campeão `60000 + id` (60001 = Annie); skin/chroma `60000000 + id` (60001001 = Annie Gótica) |
| **skins-pane** | Componente de seleção de skin do Rift Clássico (`.skins-pane__skin-title`, `__locked-overlay`, `__sub-title`) |
| **Skin/chroma exclusivo do Clássico** | Números ≥ 300 (ex.: 60001301 "Annie Clássica"); só existem na árvore Jade |
| **Smart App Control** | Política do Windows que bloqueia executáveis sem assinatura (`WinError 4551`) |
| **silent-ok** | Marcador na linha de um `except` que não loga de propósito (`# silent-ok: <motivo>`); exigido pela ADR-008 e verificado por `test/test_no_silent_exceptions.py` |
| **r3dlog** | Log do processo do jogo em `<League>\Logs\GameLogs\` |

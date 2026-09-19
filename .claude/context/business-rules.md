# Regras de negócio — Rose

## Seleção do alvo de injeção
Prioridade em `threads/utilities/skin_name_resolver.py`:
1. **Historic mode** — última skin injetada para o campeão
2. **Random mode** — skin sorteada pelo dado
3. **Skin/chroma selecionada** — `last_hovered_skin_id`

Invariantes:
- Seleção explícita de skin/chroma diferente da sorteada **desativa o random mode**; selecionar a própria skin sorteada mantém o modo (ADR-001).
- Seleção de chroma/skin desativa historic mode, exceto quando a seleção é o alvo do mod customizado salvo.
- Ativar random mode desativa historic mode.
- Random e historic são limpos ao sair da ChampSelect e após a injeção.
- Skins possuídas pelo jogador não são injetadas.

## Injeção
- O jogo fica suspenso durante o `mkoverlay` e só é retomado quando `runoverlay` inicia; auto-resume de segurança (`monitor_auto_resume_timeout`, padrão 60s).
- `runoverlay` permanece ativo durante a partida; é encerrado no fim do jogo, na limpeza de lobby ou ao fechar o Rose.
- Encerramento intencional do overlay pelo Rose **não é falha** de injeção (ADR-002).
- Threshold/cooldown de injeção configurável (`injection_threshold`).

## Conteúdo de skins
- `.fantome` vem de `Alban1911/LeagueSkins`; sync incremental por SHA de commit a cada start do launcher.
- `"Version": "Patch X"` no `info.json` não garante compatibilidade.

## Compatibilidade de mods custom entre patches
Investigação completa: `reviews/2026-09-18-compatibilidade-de-mods-custom.md`.

- Duas famílias de mod, com comportamentos opostos:
  - **Redirect** (biblioteca do Rose, 99,5% dos 8.995 `.fantome`): WAD de ~3 KB e 1 entrada, só um
    PROP cujo link aponta para `Skins/SkinN.bin` **do jogo**. O conteúdo é resolvido em runtime
    contra o jogo instalado, então sobrevive a patch.
  - **Conteúdo** (Runeforge e afins): copia BINs e assets integralmente, congelados no patch de
    publicação.
- A incompatibilidade **não** é hash mudando — hashes de caminho são determinísticos e estáveis.
  É **link pendurado**: a Riot esvaziou `Skins/SkinN.bin`, moveu o conteúdo para
  `<Char>_Multi_Skins_…bin` e removeu o antigo `Skins/Skin-1.bin` que os mods antigos referenciam.
- Mod com link pendurado **derruba o jogo no loading screen** (~150 ms após `Loading Started`),
  com `ALE-… FATAL ERROR. Missing data: 0x0` — não no spawn. Validado in-game em 2026-09-18.
  Logo: recusar a injeção é seguro e não há degradação parcial a tolerar.
- Só `.bin` (PROP) causa incompatibilidade; `.tex/.scb/.anm/.skn/.skl` são conteúdo opaco e
  estáveis entre patches. Um mod de centenas de MB em textura é praticamente imune.

## Rift Clássico (gameMode JADE, fila 3262)
- O jogo carrega `Jade_<Campeão>` com slots base 0/301/302, não o personagem normal (ADR-004).
- O mod é gerado na hora a partir de `jade_*/skins/skinN.bin` do jogo instalado **de cada usuário**; nunca a partir do `.fantome` da comunidade. Não é necessário ter o arquivo da skin na biblioteca (a biblioteca só fornece o nome do WAD do campeão).
- Campeão e auxiliares (Tibbers, forma puma, dragão, estandarte...) são trocados juntos quando possuem a skin N.
- Navegar no carrossel do Clássico depende de `session.allowSkinSelection` (LCU); a posse só impede a confirmação no LCU, não a troca do título que o Rose lê. O carrossel volta sozinho para a skin do LCU na entrada do FINALIZATION e no GAME_STARTING: o segundo é **só visual**, depois do limiar do ticker (validado in-game com outro jogador em 2026-09-19).
- No Clássico o Rose **não força a skin base** (o `skins-pane` do `rcp-fe-lol-jade` reposicionaria o carrossel); em vez disso sobrescreve os slots 0/301/302 **e** o da skin atualmente selecionada no LCU.
- Skin inexistente na árvore Jade: não injetar e não suspender o jogo; registrar `[CLASSIC] ... cannot be shown in Rift Classic`.
- Cobertura validada (patch 16.18, catálogo real do cliente): 68/68 campeões, 419/419 skins não-base (incluindo 40 exclusivas) e 1196/1196 chromas geram mod; `mkoverlay` real aceitou 68 mods simultâneos (87 personagens).
- Party skins e mods customizados não se aplicam ao Clássico.
- O cliente usa IDs deslocados no Clássico: campeão `60000 + id`, skin/chroma `60000000 + id`. O Python normaliza para o ID normal antes de buscar o `.fantome` (confirmado para os 68 campeões).
- A seleção de skin do Clássico é o componente `.skins-pane` (nome em `.skins-pane__skin-title`); o ROSE-UI esconde o cadeado e troca o subtítulo "Desabilitada" por "Habilitada" (idioma via `/riotclient/region-locale`).
- Validado in-game em 2026-09-16: Annie Gótica + Tibbers (jogo carregou `Jade_Annie SkinID(0)`).
- Dado (random), roda de chroma e histórico ainda não suportam a tela do Clássico: chromas estão prontos no lado do jogo, mas não há como selecioná-los na UI do Clássico (o ROSE-UI esconde o seletor nativo e o ChromaWheel não reconhece `.skins-pane`).

## Telemetria
- Opt-out do usuário em `config.ini`: `[General] analytics_enabled = false` (lido a cada ping).
- Payload restrito a `install_id` aleatório, versão e evento.

## Pengu Loader
- Ativado pela CLI oficial depois que o WebSocket do LCU fica ativo; desativado no cleanup.
- Exige elevação e binários assinados em máquinas com Smart App Control (ADR-003).

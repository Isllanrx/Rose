# ADR-001 — Seleção explícita de skin/chroma cancela o random mode

- **Status:** aceito
- **Data:** 2026-09-16

## Contexto
`SkinNameResolver` prioriza random mode sobre `last_hovered_skin_id`. O random mode só era cancelado quando o carrossel detectava troca de skin (`UserInterface.show_skin`). Seleções pela roda de chroma (incluindo "Default") não passavam por esse caminho. Em 16-09-2026 18:24 o usuário sorteou 21018, escolheu 21069 pelo chroma e 21018 foi injetada.

## Decisão
Toda seleção explícita de skin/chroma recebida do cliente desativa o random mode, exceto quando o ID selecionado é o próprio `random_skin_id`. Implementado em `cancel_random_mode_for_selection` (`ui/handlers/randomization_handler.py`) e chamado em `ChromaSelectionHandler.handle_selection` e no fallback de `MessageHandler._handle_chroma_selection`.

## Alternativas consideradas
- **Inverter a prioridade no resolver** (seleção > random): quebraria o random mode, pois o dado força a skin base e `last_hovered_skin_id` sempre existe.
- **Cancelar no plugin JS**: exigiria duplicar a regra em ChromaWheel e FormsWheel e não cobriria o fallback Python.
- **Cancelar só no caminho `_handle_regular_chroma_selection`**: não cobriria base skin, HOL e forms.

## Consequências
- Comportamento previsível: a última ação explícita do usuário vence.
- A mensagem `chroma-selection` precisa continuar sendo disparada apenas por clique do usuário (verificado em ROSE-ChromaWheel).
- Coberto por `test/test_injection_selection_regressions.py::RandomModeChromaSelectionTests`.

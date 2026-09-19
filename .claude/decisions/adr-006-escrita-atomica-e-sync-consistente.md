# ADR-006 — Escrita atômica de estado e sync de skins consistente

- **Status:** aceito
- **Data:** 2026-09-17

## Contexto
Review de produção (skill `prod-risk-review`) encontrou perda de dados silenciosa:
- `config.ini`, `historic.json`, `historic_targets.json` e `mod_historic.json` eram regravados com `open("w")`. Crash, disco cheio ou arquivo travado por antivírus deixavam o arquivo truncado; a leitura seguinte devolvia `{}` e a próxima gravação apagava todas as outras entradas. Leitura-modificação-gravação do histórico em várias threads perdia campeões (reproduzido 5/5).
- `set_config_option` ignorava erro de parse e regravava o INI só com a opção nova.
- Sync de skins: falha ao extrair um arquivo só gerava WARNING, o `.fantome` ficava truncado e o SHA era gravado — o arquivo nunca era baixado de novo. O SHA gravado era buscado **depois** do download. Entradas do ZIP não passavam por verificação de caminho, e `is_safe_path` comparava prefixo de string (`skins-evil` passava como dentro de `skins`).

## Decisão
- `utils/core/atomic_file.py`: grava em arquivo temporário irmão e troca com `os.replace` (atômico no NTFS), com até 5 tentativas em `PermissionError` (antivírus/leitor concorrente). `durable=True` (padrão) faz `fsync` — usado em config/histórico; `durable=False` no sync de skins (fsync custava ~12 ms/arquivo, ~110 s em 9 mil arquivos).
- Histórico: `RLock` por módulo em volta do ciclo ler-modificar-gravar; falha de gravação vira WARNING.
- Config: se o INI não puder ser lido, não salvar e registrar WARNING.
- Sync: SHA fixado antes do download e gravado só com zero falhas (`last_extraction_failures`); extração/download incremental atômicos; entradas fora da pasta recusadas (`join_within` léxico com base resolvida uma vez; `is_safe_path` com `Path.is_relative_to`); `OSError` no incremental conta como falha e cai no ZIP completo.

## Alternativas consideradas
- **Backup `.bak` antes de gravar**: não resolve gravação concorrente e deixa dois arquivos para reconciliar.
- **`fsync` em todos os arquivos**: seguro contra queda de energia, mas o sync completo ficaria ~110 s mais lento; sync interrompido é refeito no próximo start.
- **Resolver cada entrada do ZIP no disco**: ~12 mil chamadas `resolve()`; substituído por verificação léxica após resolver a base.

## Consequências
- Falhas parciais se corrigem sozinhas no próximo start (baixa de novo), ao custo de banda.
- Extração completa ~5–10% mais lenta (mediana 3,4 s → 3,6 s para 2 mil arquivos).
- Arquivos `.<nome>.*.tmp` podem sobrar após crash; o cleanup do sync completo remove os da pasta de skins.
- Testes: `test/test_data_integrity.py` (22).

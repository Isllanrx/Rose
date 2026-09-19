# Checklist — Migração de dados/config (Rose)

Rose não usa banco de dados. "Migração" aqui cobre formatos persistidos localmente.

## Artefatos persistidos
- `config.ini` (paths do League, thresholds, `installed_version`, `update_retry_count`)
- `%LOCALAPPDATA%\Rose\state\` (bridge port, sessão do Pengu)
- Historic de skins e mods (`utils/core/historic.py`, `utils/core/mod_historic.py`)
- `%LOCALAPPDATA%\Rose\skins\` + SHA local do repositório de skins
- `%LOCALAPPDATA%\Rose\Pengu Loader\` (config, datastore, estado enable/disable de plugins)

## Checklist
- [ ] Leitura tolerante ao formato antigo (fallback, sem exceção no startup)
- [ ] Escrita apenas no formato novo; migração idempotente
- [ ] Nunca apagar dados do usuário sem backup (historic, mods importados, plugins desabilitados)
- [ ] Compatível com rollback para a versão anterior (ou documentar que não é)
- [ ] Atualizações do app: respeitar detecção de update falho (`installed_version` > `APP_VERSION`, limite de 3 tentativas)
- [ ] Testar com cópia real de `%LOCALAPPDATA%\Rose` de uma versão anterior
- [ ] Registrar em ADR quando alterar formato ou local de armazenamento

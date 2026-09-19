# Segurança — Rose

## Invariantes
- **Extração**: `.fantome`/ZIP sempre via `utils/core/safe_extract.py` (proteção contra path traversal). Nunca `ZipFile.extractall` direto.
- **DLL de injeção**: `cslol-dll.dll` não é distribuída (DMCA); validada por hash em `main/__init__.py::_check_dll_present` antes do startup.
- **Elevação**: app e Pengu Loader rodam como administrador; ativação do Pengu exige token de alta integridade.
- **Assinatura**: com Smart App Control ativo, binários sem assinatura são bloqueados. Não distribuir build com `Pengu Loader.exe`/`core.dll` sem assinatura.
- **Updates**: atualização do app exige confirmação; hashes e skins (dados) são baixados sem confirmação.
- **Fontes remotas**: GitHub `Alban1911/Rose` (releases), `Alban1911/LeagueSkins` (skins), `CommunityDragon/Data` (hashes), `analytics.rosekeys.site`, relay Cloudflare (party).
- **Analytics**: ID pseudônimo aleatório, não derivado do Machine GUID; desligável via `ANALYTICS_ENABLED`.
- **Processos**: cleanup encerra apenas `mod-tools.exe`; nunca processos do jogo/cliente.
- **Bridge local**: escuta apenas em `127.0.0.1`.
- **Rift Clássico**: o alias do WAD vindo de arquivos da biblioteca é restrito a `[A-Za-z0-9_]+` (vira nome de pasta); WAD/PROP malformados viram `ClassicSkinError` (sem exceção não tratada na thread de injeção). Dependências `xxhash==4.0.1` e `zstandard==0.25.0` fixadas em `requirements.txt`.
- **Caminho seguro**: `is_safe_path` compara componentes (`Path.is_relative_to`), não prefixo de string; extração em massa usa `join_within` com a base resolvida uma vez. Entradas do ZIP de skins e caminhos do update incremental fora da pasta são recusados (ADR-006).
- **Pendente (skill `windows-trust-review`, backlog #3–#8)**: update baixado sem verificação de assinatura; staging e `apply_update.bat` em `%LOCALAPPDATA%` executados elevados; Rose elevado executa `Pengu Loader.exe`/DLLs copiados para `%LOCALAPPDATA%`; `[UninstallRun]` executa exe de `{localappdata}`; `cmd`/`schtasks` por caminho parcial; `Rose.exe` sem VERSIONINFO e `unins000.exe` sem assinatura. Binários oficiais são assinados por "Open Source Developer Alban CLIQUET" (Certum). Nunca propor exclusão no Defender.
- **Plugins de diagnóstico** (ex.: DomProbe) são só leitura, ficam fora do repositório e devem ser removidos após o uso.

## Histórico
| Data | Item |
|---|---|
| — | Nenhum CVE registrado |
| 2026-09-17 | Path traversal no ZIP de skins e prefixo em `is_safe_path` corrigidos (`78f5d805`, `45b24701`) |

Commits de hardening relevantes: `3df60f7e` (token de alta integridade no Pengu), `0697a550` (elevação obrigatória), `e92d2bac` (mapeamento de integrity levels).

# ADR-003 — Builds locais usam binários assinados do Pengu Loader

- **Status:** aceito (processo manual)
- **Data:** 2026-09-16

## Contexto
`scripts/build_pyinstaller.py` compila o Pengu Loader de `vendor/PenguLoader-1.1.6`. O executável resultante não tem assinatura. Na máquina de desenvolvimento o Smart App Control está ativo e bloqueou `Pengu Loader.exe` (`WinError 4551`, CodeIntegrity 3033/3077): o Pengu nunca ativava e os plugins não carregavam no cliente.

## Decisão
Para builds locais de teste, após o build copiar os binários assinados (`Pengu Loader.exe`, `core.dll`, DLLs e `.config`, versão 2.0.0) de `C:\Program Files\Rose\_internal\Pengu Loader\` para `dist\Rose\_internal\Pengu Loader\`. O Rose sincroniza essa pasta para `%LOCALAPPDATA%\Rose\Pengu Loader` a cada start.

## Alternativas consideradas
- **Desativar Smart App Control**: irreversível sem reinstalar o Windows; reduz a segurança da máquina.
- **Assinar localmente com certificado próprio**: exige certificado confiável; autoassinado não satisfaz o SAC.
- **Não reconstruir o Pengu no build de teste**: requer mudança no script (backlog #6).

## Consequências
- Build local funcional sem alterar políticas do Windows.
- O `vendor/` compilado não é validado em runtime nessa máquina; mudanças no código do loader precisam de binário assinado para teste.
- Builds de release devem continuar assinados.

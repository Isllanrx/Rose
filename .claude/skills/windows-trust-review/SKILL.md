---
name: windows-trust-review
description: Revisão sistemática do Rose para distribuição no Windows — permissões de disco/ACL, elevação (UAC), escalonamento de privilégio por caminhos graváveis e sinais que fazem Defender/SmartScreen/antivírus marcarem falso positivo (assinatura, metadados, heurísticas comportamentais do PyInstaller, batch, tarefas agendadas, atributos ocultos). Use quando pedirem "falso positivo", "antivírus", "Defender", "SmartScreen", "permissão de disco", "UAC", "assinatura", "instalador" ou antes de uma release.
---

# Windows Trust Review — Rose

Objetivo: o executável distribuído não deve ser bloqueado nem marcado como malware, e nenhum arquivo executado com privilégio de administrador pode ser gravável por um usuário comum.
Fora de escopo: estilo, tipagem, lógica de injeção (exceto o que muda a superfície de confiança).

## Regras
- Todo achado precisa de evidência: `arquivo:linha`, saída de comando (`Get-AuthenticodeSignature`, `Get-Acl`, `schtasks /Query`) ou log.
- Separar **segurança real** (escalonamento de privilégio, integridade de update) de **reputação/heurística** (falso positivo). Segurança real vem primeiro.
- Nunca propor exclusão no Defender (`Add-MpPreference -ExclusionPath`), desativar SmartScreen/SAC ou ofuscar/empacotar binário para "passar" no antivírus — isso é o comportamento que o antivírus deve pegar.
- Comportamento essencial do produto (suspender o jogo, `runoverlay` injetar DLL, Pengu Loader via IFEO) não é removível; documentar como risco residual e mitigar com assinatura + transparência.
- Não alterar código sem pedido; propor correção mínima + como validar.

## Coleta (somente leitura)
```powershell
# Assinatura e metadados de todos os PE distribuídos (build local e instalado)
Get-ChildItem dist\Rose, 'C:\Program Files\Rose' -Recurse -Include *.exe,*.dll | ForEach-Object {
  $s = Get-AuthenticodeSignature $_.FullName; $v = $_.VersionInfo
  '{0} | {1} | {2} | {3}' -f $_.FullName, $s.Status, $v.CompanyName, $v.FileVersion }
# ACL de diretórios cujo conteúdo é executado elevado
Get-Acl "$env:LOCALAPPDATA\Rose\Pengu Loader" | Select-Object -ExpandProperty Access
# Tarefa agendada e histórico do Defender
schtasks /Query /TN Rose /V /FO LIST
Get-MpThreatDetection | Where-Object { $_.Resources -match 'Rose|Pengu|mod-tools|cslol' }
```
Busca no código: `uac_admin|version=|upx|codesign` (Rose.spec), `SignTool|PrivilegesRequired|UninstallRun|Run\]` (installer.iss), `Popen|subprocess.run|ShellExecute|runas|schtasks|cmd|\.bat|robocopy|del "%~f0"|ping 127.0.0.1` , `copytree|copy2` + `get_user_data_dir`, `SetFileAttributesW|HIDDEN|SYSTEM`, `winreg|HKEY_LOCAL_MACHINE`, `\.suspend\(\)|nice\(|HIGH_PRIORITY`, `hashlib|sha256` perto de downloads.

## Checklist

### 1. Escalonamento de privilégio (segurança real)
- Binário/DLL/script **executado pelo processo elevado** a partir de pasta gravável por usuário comum (`%LOCALAPPDATA%`, `%TEMP%`, `%APPDATA%`, pasta de updates). Inclui DLL carregada ao lado do exe (DLL planting).
- Janela entre copiar e executar (TOCTOU) em pasta gravável.
- Caminho parcial em `subprocess` (`"cmd"`, `"schtasks"`, `"explorer"`) — resolver para `%SystemRoot%\System32\...`.
- `[UninstallRun]`/`[Run]` do instalador executando algo de `{localappdata}`/`{userappdata}` com privilégio de admin.
- Tarefa agendada `/RL HIGHEST` apontando para exe em pasta não protegida.

### 2. Integridade de update e downloads
- Pacote de update baixado sem verificação de hash/assinatura antes de ser copiado para `Program Files`.
- Hash publicado no mesmo canal que o arquivo (não protege contra release comprometido) — preferir verificar assinatura Authenticode do `Rose.exe` extraído contra o publisher esperado.
- Dados baixados sem confirmação que viram código/executável.

### 3. Permissões de disco
- Escrita em `Program Files` em runtime (só funciona elevado; quebra se instalado por outro usuário/sem UAC).
- Dados do usuário no perfil errado quando o admin elevado é outra conta (`get_user_data_dir`).
- Arquivos criados elevados no perfil do usuário ficando com dono Administrators.
- Caminhos > 260 caracteres, OneDrive/Known Folder Move, Controlled Folder Access (Documentos/Desktop).
- Arquivo travado por antivírus → `PermissionError` transitório (usar retry, ver `utils/core/atomic_file.py`).

### 4. Reputação e metadados (falso positivo)
- Todos os PE assinados (Authenticode + timestamp), incluindo `unins000.exe`/instalador (`SignTool=` no Inno Setup) e build local nunca distribuído sem assinatura.
- Recurso VERSIONINFO (Company, Product, FileVersion, FileDescription, LegalCopyright) no `Rose.exe` (`version=` no EXE do spec) e no instalador.
- Certificado OV/Open Source não tem reputação instantânea no SmartScreen: manter o mesmo certificado entre versões e enviar builds novas para análise da Microsoft (WDSI) quando detectadas.
- PyInstaller: `upx=False` (UPX aumenta detecção); bootloader recompilado do fonte reduz assinaturas genéricas de "PyInstaller dropper".
- AppId do Inno Setup único (não GUID de exemplo).

### 5. Heurísticas comportamentais (reduzir o que não é essencial)
- Batch gerado em runtime com `ping 127.0.0.1` como sleep, auto-exclusão (`del "%~f0"`), `robocopy /MIR` em Program Files.
- `SetFileAttributesW(HIDDEN|SYSTEM)` em pastas próprias.
- Escrita em `HKLM\...\Uninstall` a cada start.
- Processos filhos ocultos (`CREATE_NO_WINDOW`) + elevação de prioridade + suspensão de outro processo, sem janela nem log visível.
- Autostart oculto com privilégio máximo sem opção clara na UI.

## Relatório
Tabela por severidade: `severidade | categoria | evidência | risco | correção mínima | como validar`.
Ao final: **risco residual inerente ao produto** (o que continuará gerando alerta mesmo corrigido) e **ações fora do código** (certificado, WDSI, reputação).

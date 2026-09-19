# testes_Pesados

Validação real do caminho crítico do Rose, com processos e dados de verdade.
Complementa `test/`, não substitui.

```
.venv\Scripts\python testes_Pesados\run_all.py
```

## Por que existe

`test/` tem 107 testes que rodam em 9 segundos. Para regressão de lógica é bom,
mas o sintoma mais grave do produto — **jogo congelado** — é validado contra
dublês: `test/test_shutdown_safety.py` tem 11 mocks para 12 testes, e chega a
fazer `manager._stop_monitor = MagicMock()`.

O problema é que os defeitos do backlog #9 e #10 estão no controle de fluxo do
próprio `GameMonitor` e do handler do Swiftplay. Um mock substitui exatamente o
objeto que tem o bug, então o teste passa e o bug continua.

Aqui os processos são reais: `psutil` suspende e retoma um processo Python de
verdade, e o que se afirma é o estado do sistema operacional, não uma chamada.

## Como ler uma falha

**Falha aqui não é teste quebrado — é defeito no produto.** Os cenários foram
escritos a partir de defeitos confirmados no código, então falham até que ele
seja corrigido. O runner mapeia cada falha ao item do backlog que ela comprova.

| Arquivo | Cobre | Sintoma para o usuário |
|---|---|---|
| `test_game_monitor_real_process.py` | #9a, #9b | jogo congelado até fechar o Rose |
| `test_swiftplay_monitor_leak.py` | #10 | jogo suspenso até o auto-resume, sem skin |
| `test_external_process_timeout.py` | #12 | Rose que não fecha |
| `test_skin_library_integrity.py` | compatibilidade | crash no loading screen |

## Estado atual

Última execução: **7 de 14 cenários reproduzem defeito**.

Confirmados como abertos: #9a (`stop()` não resume quando o monitor se
auto-desativou), #9b (quatro threads `GameMonitor` vivas ao mesmo tempo após
chamadas repetidas a `start()`), #10 (Swiftplay não solta o jogo quando o
overlay falha ou retorna código não-zero) e #12 (`subprocess.run` sem `timeout`
bloqueia, e `TimeoutExpired` escaparia mesmo se o timeout fosse adicionado —
`except` atual só captura `FileNotFoundError` e `OSError`).

Passando: os controles de cada classe e os três de integridade da biblioteca —
250 mods amostrados resolvem contra o patch instalado, sem link pendurado.

## Limites — o que esta suíte NÃO prova

Não use estes testes como prova de aptidão total. Fora do alcance:

- **`mkoverlay`/`runoverlay` reais.** Nenhum teste executa `mod-tools.exe`.
  `coding-standards.md` avisa que `runoverlay` sem stdin sai na hora com 0, o
  que invalidaria um teste ingênuo.
- **Teste C** — fechar o Rose pela bandeja durante uma partida, validação
  in-game pendente do ADR-007. Só reproduzível com o jogo rodando.
- **`mkoverlay` em cache frio** — mediu 97,63 s na primeira execução contra
  4,20 s na segunda (backlog #13). Exige reiniciar a máquina, não automatizável
  aqui.
- **Concorrência sob carga real** — os testes forçam corridas específicas, não
  varrem o espaço de interleavings.

## Segurança

Todo processo criado é registrado e morto no `tearDown`, **resumido antes de
morto** — um processo suspenso pode ignorar o `terminate`. Se um teste for
interrompido com Ctrl+C no meio, confira processos `python.exe` órfãos.

Os testes não tocam no jogo, no cliente, em `mod-tools.exe` nem em qualquer
arquivo do usuário. `test_skin_library_integrity.py` **lê** a biblioteca e os
WADs do jogo, sem escrever.

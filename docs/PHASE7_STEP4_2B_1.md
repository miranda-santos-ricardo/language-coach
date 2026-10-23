# Phase 7 — Step 4.2b.1 — Non-Seekable Audio Input Fix

## Diagnóstico confirmado
O FFmpeg decodifica o MP4/AAC Samsung de 10,26 s por caminho de arquivo, mas a mesma entrada enviada por `pipe:0` retorna zero bytes, com `partial file` e `Invalid data found when processing input`. O contêiner exige busca aleatória em metadados; `stdin` não permite seek.

## Entrega
Atualiza somente `backend/app/services/speech_analysis_prototype.py`, função `_decode_pcm()`. Mantém o modo `pipe:0` para arquivos compatíveis e realiza uma segunda tentativa via arquivo temporário privado quando a saída PCM do primeiro FFmpeg é inválida. Fecha o arquivo antes de iniciar o processo (compatível com Windows), remove-o no bloco `finally`, mantém execução sem shell, 10 MiB de entrada e máximo de 60 s de PCM mono 16 kHz. Tratamentos de timeout, erro de execução e limpeza de arquivo temporário são explícitos. Sem migrations, APIs, serviços pagos ou dependências extras.

**Privacidade:** o fallback grava áudio bruto transitoriamente no diretório temporário do sistema. O arquivo é apagado ao fim do processamento normal ou das exceções gerenciadas. Uma interrupção brusca do processo, queda de energia ou impossibilidade de exclusão pode deixar dados residuais no disco. Para produção, configurar diretório temporário privado controlado, política de expurgo de órfãos e isolamento de processos. Não utilizar em armazenamento compartilhado desprotegido. O áudio não é enviado a terceiros.

## Instalação
Extrair o ZIP na raiz do repositório, substituindo apenas `backend/app/services/speech_analysis_prototype.py` e adicionando o teste e esta documentação. Em seguida, dentro de `backend`:

```powershell
python -m pytest -q tests/test_audio_seek_fallback.py
python -m pytest -q
alembic current
python -m app.services.vad_runtime_benchmark_cli `
  --audio .\samples\fr_ca_01.mp4 `
  --locale fr-CA `
  --consent > vad_report.json
```

O script CLI deve ser restaurado para o `except` original que registra apenas `error_type`, removendo o `traceback.print_exc()` usado durante a investigação.

## Validação executada para o pacote
- 9 testes novos: **passed**; inclui MP4/AAC gerado localmente com FFmpeg, fallback e limpeza em sucesso, falha e timeout.
- 18 testes do incremento 4.2b disponíveis neste ambiente: **passed** (27/27 combinados).
- A suite completa do repositório do usuário deve ser executada localmente. Baseline reportada: 445; com 18 da Step 4.2b, se também integrados, 463; somando 9 novos, **472**, se nenhuma outra alteração impactar a contagem.
- A passagem dos testes não confirma ainda qualidade do VAD em dados de voz reais ou integridade de anotações humanas.

## Próximo critério de aceite
Benchmark real em MP4: status de execução, áudio decodificado, timestamps coerentes, latência e, em seguida, comparação com anotações humanas. Nunca transformar detecção de atividade em score de pronúncia.

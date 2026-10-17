# Phase 5 — Step 10, Incremento 2

## Escopo

Este pacote acrescenta um avaliador de qualidade com relatório JSON, reutilizando o dataset `backend/evaluations/coach_cases_v1.json`, o Prompt Builder `coach-v2`, o provider `ConversationLLM` e o validador Pydantic do Step 5.

**Por padrão, `dry-run` é inteiramente offline. Nenhuma chamada à OpenAI é feita.** Todos os testes de modo `live` usam um provider falso. Nenhum arquivo existente precisa ser substituído.

## Instalação

Extrair o ZIP na raiz do repositório `language-coach`, preservando a estrutura `backend/`.

## Validação sem custo

```powershell
cd backend
python -m pytest -q tests/test_quality_evaluation.py tests/test_evaluation_dataset.py
python -m pytest -q
python -m app.evaluation.quality_report
python -m app.evaluation.quality_report --max-cases 3 --output evaluations/quality_report_dry_run.json
alembic current
```

Esperado: 25 testes direcionados, suíte completa com aproximadamente 296 testes (284 anteriores + 12 novos), dry-run com 14 casos aprovados e Alembic `c5202601 (head)`.

Para comprovar que não existe execução paga por engano (falha esperada, exit code 2):

```powershell
python -m app.evaluation.quality_report --mode live --max-cases 1
```

## Execução live — **NÃO EXECUTAR** sem aprovação explícita e orçamento

Somente quando houver autorização, API key válida e decisão consciente de incorrer em custos, são exigidos **dois desbloqueios** simultâneos: argumento `--allow-paid-api-calls` E `LANGUAGE_COACH_EVAL_LIVE=YES`.

Exemplo documentado, **não executado por esta entrega**:

```powershell
$env:LANGUAGE_COACH_EVAL_LIVE='YES'
python -m app.evaluation.quality_report --mode live --max-cases 1 --allow-paid-api-calls --output evaluations/quality_report_live.json
Remove-Item Env:LANGUAGE_COACH_EVAL_LIVE
```

`--max-cases` limita a quantidade de invocações (1–50), **não limita o custo total em moeda ou tokens**. Uma chamada pode consumir tokens variáveis e ter custo. Iniciar com 1 caso e revisar custos antes de aumentar. O dataset versão 1 contém 14 casos.

## Interpretação correta dos resultados

- `passed`/`failed`: validam o schema Pydantic e expectativas anotadas (statuses, canários regionais ou marcadores específicos).
- `errors`: falha de serviço/runtime ou provider; detalhes sensíveis nunca são registrados.
- `subjective_quality: not_assessed`: naturalidade, nível CEFR, relevância, valor pedagógico, precisão e resistência ampla a prompt injection **não foram pontuados**.
- `human_review_required: true`: a resposta real deve ser examinada por avaliadores humanos com rubrica de 1–5 para correção, falsos positivos, adequação regional, CEFR, tom corporativo, continuidade e segurança.
- Relatórios omitem mensagens, prompts, respostas brutas e credenciais. Guardar relatórios no repositório somente após revisão de privacidade.

## Limitações deliberadas

- O dataset v1 contém rótulos `multi_turn`, mas **não contém histórico prévio de mensagens**. Logo os casos etiquetados assim NÃO testam continuidade real; ampliar o dataset e passar `recent_messages` em uma próxima revisão.
- Não há orçamento monetário rígido ou limite máximo de tokens configurado no provider do Step 3. O limite implementado é de quantidade de chamadas.
- O relatório não grava a resposta textual por padrão; revisão humana aprofundada requer executar sessões reais em ambiente de teste e inspecionar saídas de forma controlada e consentida.
- Nenhum código de banco/frontend, migration ou endpoint foi alterado.

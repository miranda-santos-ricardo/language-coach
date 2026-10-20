# Phase 6 — Test Evidence Register & Acceptance Checklist

**Regra de rastreabilidade:** valores citados aqui derivam de respostas do usuário durante a implementação; o presente documento não reexecutou browser, Vitest, Vite, PostgreSQL nem chamadas reais ao LLM.

## Regressão automatizada

| Marco | Evidência informada | Estado |
|---|---|---|
| Step 1 | `Test Files 10 passed`, `Tests 76 passed`, `built in 706ms` | PASS |
| Step 2 | Usuário: “tudo ok, todos os testes passaram” após fix | PASS informado; contagem estimada 83 |
| Step 3 | `Test Files 14 passed`, `Tests 94 passed`, `built in 730ms` | PASS |
| Step 4 hotfix | Primeiro 94/95 com uma falha de `dispose`, depois TS mock incorreto; ambas corrigidas; usuário: “passou todos os testes” | PASS informado; total final previsto 95/95, **sem log numérico anexado** |
| Backend | Última baseline reportada antes da Phase 6: 313 passed, Alembic `c5202601 (head)` | NÃO REEXECUTADO na Phase 6 |

## Checklist manual prioritário informado

| ID | Teste | Resultado |
|---|---|---|
| 01 | HTTPS e permissão de microfone | PASS |
| 02 | Gravar e transcrever áudio | PASS |
| 03 | Editar e enviar transcrição | PASS |
| 04 | Receber resposta do AI Coach | PASS |
| 05 | Listen, Pause, Resume, Stop e Repeat | PASS |
| 06 | Autoplay apenas para resposta nova | PASS no reteste; falhou inicialmente |
| 07 | Interromper TTS ao gravar | PASS |
| 08 | Sair e retomar sessão | PASS |
| 09 | Concluir sessão e interromper áudio | PASS |
| 10 | Trocar FR-CA e EN | PASS |
| 11 | Persistir preferências após atualização | PASS |
| 12 | Recuperar de falhas de rede ou permissão | PASS |

**Total prioritário:** 12 PASS, 0 FAIL no estado final informado.  
**Cobertura ampliada:** há um plano de **23 testes manuais** (além de 12 automatizados futuros) em `phase6_step4_validation/STEP4_TEST_PLAN.md`; sua execução completa **não foi relatada**.  
**Dispositivos e versões:** o usuário confirmou uso de Chrome em diagnóstico TTS; não foram anexados modelo e versão de cada telefone/navegador por caso. Não extrapolar o resultado para todas as plataformas.

## Diagnóstico e fechamento de incidentes

| Ref | Incidente | Ação/evidência | Resultado |
|---|---|---|---|
| INC-001 | “Audio unavailable in this browser” | Console: API=true, Utterance=function, 22 vozes; fix StrictMode + suíte completa aprovada; checklist de áudio aprovado | Resolvido para o ambiente testado |
| INC-002 | Autoplay não executava corretamente | Após encerrar/reabrir sessões, novo teste manual PASS | Fechado como não reproduzível; raiz não comprovada |
| INC-003 | Vitest `Should not already be working` | Mock `emit()` evitou `act()` reentrante; suíte depois aprovada | Resolvido |
| INC-004 | TypeScript `ok:boolean` vs `ok:true` no mock | Literal `as const`; testes posteriormente aprovados | Resolvido |

## Checklist residual de release (para novos usuários/dispositivos)

- [ ] Registrar captura da última execução `npm test` com total numérico final pós-hotfix.
- [ ] Registrar captura do `npm run build` do código final.
- [ ] Executar matriz completa de 23 cenários quando houver dispositivos suficientes.
- [ ] Registrar Chrome/Edge/Safari/Android/iOS, versões e voz/locale efetivamente usada.
- [ ] Medir qualidade da pronúncia FR-CA com feedback humano.
- [ ] Reexecutar regressão backend se houver futura alteração de backend ou intenção de release completo.
- [ ] Antes de distribuição pública, revisar auth, CORS, TLS, tratamento de dados e políticas de retenção.

## Decisão

**Aprovado para o escopo de MVP local VOX-001** com ressalvas de compatibilidade e riscos aceitos; **não aprovado como certificação multi-plataforma nem de deployment público**.

# Phase 6 — Technical Debt, Roadmap & Handoff

## Prioridades recomendadas

| ID | Prioridade | Trabalho | Motivação / aceite futuro |
|---|---|---|---|
| GOV-01 | P0 antes de publicação | Autenticação/autorização real, proteção de APIs e privacidade | Não disponibilizar app publicamente sem segurança adequada |
| QA-01 | P1 | Matriz real Android Chrome e iOS Safari | E2E por dispositivo + evidências de voz e microfone |
| QA-02 | P1 | Avaliação real STT + LLM e feedback pedagógico | Consentimento, dados sintéticos, orçamento definido, revisão humana |
| QA-03 | P2 | Monitorar reaparecimento do problema de autoplay | Se reproduzir, coletar evento e sequência sem PII |
| UX-01 | P2 | Qualidade de voz FR-CA e fallback | Voz disponível, sotaque e pronúncia documentados |
| UX-02 | P2 | Acessibilidade avançada de voz e áudio | Teclado, leitor de tela, anúncios, interrupções mobile |
| ENG-01 | P2 | Isolar engine TTS em provider swap-ready | Contratos consistentes para futuro fornecedor externo |
| VOX-NEURAL | Posterior | Avaliar voz neural por API ou modelo local | Qualidade vs custo/privacidade, opt-in explícito |
| VOX-DIALOGUE | Posterior | Conversa hands-free/full-duplex | Nova arquitetura de streaming, VAD/barge-in, sincronização/latência |
| PED-01 | Posterior | Feedback de pronúncia e fluência | Métricas de avaliação validadas, sem promessas de precisão sem benchmark |

## Sequência recomendada após encerramento

**Próximo ciclo curto:** hardening e matriz mobile. Não começar voz neural antes de garantir a qualidade do fluxo atual e de medir FR-CA/EN em dispositivos reais.

**Depois:** comparar voz neural gerenciada e engine local, com ADR sobre privacidade, suporte regional, latência e limites de custos. Não executar serviço pago sem permissão explícita.

**Futuro maior:** conversação contínua e avaliação de pronúncia; tratar como epics novas, não como extensões triviais do Browser TTS.

## Definition of Ready do próximo incremento

1. Seleção do alvo: mobile hardening, neural voice, ou fluência/pronúncia.
2. Evidência da falha/necessidade e navegadores-alvo.
3. Arquivos do HEAD atual disponíveis; evitar empilhar overlays antigos sem checar compatibilidade.
4. Critérios automatizados (mocks) e critérios manuais (dispositivos reais) separados.
5. Custo e política de transmissão de voz/áudio decididos antes de ativar providers.

## Continuidade técnica

Baseline de referência: frontend **94 testes informados explicitamente** + um teste de StrictMode adicionado com sucesso informado; backend anterior **313**, migration `c5202601 (head)`; testes manuais VOX-001 **12/12**. Faça snapshot/tag do código efetivamente executado antes de abrir a próxima fase.

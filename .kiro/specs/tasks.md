# Tarefas - Agente Revisor de PL/SQL

## Prioridade Alta (MVP)

## 1 Definição do agente

- [x] Definir objetivo do agente (ver `steering/product.md`)
- [x] Definir entradas e saídas esperadas (ver `specs/requirements.md`)
- [x] Descrever etapas principais (ver `specs/design.md`)
- [x] Justificar por que a solução é um agente (separação entre ferramenta, LLM e geração de resposta, com estado acumulado)

## 2 Implementação com LangGraph, ferramenta e contexto

- [x] Definir `AgentState` (`agent/state.py`)
- [x] Implementar ferramenta de leitura de arquivo (`read_sql_file`)
- [x] Implementar ferramenta de análise estática (`run_static_checks`)
- [x] Implementar nó `read_file_node`
- [x] Implementar nó `static_analysis_node`
- [x] Implementar nó `llm_review_node` (integração com Groq via `langchain-groq`)
- [x] Atualizar `agent/graph.py` para usar `groq/compound-mini` como padrão
- [x] Implementar nó `complexity_check` (análise de complexidade ciclomática)
- [x] Implementar nó `rag_retrieval_node` (recuperação de contexto Oracle PL/SQL)
- [x] Implementar nó `save_history_node` (persistência de histórico)
- [x] Adicionar políticas de autonomia (`agent/autonomy.py`)
- [x] Adicionar validação de permissões (`agent/authorization.py`)
- [x] Implementar tratamento de falhas (timeout, retry, circuit breaker, fallback)
- [x] Implementar logs estruturados e métricas
- [x] Adicionar integração com n8n (`n8n_agent_wrapper.py`)
- [x] Implementar nó `generate_report_node`
- [x] Conectar os nós no grafo (`build_graph`) e compilar
- [x] Implementar CLI de execução (`agent/main.py`)
- [x] Tratar erros de leitura sem derrubar o fluxo

## 3 Documentação, prompts e repositório

- [x] Escrever `README.md` completo
- [x] Registrar prompts principais em `docs/prompts.md`
- [x] Criar exemplo de entrada (`examples/input_example.sql`)
- [x] Criar exemplo de saída (`examples/output_example.md`)
- [x] Criar `.gitignore` cobrindo `.env` e artefatos locais

## Backlog v2.0 (fora do escopo atual)

### Tarefa 4: Suporte a Múltiplos Arquivos
- [ ] Suportar diretório de entrada
- [ ] Processar arquivos em lote
- [ ] Agregação de resultados por schema

### Tarefa 5: IDE Integration
- [ ] Extensão VS Code para revisão inline
- [ ] Integração com LSP para PL/SQL
- [ ] Notificações de issues durante editação

### Tarefa 6: Dashboard Web
- [ ] Frontend React/Vue para visualização
- [ ] Histórico de revisões
- [ ] Comparação entre versões

### Tarefa 7: Regras Adicionais
- [ ] Detectar `SELECT *` em subqueries
- [ ] Detectar uso de `SELECT COUNT(*)` em loops
- [ ] Detectar `NOCOPY` em parâmetros sem necessidade
- [ ] Detectar uso de `GOTO`
- [ ] Detectar `COMMIT` em procedures/funções (regra aprimorada)

## Tarefas Concluídas (Pós-MVP)

### Tarefa 8: Integração com n8n
- [x] Criar `n8n_agent_wrapper.py` para integração com n8n via executeCommand
- [x] Atualizar workflow n8n com caminho correto do webhook
- [x] Criar documentação em `docs/solucao_webhook_n8n.md` e `docs/solucao_webhook_n8n_final.md`
- [x] Adicionar instruções n8n no README.md

### Tarefa 9: Atualização de Dependências
- [x] Adicionar `pytest`, `pytest-asyncio`, `pytest-cov` ao `requirements.txt`
- [x] Adicionar `build>=1.0.0` ao `requirements.txt`
- [x] Atualizar pipelines CI/CD para usar dependências do requirements.txt

### Tarefa 10: Correção de Configuração de Modelo
- [x] Atualizar `agent/graph.py` para usar `groq/compound-mini` como padrão
- [x] Atualizar `README.md` e `docs/sistema.md` com novo modelo
- [x] Remover referências ao arquivo inexistente `check_models.py`

### Tarefa 11: Melhoria de Qualidade de Código
- [x] Reorganizar importações em `n8n_agent_wrapper.py` (padrão, terceiros, locais)
- [x] Executar ruff check - todos os checks passando
- [x] Documentar ciclo de refinamento de prompt em `docs/ciclo_refinamento_prompt.md`

### Tarefa 12: Observabilidade e Logging
- [x] Implementar logs estruturados (JSON) com correlation_id
- [x] Implementar métricas (contadores, gauges, timings)
- [x] Implementar traces com span_id e duração
- [x] Criar documentação em `docs/observability.md` e `docs/sistema.md`

## Status Atual

**Status do MVP:** ✅ Concluído
**Status Pós-MVP:** ✅ Majoritariamente Concluído

### Concluído
- [x] Estrutura básica implementada
- [x] Fluxo LangGraph funcional
- [x] CLI operacional
- [x] Documentação básica
- [x] Integração com n8n
- [x] Atualização de dependências (pytest, build)
- [x] Configuração de modelo (groq/compound-mini)
- [x] Reorganização de importações
- [x] Ruff check 100% limpo
- [x] Documentação de ciclo de refinamento de prompt
- [x] Logs estruturados e métricas

### Em Planejamento
- [ ] Type hints completos para mypy
- [ ] Cobertura de testes para mypy
- [ ] Dockerfile para ambientes isolados
- [ ] CD automatizado (deploy)
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
- [x] Implementar nó `llm_review_node` (integração com Claude via `langchain-anthropic`)
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

## Status Atual

**Status do MVP:** ✅ Concluído

- [x] Estrutura básica implementada
- [x] Fluxo LangGraph funcional
- [x] CLI operacional
- [x] Documentação básica

**Próximos passos (Pós-MVP):**
- Implementar testes automatizados
- Adicionar CI/CD
- Melhorar qualidade de código (type hints, ruff, mypy)
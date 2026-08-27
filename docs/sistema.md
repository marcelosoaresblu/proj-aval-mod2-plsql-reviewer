# Documentação do Sistema — Agente Revisor de PL/SQL

**Data**: 26 de agosto de 2026  
**Versão**: 1.0.0

---

## Visão Geral

Este documento documenta as principais instruções de sistema utilizadas pelo agente, incluindo:

- Regras de comportamento
- Objetivos da tarefa
- Restrições importantes
- Padrões de resposta esperados
- Prompts relevantes

---

## 1. Objetivos da Tarefa

### Objetivo Principal
Automatizar uma primeira passada de revisão de código PL/SQL para identificar riscos comuns de manutenibilidade e tratamento de erros, especialmente em sistemas legados de ERP/PCP/MRP.

### Objetivos Específicos
1. **Detecção de problemas comuns**: WHEN OTHERS sem RAISE, SELECT *, COMMIT interno, valores hardcoded
2. **Cálculo de complexidade**: Complexidade ciclomática para avaliação de manutenibilidade
3. **Revisão qualitativa**: Parecer do LLM com contexto enriquecido
4. **Geração de relatório**: Formato Markdown estruturado com tabela de achados e recomendações
5. **Boas práticas Oracle**: Recomendações baseadas em documentação oficial

---

## 2. Regras de Comportamento

### Regras de Entrada
| Regra | Descrição | Consequência |
|-------|-----------|--------------|
| Extensão permitida | `.sql`, `.pck`, `.pkb`, `.pks`, `.prc`, `.fnc` | Rejeitar outros formatos |
| Tamanho máximo | 500KB (`TAMANHO_MAXIMO_BYTES`) | Rejeitar arquivos maiores |
| Caminho protegido | `/etc`, `/root`, `/home`, `.env` | Rejeitar acesso a caminhos protegidos |

### Regras de Processamento
| Regra | Descrição | Prioridade |
|-------|-----------|------------|
| Análise estática | Heurísticas regex (WHEN OTHERS, SELECT *, COMMIT, etc.) | Alta |
| Complexidade | Contagem de decisões (IF, ELSIF, CASE, LOOP, FOR, WHILE) | Média |
| RAG | Recuperação de documentação Oracle PL/SQL | Média |
| LLM Review | Parecer qualitativo com contexto enriquecido | Alta |

### Regras de Saída
| Regra | Descrição | Formato |
|-------|-----------|---------|
| Relatório estruturado | Tabela de achados, complexidade, recomendações, parecer LLM | Markdown |
| Erros claros | Mensagens de erro descritivas | Markdown com prefixo `❌` |
| Logs estruturados | JSON com correlation_id, timestamp, metadata | JSON |

---

## 3. Restrições Importantes

### Restrições Técnicas
| Restrição | Descrição | Solução Alternativa |
|-----------|-----------|---------------------|
| Sem parser PL/SQL real | Heurísticas regex (suficiente para escopo) | N/A |
| Sem acesso a banco de dados | Apenas leitura e análise de texto | N/A |
| Base RAG estática | Documentação Oracle em código | Futuro: Vector store |
| Modelo configurável | Pode ser trocado via variável | Suporte para Groq/Anthropic |

### Restrições de Segurança
| Restrição | Descrição |
|-----------|-----------|
| API Key não versionada | Sempre via `.env` |
| Caminhos protegidos | `/etc`, `/root`, `/home` bloqueados |
| Payload validation | Schema das tools validado |
| Sanitização de outputs | Segredos removidos de logs |

### Restrições de Performance
| Restrição | Descrição |
|-----------|-----------|
| Timeout LLM | 30 segundos (configurável) |
| Retry limitado | 2 tentativas com backoff exponencial |
| Circuit breaker | Abre após 3 falhas consecutivas |
| max_tokens | 1500 (padrão) |

---

## 4. Padrões de Resposta Esperados

### Resposta de Erro
```markdown
# Erro na revisão

Erro ao ler arquivo: arquivo inexistente
```

### Resposta de Sucesso
```markdown
# Relatório de Revisão — nome_arquivo.sql

## Achados da análise estática

| Linha | Severidade | Descrição |
|-------|------------|-----------|
| 1 | alta | WHEN OTHERS sem RAISE |

## Complexidade ciclomática
Complexidade estimada: 6

## Recomendações de boas práticas (Oracle PL/SQL)

| Linha | Regra | Recomendação |
|-------|-------|--------------|
| 1 | WHEN OTHERS sem RAISE | Incluir RAISE ou RAISE_APPLICATION_ERROR |

## Parecer do agente (LLM)

O código tem complexidade moderada. Recomendo:
1. Adicionar RAISE no WHEN OTHERS
2. Substituir SELECT * por colunas explícitas
```

### Resposta JSON (para integração com n8n)
```json
{
  "success": true,
  "file_analyzed": "examples/input_example.sql",
  "output_file": "/tmp/relatorio.md",
  "report_size": 7549,
  "timestamp": "2026-08-26T22:37:00.000Z"
}
```

---

## 5. Prompts Relevantes

### Prompt de Sistema (SYSTEM_PROMPT)

**Local**: `agent/graph.py` - constante `SYSTEM_PROMPT`

```python
SYSTEM_PROMPT = """Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código e uma lista de
achados de uma análise estática automática (heurísticas simples).

Sua tarefa:
1. Avaliar a qualidade geral do código (legibilidade, tratamento de erros,
   performance, aderência a boas práticas de PL/SQL).
2. Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.
3. Sugerir no máximo 5 melhorias concretas, priorizadas por impacto.

Responda em português, em formato Markdown, de forma objetiva e técnica.
Não invente comportamento do sistema que não esteja no código."""
```

### Prompt do Nó LLM (no llm_review_node)

**Local**: `agent/graph.py` - variável `prompt` dentro de `llm_review_node`

O prompt do usuário é construído dinamicamente com:

```
Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código, uma lista de
achados de uma análise estática automática (heurísticas simples), documentação
Oracle PL/SQL relevante, e contexto adicional.

Sua tarefa:
1. Avaliar a qualidade geral do código (legibilidade, tratamento de erros,
   performance, aderência a boas práticas de PL/SQL).
2. Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.
3. Usar a documentação Oracle PL/SQL (quando disponível) para fundamentar
   suas recomendações.
4. Levar em conta o contexto extra (ex: preferências do time, diretrizes
   específicas do ERP/PCP/MRP).
5. Sugerir no máximo 5 melhorias concretas, priorizadas por impacto.

Responda em português, em formato Markdown, de forma objetiva e técnica.
Não invente comportamento do sistema que não esteja no código.

{contexto_extra}

---

Código PL/SQL a revisar:

```sql
{state['codigo_fonte']}
```

Achados da análise estática automática:
{resumo_issues}

{contexto_complexidade}

{contexto_rag}
```

---

## 6. Arquitetura do Agente

### Fluxo LangGraph

```
read_file -> [heuristic_check, complexity_check, rag_retrieval] (paralelo)
             ↓
        llm_review (decisão do modelo)
             ↓
        save_history
             ↓
        generate_report
```

### Nó 1: read_file_node
- **Responsabilidade**: Ler arquivo com validação
- **Ferramenta**: `read_sql_file`
- **Validações**: Extensão, tamanho, caminho protegido
- **Retorna**: `codigo_fonte`, `erro`

### Nó 2: heuristic_check (static_analysis_node)
- **Responsabilidade**: Análise estática por regex
- **Ferramenta**: `run_static_checks`
- **Regras**: WHEN OTHERS, SELECT *, COMMIT, hardcoded, cursor, EXCEPTION
- **Retorna**: `issues_estaticos`

### Nó 2b: complexity_check
- **Responsabilidade**: Cálculo de complexidade ciclomática
- **Ferramenta**: Contagem de decisões (IF, ELSIF, CASE, LOOP, FOR, WHILE)
- **Fórmula**: 1 + número de decisões
- **Retorna**: `complexidade_ciclomatica`, `pontos_decisao`

### Nó 2c: rag_retrieval_node
- **Responsabilidade**: Recuperação de documentação Oracle PL/SQL
- **Ferramenta**: `PLSQLRetriever.retrieve`
- **Base**: 6 documentos (exceções, cursores, transações, SELECT, hardcoded, debugging)
- **Método**: Busca por keywords
- **Retorna**: `rag_result`

### Nó 3: llm_review_node
- **Responsabilidade**: Parecer qualitativo do LLM
- **Ferramenta**: `ChatGroq` (Groq API)
- **Modelo**: `groq/compound-mini` (configurável)
- **Entrada**: Código + issues + RAG + contexto extra
- **Retorna**: `parecer_llm`

### Nó 3b: save_history_node
- **Responsabilidade**: Salvar histórico de interações
- **Retorna**: `historico_interacoes`

### Nó 4: generate_report_node
- **Responsabilidade**: Gerar relatório final em Markdown
- **Retorna**: `relatorio_final`

---

## 7. Políticas de Autonomia

### Níveis de Autonomia

| Nível | Valor | Descrição |
|-------|-------|-----------|
| AUTO | 0 | Executa sem intervenção (análise estática, leitura) |
| MONITORED | 1 | Com monitoramento (LLM review ≤ 5000 tokens) |
| APPROVED | 2 | Requer aprovação (LLM review > 5000 tokens) |
| BLOCKED | 3 | Bloqueado (execute_sql, delete_file, deploy) |

### Custos Estimados

| Ação | Custo (tokens) | Nível |
|------|----------------|-------|
| read_file | 0 | AUTO |
| static_analysis | 0 | AUTO |
| complexity_analysis | 0 | AUTO |
| rag_retrieval | 0 | AUTO |
| llm_review | 1500 | MONITORED |
| get_best_practices | 0 | AUTO |
| generate_report | 0 | AUTO |

---

## 8. Integrações Externas

### Groq API
- **Wrapper**: `langchain-groq`
- **Modelo padrão**: `groq/compound-mini`
- **Configuração**: `GROQ_API_KEY` via `.env`
- **Timeout**: 30 segundos
- **Retry**: 2 tentativas + backoff exponencial
- **Circuit breaker**: Abre após 3 falhas

### Anthropic API (Fallback)
- **Modelo**: `claude-3-5-sonnet-20240620`
- **Configuração**: `ANTHROPIC_API_KEY` via `.env`
- **Uso**: Quando Groq falha

---

## 9. Observabilidade

### Logs Estruturados
```json
{
  "timestamp": "2026-08-26T00:00:00+00:00",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "uuid",
  "message": "Início do nó read_file_node",
  "metadata": {
    "caminho_arquivo": "examples/input_example.sql"
  }
}
```

### Métricas
- `read_file.success` / `read_file.error`
- `static_analysis.nodes` (número de issues)
- `complexity_ciclomatica` (gauge)
- `llm_review.duration` (timing)

### Traces
- Cada nó gera spans com `start_time`, `end_time`, `duration_ms`, `status`

---

## 10. Estratégia RAG

### Base de Documentação

| ID | Título | Tópico | Score Base |
|----|--------|--------|------------|
| `doc_exception_001` | Tratamento de Exceções WHEN OTHERS | exception_handling | 0.90 |
| `doc_cursor_001` | Tratamento de Cursor e NO_DATA_FOUND | cursor_handling | 0.85 |
| `doc_transaction_001` | Controle de Transações e COMMIT | transaction_control | 0.88 |
| `doc_select_001` | Evitar SELECT * em PL/SQL | performance | 0.82 |
| `doc_hardcoded_001` | Valores Hardcoded em PL/SQL | configuracao | 0.75 |
| `doc_debug_001` | Debugging e Logging em PL/SQL | debugging | 0.70 |

### Algoritmo de Recuperação

1. **Extrair keywords** do código, issues, contexto extra e histórico
2. **Buscar documentos** com matches nas keywords
3. **Calcular score**: `score_base + (matches * 0.05)`
4. **Filtrar** por `score_final > 0.3`
5. **Ordenar** por score decrescente

### Resultado

```python
{
    "documentos": [...],
    "queries": ["WHEN OTHERS", "SELECT *", "COMMIT"],
    "score": 0.83
}
```

---

## 11. Configuração

### Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `GROQ_API_KEY` | Sim | Chave da API Groq |
| `REVIEWER_MODEL` | Não | Modelo a usar (padrão: `groq/compound-mini`) |

### Arquivo .env

```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxx
REVIEWER_MODEL=groq/compound-mini
```

---

## 12. Fluxo Completo

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. CLI (agent/main.py)                                               │
│    - Parse args: arquivo, --saida                                    │
│    - Invoke grafo com caminho_arquivo                                │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. read_file_node                                                    │
│    - read_sql_file(caminho_arquivo)                                  │
│    - Valida extensão, tamanho, caminho                               │
│    - Retorna código_fonte                                            │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. [heuristic_check, complexity_check, rag_retrieval] (paralelo)    │
│    - heuristic_check: run_static_checks                              │
│    - complexity_check: contagem de decisões                          │
│    - rag_retrieval: PLSQLRetriever.retrieve                          │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 4. llm_review_node                                                   │
│    - Validar autonomia                                               │
│    - Call ChatGroq com:                                              │
│      * SYSTEM_PROMPT                                                 │
│      * Código + issues + RAG + contexto                              │
│    - Timeout 30s, retry 2x, circuit breaker                          │
│    - Retorna parecer_llm                                             │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 5. save_history_node                                                 │
│    - Adicionar parecer_llm ao histórico                              │
│    - Retorna historico_interacoes                                    │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 6. generate_report_node                                              │
│    - Montar relatório Markdown                                       │
│    - Incluir: issues, complexidade, recomendações, parecer           │
│    - Retorna relatorio_final                                         │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 7. CLI                                                               │
│    - Salvar relatorio_final no arquivo ou imprimir                   │
│    - Exit com código 0 (sucesso) ou 1 (erro)                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 13. Testes

### Tipos de Teste
- **Security tests**: Prompt injection, sanitização, validação de permissões
- **Agent tests**: Nós do grafo, transições, ramificações condicionais
- **Integration tests**: Circuit breaker, retry, timeout, fallback
- **Acceptance tests**: Comportamento esperado do usuário final
- **E2E tests**: Fluxo completo com integrações reais

### Comando
```bash
pytest tests/ -v --tb=short
```

---

## 14. Troubleshooting

### Erro: Rate Limit Exceeded (429)
- **Causa**: Cota de tokens da API Groq esgotada
- **Solução**: Aguardar 27 minutos ou reduzir `max_tokens`

### Erro: Nenhum provedor de API disponível
- **Causa**: `GROQ_API_KEY` não configurada
- **Solução**: Configurar `.env` com chave válida

### Erro: Arquivo não encontrado
- **Causa**: Caminho incorreto ou arquivo inexistente
- **Solução**: Verificar caminho e permissões

### Erro: Extensão não permitida
- **Causa**: Arquivo não tem extensão PL/SQL válida
- **Solução**: Usar `.sql`, `.pck`, `.pkb`, `.pks`, `.prc`, `.fnc`

---

**Documentação gerada por IA** | 26 de agosto de 2026

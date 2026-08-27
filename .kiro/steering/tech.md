# Tech - Agente Revisor de PL/SQL

## Stack

| Camada | Tecnologia | Motivo |
|--------|-----------|--------|
| Linguagem | Python 3.12+ | Linguagem do módulo; boa integração com LangGraph |
| Orquestração do agente | [LangGraph](https://github.com/langchain-ai/langgraph) | Modela o fluxo como grafo de estados com estado compartilhado |
| Integração com LLM | [langchain-groq](https://pypi.org/project/langchain-groq/) | Wrapper oficial do LangChain para API da Groq |
| Modelo de LLM | `groq/compound-mini` (padrão) | Alta performance, baixa latência, custo acessível |
| Análise estática | `re` (regex, stdlib) | Suficiente para heurísticas simples do escopo |
| CLI | `argparse` (stdlib) | Simples, sem dependências extras |
| Configuração | `python-dotenv` | Carregamento de variáveis de ambiente |

## Dependências (`requirements.txt`)

```
langgraph>=0.2.0
langchain-groq>=0.1.0
python-dotenv>=1.0.0
```

Demais dependências (`os`, `re`, `argparse`, `typing`) são da stdlib.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `GROQ_API_KEY` | Sim | Chave da API Groq (obtida em https://console.groq.com/keys) |
| `REVIEWER_MODEL` | Não | Modelo a usar. Padrão: `groq/compound-mini` |

## Como rodar

```bash
pip install -r requirements.txt
cp .env.example .env
# edite .env com sua GROQ_API_KEY

python -m agent.main examples/input_example.sql
python -m agent.main examples/input_example.sql --saida relatorio.md
```

## Arquitetura

O agente usa LangGraph com 7 nós:

1. **read_file_node**: Lê arquivo com validação de extensão/tamanho/permissões
2. **heuristic_check**: Aplica heurísticas regex (6 regras)
3. **complexity_check**: Calcula complexidade ciclomática
4. **rag_retrieval**: Recupera documentação Oracle PL/SQL via RAG
5. **llm_review_node**: Envia código+achados+RAG para Groq
6. **save_history**: Salva histórico de interações
7. **generate_report_node**: Monta relatório Markdown

### Fluxo paralelo

```
read_file -> [heuristic_check, complexity_check, rag_retrieval] (paralelo)
             ↓
        llm_review (decisão do modelo)
             ↓
        save_history
             ↓
        generate_report
```

## Limites e proteções

- **Extensões permitidas**: `.sql`, `.pck`, `.pkb`, `.pks`, `.prc`, `.fnc`
- **Tamanho máximo**: 500KB (`TAMANHO_MAXIMO_BYTES`)
- **max_tokens LLM**: 1500 (limita custo)
- **API key**: Nunca versionada (`.env` no `.gitignore`)
- **Caminhos protegidos**: `/etc`, `/root`, `/home`, etc. (não acessíveis)
- **Validação de API Key**: Formato `gsk_...` antes de usar

## Regras de análise estática

6 regras implementadas via regex:

| Severidade | Padrão | Descrição |
|------------|--------|-----------|
| alta | `WHEN OTHERS` sem `RAISE` | Exceção silenciosa |
| média | `SELECT *` | Colunas não explícitas |
| média | `COMMIT` interno | Controle transacional |
| baixa | Cursor declarado | Falta tratamento NO_DATA_FOUND |
| baixa | Valor hardcoded | String literal comparada |
| baixa | Bloco `EXCEPTION` | Tratamento genérico |

## Complexidade ciclomática

Calculada contando pontos de decisão:
- IF, ELSIF, ELSE, CASE, WHEN, LOOP, FOR, WHILE
- Fórmula: 1 + número de decisões

## Recuperação de contexto (RAG)

**Base de 6 documentos Oracle PL/SQL:**
- Tratamento de Exceções WHEN OTHERS
- Tratamento de Cursor e NO_DATA_FOUND
- Controle de Transações e COMMIT
- Evitar SELECT * em PL/SQL
- Valores Hardcoded em PL/SQL
- Debugging e Logging em PL/SQL

**Recuperação por keywords** com score dinâmico baseado em matches.

## Autonomia

| Nível | Valor | Ação |
|-------|-------|------|
| AUTO | 0 | Executa automaticamente (leitura, análise estática) |
| MONITORED | 1 | Com monitoramento (LLM review: 1500 tokens) |
| APPROVED | 2 | Requer aprovação (deploy, modificações) |
| BLOCKED | 3 | Bloqueado (execute_sql, delete_file, deploy_production) |

## Segurança

- **Validação de caminho**: impede acesso a diretórios protegidos
- **Validação de API Key**: verifica formato (`gsk_...`) antes de usar
- **Validação de payload**: valida schema das tools
- **Sanitização**: remove segredos de logs e outputs
- **Autonomia**: cada ação tem nível definido

## Decisões técnicas

- **LangGraph vs LLMChain**: Estado explícito facilita debugging e expansão
- **Regex vs Parser PL/SQL**: Escopo didático, regex é suficiente
- **Groq vs Anthropic**: Groq tem menor latência para este caso de uso
- **RAG vs Parser PL/SQL**: Busca por keywords é suficiente para documentação estática
- **Paralelização**: `heuristic_check`, `complexity_check` e `rag_retrieval` rodam em paralelo após `read_file`
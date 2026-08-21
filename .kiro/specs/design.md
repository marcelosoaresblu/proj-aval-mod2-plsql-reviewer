# Design - Agente Revisor de PL/SQL

## Visão Geral

O agente é construído usando **LangGraph**, uma biblioteca para criar agentes com estado e fluxo declarativo. O sistema segue o padrão **State-Graph** , onde cada etapa do processo é um "nó" que transforma o estado compartilhado.

O agente combina três camadas de análise:
1. **Regras determinísticas** (regex/heurísticas): rápido, sem custo de API, detecta padrões conhecidos
2. **RAG** (recuperação de contexto): busca documentação Oracle PL/SQL baseada no código
3. **Decisão do modelo (LLM)**: interpretação contextual, confirma/descarta achados, sugere melhorias

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Agent State (contexto)                        │
│  - caminho_arquivo                                                    │
│  - session_id                                                         │
│  - contexto_extra                                                     │
│  - historico_interacoes                                               │
│  - codigo_fonte                                                       │
│  - issues_estaticos                                                   │
│  - complexidade_ciclomatica                                           │
│  - rag_result                                                         │
│  - parecer_llm                                                        │
│  - relatorio_final                                                    │
│  - erro                                                               │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     ┌────────┐      ┌──────────┐    ┌──────────┐
     │ read_  │─────▶│ heuristi │───▶│  RAG     │
     │ file   │      │ c_check  │    │ retrieval│
     └────────┘      └──────────┘    └──────────┘
          │                │               │
          ▼                ▼               ▼
     ┌────────┐      ┌──────────┐    ┌──────────┐
     │ Lee    │      │ Aplica   │    │ Recupera │
     │ arquivo│      │ heurísticas│  │ context  │
     │ com    │      │ (regex)    │  │ Oracle   │
     │ valid. │      │            │    │ docs     │
     └────────┘      └──────────┘    └──────────┘
                │               │
                ▼               ▼
         ┌──────────┐    ┌──────────┐
         │complexi  │    │ llm    │
         │ty_check  │    │ review   │
         └──────────┘    └──────────┘
                │               │
                ▼               ▼
         ┌──────────┐    ┌──────────┐
         │Cont. decis │   │ Envia    │
         │ões (regex) │   │ código+  │
         │            │   │ achados  │
         │            │   │ ao LLM   │
         │            │   │ + RAG    │
         │            │   │ + context│
         │            │   │          │
         │            │   │          │
         │            │   │          │
         │            │   │          │
         └──────────┘    └────┬─────┘
                              │
                              ▼
                       ┌──────────┐
                       │save_hist │
                       │ory      │
                       └────┬─────┘
                              │
                              ▼
                       ┌──────────┐
                       │ generate │
                       │ report   │
                       └──────────┘
                              │
                              ▼
                       ┌──────────┐
                       │ Monta    │
                       │ Markdown │
                       │ final    │
                       └──────────┘
```

## Componentes

### 1. State (`agent/state.py`)

**TypedDict** que define o contrato de dados entre nós:

- **Entrada:**
  - `caminho_arquivo`: caminho do arquivo PL/SQL
  - `session_id`: ID da sessão para persistência
  - `contexto_extra`: configurações extra (ex: preferências do time)

- **Saída dos nós determinísticos:**
  - `codigo_fonte`: conteúdo do arquivo lido
  - `issues_estaticos`: lista de achados da análise heurística
  - `complexidade_ciclomatica`: estimativa de complexidade
  - `rag_result`: resultados da recuperação de contexto RAG

- **Saída dos nós de decisão:**
  - `parecer_llm`: parecer qualitativo do LLM

- **Saída final:**
  - `relatorio_final`: relatório em Markdown
  - `historico_interacoes`: histórico de mensagens para persistência

- **Controle de erros:**
  - `erro`: mensagem de erro em qualquer estágio

### 2. Tools (`agent/tools.py`)

Ferramentas utilitárias:

- `read_sql_file(caminho)`: Lê arquivo com validações de extensão e tamanho
- `run_static_checks(codigo)`: Aplica regex patterns e retorna lista de issues
- `get_best_practices(achado)`: Obtém boas práticas Oracle PL/SQL
- `get_best_practices_with_auth(achado)`: Wrapper com validação de permissão

**Regras de análise estática (heurísticas):**
1. `WHEN OTHERS` sem `RAISE` → alta (exceção silenciosa)
2. Cursor declarado → baixa (falta tratamento de exceções)
3. `SELECT *` → média (colunas não explícitas)
4. `COMMIT` explícito → média (controle transacional)
5. Valor hardcoded → baixa (string literal comparada)
6. Bloco `EXCEPTION` → baixa (tratamento genérico)

**Complexidade ciclomática:**
- Conta decisões: IF, ELSIF, ELSE, CASE, WHEN, LOOP, FOR, WHILE
- Fórmula: 1 + número de decisões

### 3. RAG (`agent/retriever.py`)

Recuperação de contexto via RAG:

- `PLSQLRetriever`: Busca documentação Oracle PL/SQL baseada no código
- Considera: código, achados, contexto_extra, histórico_interacoes
- Retorna: documentos relevantes, queries, score médio

**Documentação incluída:**
- Tratamento de exceções WHEN OTHERS
- Tratamento de Cursor e NO_DATA_FOUND
- Controle de Transações e COMMIT
- Evitar SELECT * em PL/SQL
- Valores Hardcoded em PL/SQL
- Debugging e Logging em PL/SQL

### 4. Autorização (`agent/autonomy.py`)

Política de limites de autonomia:

- **AUTO**: Ações seguras, sem custo, sem risco (leitura de arquivo, análise estática)
- **MONITORED**: Ações com custo baixo ou risco moderado (LLM review)
- **APPROVED**: Ações com custo alto ou risco significativo (deploy, modificações)
- **BLOCKED**: Ações proibidas (execute_sql, delete_file, deploy_production)

**Validações:**
- `check_file_access()`: Valida que o caminho não é protegido
- `check_api_access()`: Valida que a chave API existe e é válida
- `validate_input_payload()`: Valida o schema do payload de entrada
- `mask_secrets_in_state()`: Remove segredos do estado antes de usar
- `sanitize_output()`: Remove segredos do output antes de exibir

### 5. Graph (`agent/graph.py`)

Define o fluxo como grafo de estados:

```
read_file -> [heuristic_check, complexity_check, rag_retrieval] (paralelo)
             ↓
        llm_review (decisão do modelo)
             ↓
        save_history (persistência)
             ↓
        generate_report
```

**Nós:**
- `read_file_node`: Leitura e validação de arquivo (com autorização)
- `heuristic_check`: Análise determinística via regex
- `complexity_check`: Análise de complexidade ciclomática
- `rag_retrieval`: Recuperação de contexto RAG
- `llm_review`: Análise qualitativa com Groq
- `save_history`: Salva histórico de interações
- `generate_report`: Montagem do relatório final

**Ramificações condicionais:**
- Se erro no `read_file`: pula direto para `generate_report`
- Se erro no `llm_review`: pula para `generate_report`

### 6. Main (`agent/main.py`)

CLI de entrada:

```bash
python -m agent.main examples/input_example.sql [--saida relatorio.md]
```

## Integração com LLM

- **API Provider**: Groq (`langchain-groq`)
- **Modelo**: Configurável via `REVIEWER_MODEL` (padrão: `llama-3.3-70b-versatile`)
- **Tokens máximos**: 1500 (para limitar custo)
- **Prompt**: System prompt + código SQL + achados estáticos + contexto RAG + contexto extra

## Tratamento de Erros

- Qualquer nó pode detectar erro e preencher `erro` no estado
- Nós subsequentes verificam `erro` e não executam se houver erro
- Relatório final inclui mensagem de erro se ocorrer
- Parada antecipada: se erro no `read_file`, pula direto para `generate_report`

## Extensibilidade

### Adicionar nova regra estática

```python
# Em agent/tools.py, adicione à lista REGRAS:
(
    re.compile(r"padrao_regex"),
    "severidade",  # "alta", "media", "baixa"
    "Descrição do problema"
)
```

### Adicionar novo nó ao fluxo

```python
# Em agent/graph.py:
def novo_nodo(state: AgentState) -> dict:
    # lógica do novo nó
    pass

graph.add_node("novo_nodo", novo_nodo)
graph.add_edge("nodo_anterior", "novo_nodo")
graph.add_edge("novo_nodo", "proximo_nodo")
```

### Adicionar nova fonte RAG

```python
# Em agent/retriever.py, adicione ao docs_db:
{
    "id": "doc_novo",
    "titulo": "Título",
    "topico": "topico",
    "conteudo": "Documentação...",
    "keywords": ["kw1", "kw2"],
    "relevancia_base": 0.8,
}
```

## Segurança

- **Validação de extensão**: allowlist explícita (.sql, .pck, .pkb, .pks, .prc, .fnc)
- **Validação de tamanho**: 500KB máximo
- **Validação de caminho**: impede acesso a diretórios protegidos (/etc, /root, etc.)
- **Validação de API Key**: verifica formato (gsk_...) antes de usar
- **API Key**: Variável de ambiente (.env), nunca hardcoded
- **max_tokens**: Limita custo por chamada (1500 tokens)
- **Sanitização de saída**: remove segredos de logs e outputs
- **Autonomia**: cada ação tem nível definido (AUTO, MONITORED, APPROVED, BLOCKED)
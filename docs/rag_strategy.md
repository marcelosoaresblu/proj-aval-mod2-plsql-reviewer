# Estratégia RAG — Agente Revisor de PL/SQL

## Visão Geral 

O agente utiliza **RAG (Retrieval-Augmented Generation)** para enriquecer o contexto do modelo de linguagem com documentação Oracle PL/SQL e boas práticas específicas do domínio ERP/PCP/MRP.

---

## Base de Documentação

A base de conhecimento consiste em **6 documentos** cobrindo os principais tópicos de boas práticas PL/SQL:

| ID | Título | Tópico | Score Base | Fonte |
|----|--------|--------|------------|-------|
| `doc_exception_001` | Tratamento de Exceções WHEN OTHERS | `exception_handling` | 0.90 | Oracle PL/SQL Best Practices |
| `doc_cursor_001` | Tratamento de Cursor e NO_DATA_FOUND | `cursor_handling` | 0.85 | Oracle PL/SQL User's Guide |
| `doc_transaction_001` | Controle de Transações e COMMIT | `transaction_control` | 0.88 | Oracle PL/SQL Best Practices |
| `doc_select_001` | Evitar SELECT * em PL/SQL | `performance` | 0.82 | Oracle SQL Tuning Guide |
| `doc_hardcoded_001` | Valores Hardcoded em PL/SQL | `configuracao` | 0.75 | Oracle PL/SQL Code Review Guidelines |
| `doc_debug_001` | Debugging e Logging em PL/SQL | `debugging` | 0.70 | Oracle PL/SQL Best Practices |

### Formato dos Documentos

Cada documento contém:
- **ID único** (`id`)
- **Título** (`titulo`)
- **Tópico** (`topico`) — categoria da documentação
- **Conteúdo** (`conteudo`) — explicação + exemplo problemático + exemplo corrigido
- **Keywords** (`keywords`) — termos relevantes para busca
- **Score base** (`relevancia_base`) — pontuação inicial de relevância (0-1)

### Fontes Originais

As informações são derivadas da documentação oficial Oracle:
- **Oracle PL/SQL Language Reference**
- **Oracle Database Application Developer's Guide**
- **Oracle SQL Tuning Guide**
- **Oracle Database PL/SQL Best Practices**

Em produção, esses documentos seriam armazenados em um **vector store** (ex: Chroma, FAISS, Pinecone).

---

## Chunking

A estratégia de chunking é **baseada em tópicos** — cada documento representa um chunk lógico autossuficiente.

### Características

- **Tipo**: Chunking estático por documento completo
- **Tamanho médio**: 200-300 tokens por documento
- **Estratégia**: Nenhum chunking adicional (cada documento já é um chunk)
- **Overlap**: Não aplicável (documentos são independentes)

### Justificativa

Para o domínio PL/SQL:
- Os documentos são curtos e focados (um tópico por documento)
- Não há necessidade de chunking fragmentado
- A recuperação por keywords é suficiente para o escopo

### Estrutura de Chunk

```python
chunk = {
    "id": "doc_exception_001",
    "metadata": {
        "topico": "exception_handling",
        "relevancia_base": 0.9
    },
    "content": """Texto completo com explicação e exemplos"""
}
```

---

## Indexação

A indexação é **baseada em keywords** com meta-informações.

### Estratégia

1. **Extração de keywords** de cada documento
2. **Índice invertido** simples: `keyword -> [document_ids]`
3. **Metadados** associados: tópico, score base

### Exemplo de Índice

```python
{
    "WHEN OTHERS": ["doc_exception_001"],
    "exception": ["doc_exception_001"],
    "raise": ["doc_exception_001"],
    "null": ["doc_exception_001"],
    "error": ["doc_exception_001"],
    "CURSOR": ["doc_cursor_001"],
    "NO_DATA_FOUND": ["doc_cursor_001"],
    # ... mais keywords
}
```

### Em Produção

Para escala maior, substituir por:
- **Vector embeddings** (ex: OpenAI embeddings, Cohere embeddings)
- **Vector store** (ex: Chroma, FAISS, Pinecone)
- **Hybrid search** (keywords + semântico)

---

## Recuperação

A recuperação combina **busca por keywords** com **heurísticas de relevância**.

### Algoritmo

1. **Extrair keywords** do código e achados:
   - Código PL/SQL → padrões regex (WHEN OTHERS, SELECT *, COMMIT, etc.)
   - Achados estáticos → análise do texto da regra
   - Contexto extra → keywords definidas pelo usuário
   - Histórico → keywords de perguntas anteriores

2. **Buscar documentos**:
   - Para cada documento, contar matches com keywords
   - Calcular score final: `score_base + (matches * 0.05)`

3. **Filtrar por threshold**:
   - Manter apenas documentos com `score_final > 0.3`

4. **Ordenar por score**:
   - Mais relevantes primeiro

### Código de Recuperação

```python
def retrieve(self, codigo, issues, contexto_extra=None, historico=None):
    # 1. Extrair keywords
    keywords = self._extrair_keywords(codigo)
    keywords += self._extrair_keywords_dos_achados(issues)
    keywords += self._extrair_keywords_do_contexto(contexto_extra)
    keywords += self._extrair_keywords_do_historico(historico)
    
    # 2. Buscar documentos
    for doc in self._docs_db:
        matches = sum(1 for kw in keywords if kw in doc["keywords"])
        score = doc["relevancia_base"] + (matches * 0.05)
        if score > 0.3:
            documentos.append(doc)
    
    # 3. Ordenar
    documentos.sort(key=lambda x: x["score"], reverse=True)
    
    return documentos
```

### Resultado da Recuperação

```python
{
    "documentos": [
        {
            "id": "doc_exception_001",
            "titulo": "Tratamento de Exceções WHEN OTHERS",
            "topico": "exception_handling",
            "conteudo": "...",
            "score": 0.95
        },
        # ... mais documentos
    ],
    "queries": ["WHEN OTHERS", "SELECT *", "COMMIT"],  # Top 5 queries
    "score": 0.83  # Score médio
}
```

---

## Fontes Externas

### 1. Documentação Oracle PL/SQL (RAG)

| Fonte | Tipo | Recuperação | Atualização |
|-------|------|-------------|-------------|
| Oracle PL/SQL Language Reference | Documentação oficial | Manual | Manual |
| Oracle Database Application Developer's Guide | Documentação oficial | Manual | Manual |
| Oracle SQL Tuning Guide | Documentação oficial | Manual | Manual |

**Como recuperadas:**
- Atualmente: Documentos estáticos no código (`PLSQLRetriever._docs_db`)
- Em produção: Vector store (Chroma, FAISS) com embeddings

**Frequency of updates:** Mensal (revisão manual da documentação)

---

### 2. Boas Práticas (Tools)

| Fonte | Tipo | Recuperação | Atualização |
|-------|------|-------------|-------------|
| `get_best_practices(achado)` | API simulada | In-memory DB | Manual |

**Como recuperadas:**
- Database estático em `agent/tools.py`
- Mapeia achados para recomendações Oracle

**Exemplos:**
- `WHEN_OTHERS_SILENT` → Recomendação com RAISE
- `SELECT_STAR` → Recomendação com colunas explícitas

**Frequency of updates:** Sob demanda (nova regra adicionada)

---

### 3. API Groq (LLM)

| Fonte | Tipo | Recuperação | Atualização |
|-------|------|-------------|-------------|
| `groq/compound-mini` | LLM | API | Automática |

**Como recuperadas:**
- `langchain-groq` wrapper
- `ChatGroq(model=MODEL_NAME, max_tokens=1500)`

**Frequency of updates:** Automática (versão do modelo)

---

### 4. Arquivo Local (Input)

| Fonte | Tipo | Recuperação | Atualização |
|-------|------|-------------|-------------|
| `read_sql_file(caminho)` | Local file system | Python `open()` | Manual |

**Como recuperadas:**
- Validação de extensão (`.sql`, `.pck`, `.pkb`, `.pks`, `.prc`, `.fnc`)
- Validação de tamanho (< 500KB)
- Leitura com encoding UTF-8

**Frequency of updates:** Por execução

---

## Pipeline Completo

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. READ FILE (read_sql_file)                                    │
│    - Valida extensão, tamanho                                    │
│    - Lê código PL/SQL                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. STATIC ANALYSIS (run_static_checks)                          │
│    - Heurísticas regex (WHEN OTHERS, SELECT *, etc.)            │
│    - Retorna lista de issues                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. RAG RETRIEVAL (PLSQLRetriever.retrieve)                      │
│    - Extrai keywords do código + issues                         │
│    - Considera contexto_extra e historico                       │
│    - Busca documentos relevantes                                │
│    - Retorna documentos + queries + score                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. LLM REVIEW (ChatGroq.invoke)                                 │
│    - Prompt com:                                                 │
│      * Código PL/SQL                                             │
│      * Issues estáticas                                          │
│      * Documentação RAG                                          │
│      * Contexto extra                                            │
│    - Gera parecer qualitativo                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. GENERATE REPORT (generate_report_node)                       │
│    - Formata relatório Markdown                                 │
│    - Inclui issues, complexidade, recomendações, parecer LLM   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Próximos Passos para Produção

1. **Vector Store**: Substituir busca por keywords por embeddings semânticos
2. **Cache**: Adicionar cache para documentos recuperados (Redis/Memcached)
3. **Monitoring**: Monitorar hit rate, latência, e qualidade das recomendações
4. **Feedback Loop**: Coletar feedback de usuários para melhorar o RAG
5. **Dynamic Updates**: Permitir atualização da base de conhecimento sem redeploy

---

## Referências

- [Oracle PL/SQL Language Reference](https://docs.oracle.com/en/database/oracle/oracle-database/)
- [Oracle SQL Tuning Guide](https://docs.oracle.com/en/database/oracle/oracle-database/)
- [LangChain RAG Tutorial](https://python.langchain.com/docs/tutorials/rag/)
- [Chroma Vector Database](https://www.trychroma.com/)
- [FAISS Facebook AI Similarity Search](https://ai.meta.com/tech/faiss/)

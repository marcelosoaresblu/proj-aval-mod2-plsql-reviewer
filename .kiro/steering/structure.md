# Structure - Agente Revisor de PL/SQL

## Layout do repositório

```
plsql-reviewer/
├── README.md                    # documentação principal do projeto
├── requirements.txt              # dependências Python
├── .gitignore                    # protege .env e artefatos locais
│
├── agent/                        # código-fonte do agente
│   ├── __init__.py              # inicialização e carregamento de .env
│   ├── state.py                  # AgentState (estado/memória do grafo)
│   ├── tools.py                  # ferramentas: leitura, análise, boas práticas
│   ├── graph.py                  # definição e montagem do grafo LangGraph
│   ├── retriever.py              # RAG: recuperação de contexto Oracle PL/SQL
│   ├── autonomy.py               # políticas de autonomia e validação de permissões
│   ├── authorization.py          # validação de permissões e sanitização
│   └── main.py                   # CLI de execução
│
├── docs/                         # documentação técnica
│   ├── prompts.md                # prompts usados com o LLM
│   └── rag_strategy.md           # estratégia RAG (base, chunking, indexação, recuperação)
│
├── examples/                     # exemplos de entrada/saída
│   ├── input_example.sql        # PL/SQL com problemas propositais
│   └── output_example.md        # relatório gerado pelo agente
│
├── .kiro/                        # configuração do Kiro
│   ├── specs/                    # especificação do projeto
│   │   ├── requirements.md       # requisitos funcionais e não-funcionais
│   │   ├── design.md             # design document da arquitetura
│   │   └── tasks.md              # lista de tarefas e roadmap
│   └── steering/                 # orientação do projeto
│       ├── product.md            # visão de produto
│       ├── structure.md          # este arquivo
│       └── tech.md               # detalhes técnicos
│
└── CONTRIBUTING.md               # guia de contribuição
```

## Convenções de código

- **Idioma:** código (nomes de função, variáveis) em inglês/português misto conforme já estabelecido no projeto (ex.: `read_sql_file`, `codigo_fonte`, `caminho_arquivo`) — prioriza-se clareza sobre padronização estrita de idioma, já que o domínio (PL/SQL, ERP) é tratado em português nos comentários e docstrings.
- **Docstrings:** todo módulo e função pública tem docstring em português explicando responsabilidade e comportamento.
- **Nós do grafo:** cada nó é uma função pura de `AgentState` para um `dict` parcial — não há efeitos colaterais além de chamadas às ferramentas explicitamente importadas.
- **Ferramentas:** vivem exclusivamente em `agent/tools.py`, nunca implementadas inline dentro de um nó.
- **Validação de permissões:** todos os nós chamam funções de autorização antes de executar ações externas.
- **Autonomia:** cada ação tem nível definido (AUTO, MONITORED, APPROVED, BLOCKED).

## Módulos do agente

| Módulo | Responsabilidade |
|--------|------------------|
| `agent/state.py` | TypedDict `AgentState` com todos os campos do estado |
| `agent/tools.py` | Ferramentas: `read_sql_file`, `run_static_checks`, `get_best_practices` |
| `agent/graph.py` | Definição do grafo LangGraph com 7 nós |
| `agent/retriever.py` | `PLSQLRetriever` para RAG com 6 documentos Oracle PL/SQL |
| `agent/autonomy.py` | Políticas de autonomia (4 níveis) e validação de custo |
| `agent/authorization.py` | Validação de permissões e sanitização de segredos |
| `agent/main.py` | CLI de execução com argparse |

## Convenções de commits

Para manter evidência rastreável de participação, os commits devem:

- Ser incrementais (um commit por etapa/funcionalidade, não um único commit final com tudo).
- Ter mensagens descritivas no formato `<tipo>: <descrição>` usando Conventional Commits:
  - `feat: adiciona nova regra de análise estática`
  - `fix: corrige validação de extensão de arquivo`
  - `docs: atualiza README com novos exemplos`
  - `refactor: extrai lógica de análise para função separada`
  - `perf: melhora performance da análise estática`
  - `sec: adiciona validação de permissões`

## Convenções de código

- **Idioma:** código (nomes de função, variáveis) em inglês/português misto conforme já estabelecido no projeto (ex.: `read_sql_file`, `codigo_fonte`) — prioriza-se clareza sobre padronização estrita de idioma, já que o domínio (PL/SQL, ERP) é tratado em português nos comentários e docstrings.
- **Docstrings:** todo módulo e função pública tem docstring em português explicando responsabilidade e comportamento.
- **Nós do grafo:** cada nó é uma função pura de `AgentState` para um `dict` parcial — não há efeitos colaterais além de chamadas às ferramentas explicitamente importadas.
- **Ferramentas:** vivem exclusivamente em `agent/tools.py`, nunca implementadas inline dentro de um nó.

## Convenções de commits

Para manter evidência rastreável de participação, os commits devem:

- Ser incrementais (um commit por etapa/funcionalidade, não um único commit final com tudo).
- Ter mensagens descritivas no formato `<tipo>: <descrição>` usando Conventional Commits:
  - `feat: adiciona nova regra de análise estática`
  - `fix: corrige validação de extensão de arquivo`
  - `docs: atualiza README com novos exemplos`
  - `refactor: extrai lógica de análise para função separada`
# Agente Revisor de PL/SQL

Agente construído com **LangGraph** que automatiza a revisão de trechos de
código PL/SQL (procedures, functions, packages), identificando riscos
comuns de manutenibilidade e tratamento de erros, e gerando um relatório
técnico estruturado.

## Descrição do problema

Revisar código PL/SQL manualmente — especialmente em sistemas legados de
ERP/PCP/MRP — é repetitivo e propenso a deixar passar problemas comuns
(exceções silenciosas, `SELECT *`, commits mal posicionados, valores
hardcoded). Este agente automatiza uma primeira passada de revisão,
combinando checagens estáticas determinísticas com uma análise
qualitativa feita por LLM.

## Objetivo do agente

- **Entrada:** um arquivo de código PL/SQL (`.sql`, `.pck`, `.pkb`, `.pks`,
  `.prc`, `.fnc`).
- **Processo:** leitura do arquivo → análise estática por heurísticas →
  revisão qualitativa por LLM (com o contexto dos achados estáticos) →
  geração de relatório.
- **Saída:** relatório em Markdown com tabela de achados estáticos
  (linha, severidade, descrição) e parecer do agente com sugestões
  priorizadas de melhoria.

## Fluxo com LangGraph

```
read_file -> static_analysis -> llm_review -> generate_report
```

- **Estado (`AgentState`)**: acumula, durante a execução, o código lido,
  os achados da análise estática, o parecer do LLM e o relatório final.
  Esse estado é o "contexto/memória" que cada nó lê e enriquece.
- **Nós:**
  - `read_file_node`: usa a ferramenta `read_sql_file` para ler o arquivo.
  - `static_analysis_node`: usa a ferramenta `run_static_checks`
    (heurísticas via regex) para gerar achados determinísticos.
  - `llm_review_node`: chama o modelo via API da Groq, passando o código e
    os achados estáticos como contexto, para gerar um parecer qualitativo.
  - `generate_report_node`: monta o relatório final em Markdown.

Por que é um agente, e não um script linear: o fluxo separa claramente
**planejamento** (o que checar), **uso de ferramenta** (leitura de
arquivo + análise estática determinística) e **geração da resposta
final** (síntese do LLM), e o estado carrega contexto acumulado entre
essas etapas — não é uma única chamada de prompt.

## Ferramenta integrada

1. `read_sql_file` — leitura de arquivo, com validação de extensão e
   limite de tamanho (proteção contra abuso).
2. `run_static_checks` — análise de código via regex (cursors sem
   tratamento de exceção, `SELECT *`, `COMMIT` interno, valores
   hardcoded, blocos `WHEN OTHERS` sem `RAISE`).

## Segurança e validação

- A chave de API é lida de variável de ambiente (`GROQ_API_KEY`),
  nunca hardcoded ou versionada (ver `.gitignore`).
- `read_sql_file` só aceita extensões de código PL/SQL conhecidas e
  limita o tamanho do arquivo lido.
- O agente não executa nenhum SQL contra banco de dados — apenas lê e
  analisa texto. Não há ação destrutiva possível.

## Como executar

```bash
pip install -r requirements.txt
cp .env.example .env
# edite o .env e preencha GROQ_API_KEY com sua chave real

python -m agent.main examples/input_example.sql
# ou salvando em arquivo:
python -m agent.main examples/input_example.sql --saida relatorio.md
```

Alternativa sem `.env`, exportando a variável diretamente no shell:

```bash
export GROQ_API_KEY="sua-chave-aqui"
```

## Exemplo de entrada

Ver [`examples/input_example.sql`](examples/input_example.sql) — uma
procedure de atualização de ordem de produção com problemas propositais
(exceção silenciosa, `SELECT *`, commit interno).

## Exemplo de saída

Ver [`examples/output_example.md`](examples/output_example.md) — relatório
gerado pelo agente para o exemplo acima.

## Principais decisões tomadas

- Separar análise estática (rápida, determinística, sem custo de API) da
  análise via LLM (mais cara, mas qualitativa) — a estática alimenta o
  contexto da LLM, reduzindo alucinação e custo de tokens.
- Usar heurísticas simples (regex) em vez de um parser PL/SQL completo,
  por ser suficiente para o escopo do mini-projeto e manter o código
  legível.
- Modelo do LLM configurável via variável de ambiente `REVIEWER_MODEL`
  (padrão: `groq/compound-mini`), para não travar o projeto a um modelo específico.

## Limitações

- As regras estáticas são heurísticas simples (regex), não um parser
  PL/SQL real — podem gerar falsos positivos/negativos.
- O agente revisa um arquivo por vez; não analisa dependências entre
  múltiplos objetos do banco.
- O parecer do LLM depende da qualidade do modelo configurado e não
  substitui revisão humana em código crítico de produção.
- A base de documentação RAG é atualmente estática (simulada); em
  produção, seria substituída por um vector store com embeddings semânticos.

## Prompts utilizados

Ver [`docs/prompts.md`](docs/prompts.md).

## Estratégia RAG

O agente utiliza **RAG (Retrieval-Augmented Generation)** para enriquecer o contexto do modelo com documentação Oracle PL/SQL e boas práticas específicas do domínio ERP/PCP/MRP.

Ver [`docs/rag_strategy.md`](docs/rag_strategy.md) para detalhes sobre:
- Base de documentação (6 documentos sobre exceções, cursores, transações, performance, etc.)
- Chunking, indexação e recuperação por keywords
- Fontes externas e pipelines de recuperação

## Documentação do Sistema

Ver [`docs/sistema.md`](docs/sistema.md) para instruções completas do sistema, incluindo:
- Objetivos da tarefa e regras de comportamento
- Restrições importantes e padrões de resposta
- Prompts relevantes (SYSTEM_PROMPT e prompt do LLM)
- Arquitetura do agente (fluxo LangGraph)
- Políticas de autonomia e integrações externas
- Estratégia RAG e observabilidade
- Configuração e troubleshooting

## Automação com n8n (Low-Code/No-Code)

O agente pode ser orquestrado via **n8n** para integração com sistemas de CI/CD, monitoramento de diretórios ou webhooks.

### Pré-requisitos

- Node.js (v14+)
- n8n instalado globalmente: `npm install -g n8n`
- Discord Webhook URL (opcional, para notificações)

### Configuração Rápida

```bash
# 1. Configurar o wrapper n8n
chmod +x setup_n8n.sh
./setup_n8n.sh

# 2. Iniciar o n8n
cd n8n_workflows
export DISCORD_WEBHOOK_URL="seu_webhook_discord"  # opcional
n8n start --tunnel
```

### Importar Workflow no n8n

1. Acesse `http://localhost:5678`
2. Clique em **"Import from File"**
3. Selecione `n8n_workflows/n8n_workflow.json`
4. Clique no ícone **play** (▶️) no canto superior direito do nó **Webhook Recebedor** para ativar

### Testar via Webhook

```bash
curl -X POST http://localhost:5678/webhook/webhook-plsql-review \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "examples/input_example.sql",
    "output_file": "/tmp/relatorio.md"
  }'
```

**Resposta esperada**:
```
Análise concluída com sucesso!
```

### Usando o Wrapper Python Diretamente

O wrapper `n8n_agent_wrapper.py` pode ser chamado diretamente:

```bash
# Com saída em arquivo
python n8n_agent_wrapper.py examples/input_example.sql --output relatorio.md

# Com saída em JSON (para processamento por outros sistemas)
python n8n_agent_wrapper.py examples/input_example.sql --json
```

### Arquivos do n8n

| Arquivo | Descrição |
|---------|-----------|
| `n8n_agent_wrapper.py` | Wrapper Python para executar o agente |
| `n8n_workflows/n8n_workflow.json` | Workflow com webhook |
| `n8n_workflows/n8n_workflow_watch.json` | Workflow com monitoramento de diretório |
| `n8n_workflows/.env` | Variáveis de ambiente do n8n |

# Requirements - Agente Revisor de PL/SQL

## 1. Objetivo do agente

Automatizar uma primeira passada de revisão de código PL/SQL (procedures,
functions, packages), identificando riscos comuns de manutenibilidade e
tratamento de erros, e produzindo um relatório técnico estruturado com
recomendações baseadas em documentação Oracle PL/SQL.

## 2. Requisitos funcionais

### 2.1 Entrada e Processamento

| ID | Requisito | Status |
|----|-----------|--------|
| RF01 | O agente deve receber como entrada um arquivo de código PL/SQL (`.sql`, `.pck`, `.pkb`, `.pks`, `.prc`, `.fnc`). | ✅ Implementado |
| RF02 | O agente deve ler o conteúdo do arquivo através de uma ferramenta dedicada. | ✅ Implementado (`read_sql_file`) |
| RF03 | O agente deve rodar uma análise estática determinística sobre o código antes de acionar o LLM. | ✅ Implementado (`run_static_checks`) |
| RF04 | O agente deve rodar análise de complexidade ciclomática do código. | ✅ Implementado (`complexity_analysis_node`) |
| RF05 | O agente deve recuperar contexto via RAG baseado no código e achados. | ✅ Implementado (`rag_retrieval_node`) |
| RF06 | O agente deve enviar o código-fonte, achados estáticos e contexto RAG para um LLM gerar um parecer qualitativo. | ✅ Implementado (`llm_review_node`) |
| RF07 | O agente deve gerar um relatório final em Markdown, combinando achados estáticos, recomendações e parecer do LLM. | ✅ Implementado (`generate_report_node`) |
| RF08 | O agente deve poder ser executado via linha de comando, recebendo o caminho do arquivo e, opcionalmente, um caminho de saída. | ✅ Implementado (`agent/main.py`) |

### 2.2 Análise Estática

| ID | Requisito | Status |
|----|-----------|--------|
| RF09 | Detectar `WHEN OTHERS` sem `RAISE` (severidade: alta). | ✅ Implementado |
| RF10 | Detectar cursor declarado sem tratamento de exceção (severidade: baixa). | ✅ Implementado |
| RF11 | Detectar `SELECT *` (severidade: média). | ✅ Implementado |
| RF12 | Detectar `COMMIT` explícito (severidade: média). | ✅ Implementado |
| RF13 | Detectar valor hardcoded (severidade: baixa). | ✅ Implementado |
| RF14 | Detectar bloco `EXCEPTION` presente (severidade: baixa). | ✅ Implementado |
| RF15 | Contar pontos de decisão (IF, ELSIF, ELSE, CASE, WHEN, LOOP, FOR, WHILE) para complexidade ciclomática. | ✅ Implementado |

### 2.3 Contexto RAG

| ID | Requisito | Status |
|----|-----------|--------|
| RF16 | Recuperar documentação Oracle PL/SQL baseada no código (WHEN OTHERS, cursores, transações, performance, configuração, debugging). | ✅ Implementado |
| RF17 | Considerar contexto extra (configurações do time, preferências) ao recuperar documentos. | ✅ Implementado |
| RF18 | Considerar histórico de interações anteriores ao recuperar documentos. | ✅ Implementado |

### 2.4 Saída

| ID | Requisito | Status |
|----|-----------|--------|
| RF19 | Gerar relatório em Markdown com tabela de achados estáticos (linha, severidade, descrição). | ✅ Implementado |
| RF20 | Gerar recomendações de boas práticas Oracle PL/SQL baseadas nos achados. | ✅ Implementado |
| RF21 | Incluir complexidade ciclomática no relatório. | ✅ Implementado |
| RF22 | Incluir parecer qualitativo do LLM no relatório. | ✅ Implementado |

### 2.5 Tratamento de Erros

| ID | Requisito | Status |
|----|-----------|--------|
| RF23 | O agente deve tratar erros de leitura (arquivo inexistente, extensão inválida, arquivo muito grande) sem quebrar o fluxo. | ✅ Implementado (campo `erro` no estado) |
| RF24 | Se erro ocorrer no início, pular direto para geração de relatório de erro. | ✅ Implementado (ramificação condicional) |
| RF25 | Se erro ocorrer no LLM, incluir mensagem de erro no relatório final. | ✅ Implementado |

### 2.6 Autonomia e Segurança

| ID | Requisito | Status |
|----|-----------|--------|
| RF26 | Validar permissão de acesso ao caminho do arquivo (não permitir diretórios protegidos). | ✅ Implementado (`check_file_access`) |
| RF27 | Validar formato da chave de API antes de usá-la. | ✅ Implementado (`check_api_access`) |
| RF28 | Validar schema do payload de entrada das tools. | ✅ Implementado (`validate_input_payload`) |
| RF29 | Sanitizar segredos de outputs e logs. | ✅ Implementado (`sanitize_output`) |
| RF30 | Respeitar níveis de autonomia (AUTO, MONITORED, APPROVED, BLOCKED). | ✅ Implementado (`validate_autonomy`) |

## 3. Requisitos não funcionais

| ID | Requisito | Status |
|----|-----------|--------|
| RNF01 | A chave de API não pode ser versionada no repositório. | ✅ `.gitignore` cobre `.env` |
| RNF02 | O agente não deve executar nenhuma instrução SQL contra um banco de dados — apenas leitura e análise de texto. | ✅ Nenhuma dependência de driver de banco |
| RNF03 | O modelo de LLM usado deve ser configurável, sem hardcode. | ✅ Variável `REVIEWER_MODEL` |
| RNF04 | O tamanho do arquivo de entrada deve ser limitado, como proteção básica contra abuso/custo. | ✅ Limite de 500 KB em `tools.py` |
| RNF05 | O agente deve suportar execução paralela de análise estática (heurísticas + complexidade) e RAG. | ✅ Implementado via LangGraph |
| RNF06 | O agente deve persistir histórico de interações para aprendizado contínuo. | ✅ Implementado (`save_history_node`) |
| RNF07 | O agente deve limitar custo de API por chamada (max_tokens: 1500). | ✅ Implementado no `llm_review_node` |

## 4. Fora de escopo (explicitamente)

- Parsing completo de PL/SQL (uso de parser real/AST) — o projeto usa heurísticas por regex, suficiente para o escopo do mini-projeto.
- Integração com banco de dados Oracle real.
- Interface web — a entrega é via CLI.
- Análise de múltiplos arquivos/dependências entre objetos do banco.
- Checkpointer persistente em banco de dados (apenas memória/volátil no estado atual).

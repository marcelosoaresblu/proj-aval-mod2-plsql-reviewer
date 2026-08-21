# Registro de Prompts 

Este arquivo documenta os principais prompts utilizados para planejar,
implementar e revisar o agente.

## 1. Planejamento do projeto

> Preciso desenvolver um agente com LangGraph para o mini-projeto do
> módulo. Tenho background em PL/SQL, ERP/PCP e MRP. Quais opções de
> agente fazem mais sentido dado esse contexto, considerando os
> requisitos: entrada definida, fluxo com LangGraph, ferramenta
> integrada, uso de contexto/memória e saída útil?

Resultado: escolha do agente revisor de PL/SQL como melhor encaixe com o
domínio de conhecimento do autor.

## 2. Desenho da arquitetura

> Desenhe o fluxo LangGraph para um agente revisor de PL/SQL: quais nós,
> que ferramenta usar, e como estruturar o estado para manter contexto
> entre as etapas.

Resultado: fluxo `read_file -> static_analysis -> llm_review ->
generate_report`, com `AgentState` acumulando código, achados estáticos,
parecer do LLM e relatório final.

## 3. Prompt de sistema do nó `llm_review`

Prompt efetivamente usado no agente (arquivo `agent/graph.py`,
constante `SYSTEM_PROMPT`):

```
Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código e uma lista de
achados de uma análise estática automática (heurísticas simples).

Sua tarefa:
1. Avaliar a qualidade geral do código (legibilidade, tratamento de erros,
   performance, aderência a boas práticas de PL/SQL).
2. Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.
3. Sugerir no máximo 5 melhorias concretas, priorizadas por impacto.

Responda em português, em formato Markdown, de forma objetiva e técnica.
Não invente comportamento do sistema que não esteja no código.
```

Decisão de design: pedir explicitamente para o modelo **confirmar ou
descartar** os achados estáticos, em vez de só listar problemas novos —
isso reduz ruído e mostra o raciocínio do agente sobre os falsos
positivos da análise por regex.

## 4. Correção/ajuste durante implementação

> O parecer do LLM está saindo genérico demais, sem citar as linhas dos
> achados estáticos. Como ajustar o prompt para forçar o modelo a cruzar
> os achados com o código antes de opinar?

Resultado: o prompt de usuário passou a incluir a lista de achados
estáticos formatada (linha, severidade, descrição) junto com o código,
em vez de mandar só o código puro para o LLM.

## 5. Geração dos exemplos de entrada/saída

> Crie um exemplo de procedure PL/SQL de atualização de ordem de
> produção com problemas propositais (exceção silenciosa, SELECT *,
> commit interno) para servir de exemplo de entrada do agente.

Resultado: arquivo `examples/input_example.sql` e o relatório
correspondente em `examples/output_example.md`.

## 6. Troca de provedor de LLM

> Trocar de ANTHROPIC_API_KEY para GROQ_API_KEY e gerar o projeto
> novamente.

Resultado: `agent/graph.py` passou a usar `ChatGroq` (pacote
`langchain-groq`) em vez de `ChatAnthropic`, com o modelo padrão
`llama-3.3-70b-versatile` (configurável via `REVIEWER_MODEL`). Toda a
documentação (`README.md`, `steering/tech.md`, `specs/design.md`,
`specs/tasks.md`) foi atualizada para refletir a nova variável de
ambiente e o novo provedor. Motivo da troca: camada gratuita da Groq
mais generosa para uso em projeto acadêmico.

## 7. Adição de RAG

> Como adicionar recuperação de contexto Oracle PL/SQL ao agente?

Resultado: criação do módulo `agent/retriever.py` com:
- Base de 6 documentos Oracle PL/SQL (exceções, cursores, transações, performance, configuração, debugging)
- Recuperação por keywords baseada no código e achados
- Contexto extra (configurações do time) e histórico de interações

O prompt do LLM agora inclui a seção `=== DOCUMENTAÇÃO ORACLE PL/SQL (RAG) ===` com documentos recuperados.

## 8. Adição de validação de permissões

> Como garantir que o agente não acesse caminhos protegidos ou use API keys inválidas?

Resultado: criação do módulo `agent/authorization.py` com:
- `check_file_access()`: valida que o caminho não é protegido (/etc, /root, etc.)
- `check_api_access()`: valida formato da chave API (gsk_...)
- `validate_input_payload()`: valida schema das tools
- `sanitize_output()`: remove segredos de logs e outputs

## 9. Adição de políticas de autonomia

> Como definir quando o agente pode executar ações automaticamente ou precisa de aprovação?

Resultado: criação do módulo `agent/autonomy.py` com:
- 4 níveis: AUTO (0), MONITORED (1), APPROVED (2), BLOCKED (3)
- Cada ação tem custo estimado (ex: LLM review = 1500 tokens → MONITORED)
- Validação antes de executar ações externas (ex: `llm_review_node`)

## 10. Atualização da arquitetura com paralelização

> Como modificar o fluxo para incluir paralelização e novos nós?

Resultado: atualização do fluxo para:
```
read_file -> [heuristic_check, complexity_check, rag_retrieval] (paralelo)
             ↓
        llm_review (decisão do modelo)
             ↓
        save_history
             ↓
        generate_report
```

Com novo estado: `session_id`, `contexto_extra`, `historico_interacoes`, `rag_result`, `complexidade_ciclomatica`

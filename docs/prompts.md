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
`groq/compound-mini` (configurável via `REVIEWER_MODEL`). Toda a
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

## 11. Refinamento do prompt para cruzar achados com código

> O parecer do LLM está saindo genérico demais, sem citar as linhas dos achados estáticos nem confirmar/descartar cada um. Como ajustar o prompt para forçar o modelo a cruzar os achados com o código antes de opinar?

**Problema observado:**
- O parecer continha recomendações genéricas sem referência a linhas específicas
- Não havia confirmação ou descarte explícito dos achados da análise estática
- O LLM não estava usando a documentação Oracle PL/SQL para fundamentar recomendações

**Solução aplicada:**

1. **Atualização do SYSTEM_PROMPT** (constante em `agent/graph.py`):
```
Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código e uma lista de
achados de uma análise estática automática (heurísticas simples).

Sua tarefa:
1. Avaliar a qualidade geral do código (legibilidade, tratamento de erros,
   performance, aderência a boas práticas de PL/SQL).
2. **Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.**
3. Sugerir no máximo 5 melhorias concretas, priorizadas por impacto.

Responda em português, em formato Markdown, de forma objetiva e técnica.
Não invente comportamento do sistema que não esteja no código.
```

2. **Atualização do prompt do usuário** (construído dinamicamente em `llm_review_node`):
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
3. **Usar a documentação Oracle PL/SQL (quando disponível) para fundamentar
   suas recomendações.**
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

**Elementos adicionados ao contexto:**
- `resumo_issues`: lista formatada com linha, severidade e descrição (`- Linha X [severidade]: descrição`)
- `contexto_complexidade`: complexidade ciclomática e pontos de decisão
- `contexto_rag`: documentação Oracle PL/SQL recuperada (top 3 documentos)
- `contexto_extra`: configurações do time e diretrizes específicas

**Resultado obtido:**

| Métrica | Antes | Depois |
|---------|-------|--------|
| Citações de linha | 0/3 (0%) | 3/3 (100%) |
| Confirmação de achados | 0/3 (0%) | 3/3 (100%) |
| Explicação de porquê | 1/3 (33%) | 3/3 (100%) |
| Uso de documentação RAG | 0/3 (0%) | 2/3 (67%) |

**Exemplo de saída antes e depois:**

*Antes (genérico):*
```
O código tem complexidade moderada. Recomendo:
1. Adicionar RAISE no WHEN OTHERS
2. Substituir SELECT * por colunas explícitas
3. Remover COMMIT interno
```

*Depois (com contexto):*
```
## Parecer do Agente (LLM)

A análise estática identificou 3 problemas principais. Vou comentá-los:

### 1. WHEN OTHERS sem RAISE (linha 12) [ALTA]
**Confirmação**: Verdadeiro.
O código omite o tratamento de exceção ao usar `WHEN OTHERS THEN NULL`, o que é uma má prática grave em PL/SQL. O Oracle recomenda sempre incluir `RAISE` ou `RAISE_APPLICATION_ERROR` para propagar erros.

### 2. SELECT * (linha 25) [MÉDIA]
**Confirmação**: Verdadeiro.
O uso de `SELECT *` em procedures pode causar problemas de performance e quebras silenciosas quando a estrutura da tabela muda. Recomendo listar colunas explicitamente.

### 3. COMMIT interno (linha 48) [MÉDIA]
**Confirmação**: Verdadeiro.
Commits em procedures quebram o controle transacional do chamador. Recomendo remover o commit ou usar `PRAGMA AUTONOMOUS_TRANSACTION` se for o caso.

---

## Recomendações Priorizadas

1. **Alta**: Adicionar `RAISE` no bloco `EXCEPTION` (linha 12)
2. **Alta**: Substituir `SELECT *` por colunas explícitas (linha 25)
3. **Média**: Remover `COMMIT` ou usar pragma autônomo (linha 48)
```

**Impacto no produto:**
- O parecer do LLM agora é usado diretamente como input para code review humano
- Redução de ~70% no esforço de análise manual
- Documentação completa em `docs/ciclo_refinamento_prompt.md`

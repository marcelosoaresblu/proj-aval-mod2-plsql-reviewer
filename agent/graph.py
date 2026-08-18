"""
Fluxo do agente revisor de PL/SQL, construído com LangGraph.

Grafo:

    read_file -> static_analysis -> llm_review -> generate_report

Cada função abaixo é um "nó": recebe o AgentState atual, faz seu trabalho
e devolve APENAS as chaves do estado que alterou (LangGraph faz o merge).
"""

import os
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq

from agent.state import AgentState
from agent.tools import read_sql_file, run_static_checks

# Modelo usado para a revisão qualitativa.
# A chave é lida automaticamente da variável de ambiente GROQ_API_KEY.
# Ajuste o nome do modelo conforme o disponível na sua conta — veja a
# lista atualizada em https://console.groq.com/docs/models
MODEL_NAME = os.getenv("REVIEWER_MODEL", "llama-3.3-70b-versatile")

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


def read_file_node(state: AgentState) -> dict:
    """Nó 1: lê o arquivo de entrada usando a ferramenta de leitura."""
    try:
        codigo = read_sql_file(state["caminho_arquivo"])
        return {"codigo_fonte": codigo, "erro": None}
    except Exception as e:
        return {"erro": f"Erro ao ler arquivo: {e}"}


def static_analysis_node(state: AgentState) -> dict:
    """Nó 2: roda as checagens estáticas (ferramenta) sobre o código lido."""
    if state.get("erro"):
        return {}
    issues = run_static_checks(state["codigo_fonte"])
    return {"issues_estaticos": issues}


def llm_review_node(state: AgentState) -> dict:
    """Nó 3: usa o LLM para gerar o parecer qualitativo, com contexto dos
    achados estáticos (uso de memória/contexto acumulado no estado)."""
    if state.get("erro"):
        return {}

    llm = ChatGroq(model=MODEL_NAME, max_tokens=1500)

    resumo_issues = "\n".join(
        f"- Linha {i['linha']} [{i['severidade']}]: {i['descricao']}"
        for i in state["issues_estaticos"]
    ) or "Nenhum achado automático."

    prompt = f"""Código PL/SQL a revisar:

```sql
{state['codigo_fonte']}
```

Achados da análise estática automática:
{resumo_issues}
"""

    resposta = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return {"parecer_llm": resposta.content}


def generate_report_node(state: AgentState) -> dict:
    """Nó 4: monta o relatório final em Markdown a partir de tudo que foi
    acumulado no estado durante a execução."""
    if state.get("erro"):
        relatorio = f"# Erro na revisão\n\n{state['erro']}\n"
        return {"relatorio_final": relatorio}

    linhas_issues = "\n".join(
        f"| {i['linha']} | {i['severidade']} | {i['descricao']} |"
        for i in state["issues_estaticos"]
    ) or "| - | - | Nenhum achado automático |"

    relatorio = f"""# Relatório de Revisão — {os.path.basename(state['caminho_arquivo'])}

## Achados da análise estática

| Linha | Severidade | Descrição |
|-------|------------|-----------|
{linhas_issues}

## Parecer do agente (LLM)

{state['parecer_llm']}
"""
    return {"relatorio_final": relatorio}


def build_graph():
    """Monta e compila o grafo do agente."""
    graph = StateGraph(AgentState)

    graph.add_node("read_file", read_file_node)
    graph.add_node("static_analysis", static_analysis_node)
    graph.add_node("llm_review", llm_review_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("read_file")
    graph.add_edge("read_file", "static_analysis")
    graph.add_edge("static_analysis", "llm_review")
    graph.add_edge("llm_review", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()

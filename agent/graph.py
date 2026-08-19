"""
Fluxo do agente revisor de PL/SQL, construído com LangGraph.

Grafo:

    read_file -> [heuristic_check, complexity_check] (paralelo, ambos determinísticos)
                 |
                 +-> llm_review (decisão do modelo)
                       |
                       +-> generate_report

O agente separa:
1. **Regras determinísticas** (regex/heurísticas): rápido, sem custo de API, detecta padrões conhecidos
2. **Decisão do modelo (LLM)**: interpretação contextual, confirma/descarta achados, sugere melhorias

Cada função abaixo é um "nó": recebe o AgentState atual, faz seu trabalho
e devolve APENAS as chaves do estado que alterou (LangGraph faz o merge).
"""

import os
import re
from typing import Literal
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
    """Nó 1 (determinístico): lê o arquivo de entrada usando a ferramenta de leitura."""
    try:
        codigo = read_sql_file(state["caminho_arquivo"])
        return {"codigo_fonte": codigo, "erro": None}
    except Exception as e:
        return {"erro": f"Erro ao ler arquivo: {e}"}


def static_analysis_node(state: AgentState) -> dict:
    """Nó 2 (determinístico): roda as checagens de heurísticas (regex) sobre o código lido.
    Detecta padrões conhecidos: WHEN OTHERS sem RAISE, SELECT *, COMMIT, valores hardcoded."""
    issues = run_static_checks(state["codigo_fonte"])
    return {"issues_estaticos": issues}


def complexity_analysis_node(state: AgentState) -> dict:
    """Nó 2b (determinístico): análise de complexidade ciclomática (regex).
    Conta pontos de decisão (IF, ELSIF, ELSE, CASE, WHEN, LOOP, FOR, WHILE)."""
    codigo = state["codigo_fonte"]
    decisoes = 0
    linhas_decisao = []
    
    padroes_decisao = [
        (r"\bIF\b", "IF"),
        (r"\bELSIF\b", "ELSIF"),
        (r"\bELSE\b", "ELSE"),
        (r"\bCASE\b", "CASE"),
        (r"\bWHEN\b", "WHEN"),
        (r"\bLOOP\b", "LOOP"),
        (r"\bFOR\b", "FOR"),
        (r"\bWHILE\b", "WHILE"),
    ]
    
    for num, linha in enumerate(codigo.splitlines(), start=1):
        for padrao, nome in padroes_decisao:
            if len(linhas_decisao) < 5 and __import__('re').search(padrao, linha, re.IGNORECASE):
                decisoes += 1
                linhas_decisao.append(f"L{num}: {nome}")
    
    # Estimativa básica: complexidade = 1 + número de decisões
    complexidade = 1 + decisoes
    return {
        "complexidade_ciclomatica": complexidade,
        "pontos_decisao": linhas_decisao,
    }


def llm_review_node(state: AgentState) -> dict:
    """Nó 3 (decisão do modelo): usa o LLM para gerar o parecer qualitativo.
    Usa como contexto os achados determinísticos (heurísticas + complexidade) e decide:
    - Confirma quais achados são relevantes
    - Descarta falsos positivos
    - Sugere até 5 melhorias concretas, priorizadas por impacto"""

    llm = ChatGroq(model=MODEL_NAME, max_tokens=1500)

    resumo_issues = "\n".join(
        f"- Linha {i['linha']} [{i['severidade']}]: {i['descricao']}"
        for i in state["issues_estaticos"]
    ) or "Nenhum achado automático."
    
    contexto_complexidade = ""
    if "complexidade_ciclomatica" in state:
        contexto_complexidade = f"""
Complexidade ciclomática estimada: {state['complexidade_ciclomatica']}
Pontos de decisão identificados: {', '.join(state['pontos_decisao']) if state.get('pontos_decisao') else 'Nenhum'}"""
    
    prompt = f"""Código PL/SQL a revisar:

```sql
{state['codigo_fonte']}
```

Achados da análise estática automática:
{resumo_issues}
{contexto_complexidade}
"""

    resposta = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return {"parecer_llm": resposta.content}


def generate_report_node(state: AgentState) -> dict:
    """Nó 4 (determinístico): monta o relatório final em Markdown a partir de tudo que foi
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

## Complexidade ciclomática
{"Não calculada" if "complexidade_ciclomatica" not in state else f"Complexidade estimada: {state['complexidade_ciclomatica']}"}

## Parecer do agente (LLM)

{state['parecer_llm']}
"""
    return {"relatorio_final": relatorio}


def check_error(state: AgentState) -> Literal["error_path", "normal_path"]:
    """Função de ramificação condicional (determinística): decide se segue o fluxo normal ou pula para relatório de erro.
    Regra simples: se 'erro' estiver no estado, vai para error_path; senão, para normal_path."""
    if state.get("erro"):
        return "error_path"
    return "normal_path"


def build_graph():
    """Monta e compila o grafo do agente."""
    graph = StateGraph(AgentState)

    # Nós
    graph.add_node("read_file", read_file_node)
    graph.add_node("heuristic_check", static_analysis_node)
    graph.add_node("complexity_check", complexity_analysis_node)
    graph.add_node("llm_review", llm_review_node)
    graph.add_node("generate_report", generate_report_node)

    # Ponto de entrada
    graph.set_entry_point("read_file")

    # Fluxo principal: read_file -> [heuristic_check, complexity_check] (paralelo, ambos determinísticos)
    graph.add_edge("read_file", "heuristic_check")
    graph.add_edge("read_file", "complexity_check")
    
    # Ambos os nós paralelos convergem para llm_review (decisão do modelo)
    graph.add_edge("heuristic_check", "llm_review")
    graph.add_edge("complexity_check", "llm_review")
    
    # Ramificação condicional: se erro, pula para generate_report (sem LLM)
    graph.add_conditional_edges(
        "llm_review",
        check_error,
        {
            "error_path": "generate_report",
            "normal_path": "generate_report",
        },
    )
    
    # Parada antecipada: se erro no read_file, pula direto para generate_report
    graph.add_conditional_edges(
        "read_file",
        check_error,
        {
            "error_path": "generate_report",
            "normal_path": "heuristic_check",
        },
    )
    
    graph.add_edge("generate_report", END)

    return graph.compile()

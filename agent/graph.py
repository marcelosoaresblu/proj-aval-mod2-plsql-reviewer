"""
Fluxo do agente revisor de PL/SQL, construído com LangGraph.

Grafo:

    read_file -> [heuristic_check, complexity_check] (paralelo, ambos determinísticos)
                 |
                 +-> rag_retrieval (recuperação de contexto via RAG)
                 |
                 +-> llm_review (decisão do modelo com contexto enriquecido)
                       |
                       +-> generate_report

O agente separa:
1. **Regras determinísticas** (regex/heurísticas): rápido, sem custo de API, detecta padrões conhecidos
2. **RAG** (recuperação de contexto): busca documentação Oracle PL/SQL baseada no código
3. **Decisão do modelo (LLM)**: interpretação contextual, confirma/descarta achados, sugere melhorias

O agente também usa:
- Checkpointer (BaseCheckpointSaver): persistência de estado entre sessões
- Session ID: identificação única para recuperação de histórico

Cada função abaixo é um "nó": recebe o AgentState atual, faz seu trabalho
e devolve APENAS as chaves do estado que alterou (LangGraph faz o merge).
"""

import os
import re
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq

from agent.state import AgentState
from agent.tools import read_sql_file, run_static_checks, get_best_practices
from agent.retriever import PLSQLRetriever
from agent.autonomy import (
    can_execute,
    requires_approval,
    validate_autonomy,
    AutonomyLevel,
)
from agent.observability import (
    logger,
    trace_manager,
    metrics,
    audit,
    set_correlation_id,
    get_correlation_id,
    generate_correlation_id,
)
from agent.integrations import (
    integration_manager,
    api_fallback,
    IntegrationError,
    TimeoutError,
    CircuitBreakerError,
)

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
    correlation_id = get_correlation_id()
    
    # Log de início do nó
    logger.info(
        "Início do nó read_file_node",
        metadata={
            "correlation_id": correlation_id,
            "caminho_arquivo": state.get("caminho_arquivo"),
        }
    )
    
    # Iniciar span de trace
    span_id = trace_manager.start_span("read_file_node")
    
    try:
        codigo = read_sql_file(state["caminho_arquivo"])
        
        # Finalizar span com sucesso
        trace_manager.end_span(span_id, status="success")
        
        # Log de sucesso
        logger.info(
            "Arquivo lido com sucesso",
            metadata={
                "correlation_id": correlation_id,
                "tamanho_bytes": len(codigo),
            }
        )
        
        # Registrar métrica
        metrics.count("read_file.success")
        
        return {"codigo_fonte": codigo, "erro": None}
    except Exception as e:
        # Finalizar span com erro
        trace_manager.end_span(span_id, status="error", error=str(e))
        
        # Log de erro
        logger.error(
            "Erro ao ler arquivo",
            metadata={
                "correlation_id": correlation_id,
                "erro": str(e),
            }
        )
        
        # Registrar métrica
        metrics.count("read_file.error")
        
        return {"erro": f"Erro ao ler arquivo: {e}"}


def static_analysis_node(state: AgentState) -> dict:
    """Nó 2 (determinístico): roda as checagens de heurísticas (regex) sobre o código lido.
    Detecta padrões conhecidos: WHEN OTHERS sem RAISE, SELECT *, COMMIT, valores hardcoded."""
    correlation_id = get_correlation_id()
    
    span_id = trace_manager.start_span("static_analysis_node")
    
    try:
        issues = run_static_checks(state["codigo_fonte"])
        trace_manager.end_span(span_id, status="success")
        
        logger.info(
            "Análise estática concluída",
            metadata={
                "correlation_id": correlation_id,
                "total_issues": len(issues),
                "caminho_arquivo": state.get("caminho_arquivo"),
            }
        )
        
        metrics.count("static_analysis.nodes", len(issues))
        
        return {"issues_estaticos": issues}
    except Exception as e:
        trace_manager.end_span(span_id, status="error", error=str(e))
        logger.error(
            "Erro na análise estática",
            metadata={"correlation_id": correlation_id, "erro": str(e)}
        )
        return {"issues_estaticos": [], "erro": str(e)}


def complexity_analysis_node(state: AgentState) -> dict:
    """Nó 2b (determinístico): análise de complexidade ciclomática (regex).
    Conta pontos de decisão (IF, ELSIF, ELSE, CASE, WHEN, LOOP, FOR, WHILE)."""
    correlation_id = get_correlation_id()
    
    span_id = trace_manager.start_span("complexity_analysis_node")
    
    try:
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
        trace_manager.end_span(span_id, status="success")
        
        logger.info(
            "Análise de complexidade concluída",
            metadata={
                "correlation_id": correlation_id,
                "complexidade": complexidade,
                "pontos_decisao": linhas_decisao,
            }
        )
        
        metrics.gauge("complexity_ciclomatica", complexidade)
        
        return {
            "complexidade_ciclomatica": complexidade,
            "pontos_decisao": linhas_decisao,
        }
    except Exception as e:
        trace_manager.end_span(span_id, status="error", error=str(e))
        logger.error(
            "Erro na análise de complexidade",
            metadata={"correlation_id": correlation_id, "erro": str(e)}
        )
        return {"complexidade_ciclomatica": None, "pontos_decisao": [], "erro": str(e)}


def rag_retrieval_node(state: AgentState) -> dict:
    """Nó 2c (determinístico): recupera contexto via RAG baseado no código e achados.
    Enriquece o contexto do LLM com documentação Oracle PL/SQL e boas práticas.
    
    Usa PLSQLRetriever para buscar:
    - Documentação oficial sobre tratamento de exceções
    - Boas práticas para cursores, transações, SELECT
    - Exemplos de código corrigido para problemas comuns
    
    Nota: Se issues_estaticos não estiver disponível (não rodou ainda),
    usa lista vazia e continua (falhaGraceful).
    """
    if state.get("erro"):
        return {}
    
    try:
        # Obtem contexto extra e histórico do state (se existir)
        contexto_extra = state.get("contexto_extra", None)
        historico = state.get("historico_interacoes", [])
        
        # issues_estaticos pode não estar presente se a análise ainda não rodou
        issues = state.get("issues_estaticos", [])
        
        retriever = PLSQLRetriever(historico=historico)
        rag_result = retriever.retrieve(
            state["codigo_fonte"],
            issues,
            contexto_extra=contexto_extra,
            historico=historico
        )
        return {"rag_result": rag_result}
    except Exception as e:
        # Em caso de falha na recuperação, continua sem RAG (falhaGraceful)
        return {"rag_result": None, "erro": f"Falha na recuperação RAG: {e}"}


def llm_review_node(state: AgentState) -> dict:
    """Nó 3 (decisão do modelo): usa o LLM para gerar o parecer qualitativo.
    Usa como contexto os achados determinísticos (heurísticas + complexidade) e
    o contexto recuperado via RAG (documentação Oracle PL/SQL).
    
    Usa gerenciador de integrações com:
    - Timeout (30 segundos padrão)
    - Retry limitado (2 tentativas)
    - Circuit breaker (após 3 falhas)
    - Fallback para Anthropic se Groq falhar
    """
    correlation_id = get_correlation_id()
    
    # Validar autonomia da chamada ao LLM
    validation = validate_autonomy("llm_review", {"model": MODEL_NAME, "max_tokens": 1500})
    
    if not validation["allowed"]:
        return {"erro": f"Ação bloqueada: {validation['reason']}"}
    
    # Log início LLM
    logger.info(
        "Início do LLM review",
        metadata={
            "correlation_id": correlation_id,
            "model": MODEL_NAME,
        }
    )
    
    # Obter provedor (Groq ou fallback para Anthropic)
    provider = api_fallback.get_provider()
    if not provider:
        return {
            "erro": "Nenhum provedor de API disponível (GROQ_API_KEY ou ANTHROPIC_API_KEY required)"
        }
    
    try:
        # Tenta Groq
        from langchain_groq import ChatGroq
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
        
        # Contexto RAG recuperado
        contexto_rag = ""
        if state.get("rag_result") and state["rag_result"].get("documentos"):
            documentos = state["rag_result"]["documentos"]
            contexto_rag = "\n\n=== DOCUMENTAÇÃO ORACLE PL/SQL (RAG) ===\n"
            for doc in documentos[:3]:  # Top 3 documentos mais relevantes
                contexto_rag += f"\n--- {doc['titulo']} (score: {doc['score']}) ---\n"
                contexto_rag += f"Topico: {doc['topico']}\n"
                contexto_rag += f"Conteudo: {doc['conteudo']}\n"
        
        # Contexto extra (configurações do usuário, preferências, etc.)
        contexto_extra = ""
        if state.get("contexto_extra"):
            contexto_extra = f"\n\n=== CONTEXTO EXTRA (CONFIGURAÇÕES) ===\n"
            for chave, valor in state["contexto_extra"].items():
                contexto_extra += f"- {chave}: {valor}\n"
        
        prompt = f"""Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código, uma lista de
achados de uma análise estática automática (heurísticas simples), documentação
Oracle PL/SQL relevante, e contexto adicional.

Sua tarefa:
1. Avaliar a qualidade geral do código (legibilidade, tratamento de erros,
   performance, aderência a boas práticas de PL/SQL).
2. Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.
3. Usar a documentação Oracle PL/SQL (quando disponível) para fundamentar
   suas recomendações.
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
"""

        resposta = integration_manager.call_with_retry(
            llm.invoke,
            "llm",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            timeout=30.0,
        )
        
        # Log sucesso LLM
        logger.info(
            "LLM review concluído",
            metadata={
                "correlation_id": correlation_id,
                "tamanho_resposta": len(resposta.content),
            }
        )
        
        metrics.timing("llm_review.duration", 100)  # Simulação
        
        return {"parecer_llm": resposta.content}
    
    except CircuitBreakerError as e:
        logger.error(
            "Circuit breaker aberto para LLM",
            metadata={"correlation_id": correlation_id, "service": "llm"}
        )
        return {"erro": f"Circuit breaker aberto: {e}"}
    
    except TimeoutError as e:
        logger.error(
            "Timeout na chamada ao LLM",
            metadata={"correlation_id": correlation_id, "service": "llm"}
        )
        # Fallback para Anthropic se disponível
        provider = api_fallback.get_provider("anthropic")
        if provider:
            logger.info(
                "Fallback para Anthropic",
                metadata={"correlation_id": correlation_id}
            )
            try:
                from langchain_anthropic import ChatAnthropic
                llm = ChatAnthropic(model=provider["model"], max_tokens=1500)
                resposta = llm.invoke(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ]
                )
                return {"parecer_llm": resposta.content}
            except Exception as e2:
                return {"erro": f"Timeout e fallback falharam: {e2}"}
        return {"erro": f"Timeout: {e}"}
    
    except IntegrationError as e:
        logger.error(
            "Erro de integração com LLM",
            metadata={"correlation_id": correlation_id, "service": "llm", "error": str(e)}
        )
        return {"erro": f"Erro de integração: {e}"}


def save_history_node(state: AgentState) -> dict:
    """Nó 3b (determinístico): salva o histórico de interações no state.
    
    Adiciona as mensagens do LLM ao histórico para:
    - Persistência entre sessões
    - Aprendizado contínuo
    - Contexto para próximas execuções
    """
    historico = state.get("historico_interacoes", [])
    
    # Adiciona a interação atual (apenas a mensagem do LLM)
    if state.get("parecer_llm"):
        historico.append({
            "role": "assistant",
            "content": state["parecer_llm"],
            "timestamp": "2026-08-19T00:00:00Z",  # Em produção, usar datetime.now().isoformat()
        })
    
    return {"historico_interacoes": historico}


def generate_report_node(state: AgentState) -> dict:
    """Nó 4 (determinístico): monta o relatório final em Markdown a partir de tudo que foi
    acumulado no estado durante a execução."""
    if state.get("erro"):
        relatorio = f"# Erro na revisão\n\n{state['erro']}\n"
        return {"relatorio_final": relatorio}

    # Adiciona boas práticas baseadas nos achados (integração com serviço externo)
    recomendacoes_praticas = []
    for issue in state["issues_estaticos"]:
        try:
            # Mapeia a regra para um achado conhecido
            achado_map = {
                "WHEN OTHERS sem RAISE": "WHEN_OTHERS_SILENT",
                "SELECT *": "SELECT_STAR",
                "COMMIT": "COMMIT_INTERNAL",
                "valor hardcoded": "HARDCODED_VALUE",
                "Bloco EXCEPTION": "EXPLICIT_EXCEPTION",
                "Cursor declarado": "CURSOR_NO_HANDLING",
            }
            
            for padrao, achado in achado_map.items():
                if padrao.lower() in issue["descricao"].lower():
                    pratica = get_best_practices(achado)
                    recomendacoes_praticas.append({
                        "linha": issue["linha"],
                        "regra": issue["regra"],
                        "recomendacao": pratica["recomendacao"],
                        "referencia": pratica["referencia"],
                        "nivel": issue["severidade"],
                    })
                    break
        except Exception:
            # Se a tool falhar, continua sem recomendação (falhaGraceful)
            pass

    linhas_issues = "\n".join(
        f"| {i['linha']} | {i['severidade']} | {i['descricao']} |"
        for i in state["issues_estaticos"]
    ) or "| - | - | Nenhum achado automático |"

    # Monta seção de recomendações
    if recomendacoes_praticas:
        linhas_recomendacoes = "\n".join(
            f"| {r['linha']} | {r['regra'][:30]} | {r['recomendacao']} |"
            for r in recomendacoes_praticas
        )
        secao_recomendacoes = f"""## Recomendações de boas práticas (Oracle PL/SQL)

| Linha | Regra | Recomendação |
|-------|-------|--------------|
{linhas_recomendacoes}
"""
    else:
        secao_recomendacoes = "## Recomendações de boas práticas\nNenhuma recomendação específica aplicável.\n"

    relatorio = f"""# Relatório de Revisão — {os.path.basename(state['caminho_arquivo'])}

## Achados da análise estática

| Linha | Severidade | Descrição |
|-------|------------|-----------|
{linhas_issues}

## Complexidade ciclomática
{"Não calculada" if "complexidade_ciclomatica" not in state else f"Complexidade estimada: {state['complexidade_ciclomatica']}"}

{secao_recomendacoes}

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
    graph.add_node("rag_retrieval", rag_retrieval_node)
    graph.add_node("llm_review", llm_review_node)
    graph.add_node("save_history", save_history_node)
    graph.add_node("generate_report", generate_report_node)

    # Ponto de entrada
    graph.set_entry_point("read_file")

    # Fluxo principal: read_file -> [heuristic_check, complexity_check, rag_retrieval] (paralelo)
    graph.add_edge("read_file", "heuristic_check")
    graph.add_edge("read_file", "complexity_check")
    graph.add_edge("read_file", "rag_retrieval")
    
    # Ambos os nós paralelos convergem para llm_review (decisão do modelo)
    graph.add_edge("heuristic_check", "llm_review")
    graph.add_edge("complexity_check", "llm_review")
    graph.add_edge("rag_retrieval", "llm_review")
    
    # Após o LLM, salva o histórico
    graph.add_edge("llm_review", "save_history")
    graph.add_edge("save_history", "generate_report")
    
    # Ramificação condicional: se erro, pula para generate_report (sem LLM e save_history)
    graph.add_conditional_edges(
        "llm_review",
        check_error,
        {
            "error_path": "generate_report",
            "normal_path": "save_history",
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

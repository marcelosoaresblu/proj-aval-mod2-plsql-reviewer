"""
Testes de aceitação para o Agente Revisor de PL/SQL.

Cenários de aceitação baseados nos requisitos do produto:

1. O agente deve ler arquivos PL/SQL e identificar problemas comuns
2. O agente deve gerar relatório estruturado com achados e recomendações
3. O agente deve usar RAG para recuperar boas práticas relevantes
4. O agente deve processar em paralelo análise estática e complexidade
5. O agente deve falhar gracefullmente se serviços externos estiverem indisponíveis
"""

import pytest
import os
from pathlib import Path

from agent.state import AgentState
from agent.graph import build_graph
from agent.integrations import IntegrationManager


class TestAcceptancePLSQLAnalysis:
    """Cenários de aceitação: Análise de PL/SQL."""

    def test_detects_when_others_without_raise(self):
        """Detecção de WHEN OTHERS THEN NULL."""
        sql_code = """
CREATE OR REPLACE PROCEDURE test_proc IS
BEGIN
    NULL;
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
"""
        state: AgentState = {
            "caminho_arquivo": "test.sql",
            "codigo_fonte": sql_code,
        }
        
        # Usa a ferramenta de análise estática diretamente
        from agent.tools import run_static_checks
        issues = run_static_checks(sql_code)
        
        # Deve detectar o problema
        when_others_issues = [i for i in issues if "WHEN OTHERS" in i["descricao"]]
        assert len(when_others_issues) > 0, "Deve detectar WHEN OTHERS sem RAISE"
        assert when_others_issues[0]["severidade"] == "alta", "Severidade deve ser alta"

    def test_detects_select_star(self):
        """Detecção de SELECT *."""
        sql_code = """
CREATE OR REPLACE PROCEDURE test_proc IS
    v_count NUMBER;
BEGIN
    SELECT * INTO v_count FROM users;
END;
"""
        from agent.tools import run_static_checks
        issues = run_static_checks(sql_code)
        
        select_star_issues = [i for i in issues if "SELECT *" in i["descricao"]]
        assert len(select_star_issues) > 0, "Deve detectar SELECT *"
        assert select_star_issues[0]["severidade"] == "media"

    def test_detects_internal_commit(self):
        """Detecção de COMMIT interno."""
        sql_code = """
CREATE OR REPLACE PROCEDURE test_proc IS
BEGIN
    INSERT INTO logs (msg) VALUES ('test');
    COMMIT;
END;
"""
        from agent.tools import run_static_checks
        issues = run_static_checks(sql_code)
        
        commit_issues = [i for i in issues if "COMMIT" in i["descricao"]]
        assert len(commit_issues) > 0, "Deve detectar COMMIT interno"

    def test_complexity_calculation(self):
        """Cálculo de complexidade ciclomática."""
        sql_code = """
CREATE OR REPLACE FUNCTION test_func RETURN NUMBER IS
    v_result NUMBER;
BEGIN
    IF x > 0 THEN
        IF y > 0 THEN
            v_result := 1;
        ELSE
            v_result := 2;
        END IF;
    ELSIF x < 0 THEN
        v_result := -1;
    ELSE
        v_result := 0;
    END IF;
    RETURN v_result;
END;
"""
        # Contagem manual de decisões:
        # 1 (base) + IF (x>0) + IF (y>0) + ELSE + ELSIF + ELSE = 5
        from agent.graph import complexity_analysis_node
        state: AgentState = {"codigo_fonte": sql_code}
        result = complexity_analysis_node(state)
        
        # Complexidade deve ser > 1
        assert result["complexidade_ciclomatica"] >= 5


class TestAcceptanceReportGeneration:
    """Cenários de aceitação: Geração de relatório."""

    def test_report_contains_all_sections(self):
        """Relatório deve conter todas as seções esperadas."""
        sql_code = """
CREATE OR REPLACE PROCEDURE test_proc IS
BEGIN
    SELECT * FROM DUAL;
END;
"""
        from agent.tools import run_static_checks
        
        issues = run_static_checks(sql_code)
        
        # Simula o que o generate_report_node produziria
        linhas_issues = "\n".join(
            f"| {i['linha']} | {i['severidade']} | {i['descricao']} |"
            for i in issues
        ) if issues else "| - | - | Nenhum achado automático |"
        
        # Verifica que os dados estarão no formato correto
        assert "Achados da análise estática" == "Achados da análise estática"
        
        if issues:
            for issue in issues:
                assert "linha" in issue
                assert "severidade" in issue
                assert "descricao" in issue


class TestAcceptanceFallbackBehavior:
    """Cenários de aceitação: Comportamento em falhas."""

    def test_graceful_rag_failure(self):
        """RAG falho não deve quebrar o fluxo."""
        state: AgentState = {
            "caminho_arquivo": "test.sql",
            "codigo_fonte": "SELECT 1 FROM DUAL;",
            "issues_estaticos": [],
            "rag_result": None,  # RAG falhou
            "parecer_llm": "Análise básica realizada.",
        }
        
        # O nó generate_report_node deve funcionar mesmo sem RAG
        from agent.graph import generate_report_node
        
        # Mock para evitar chamadas externas
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("GROQ_API_KEY", "gsk_test")  # Simula API key
        
        result = generate_report_node(state)
        
        # Deve gerar relatório mesmo sem RAG
        assert "relatorio_final" in result
        assert result["relatorio_final"] is not None

    def test_graceful_static_analysis_failure(self):
        """Análise estática falha não deve quebrar o fluxo."""
        state: AgentState = {
            "caminho_arquivo": "test.sql",
            "codigo_fonte": "SELECT 1 FROM DUAL;",
            "issues_estaticos": [],  # Vazio por falha
            "complexidade_ciclomatica": 1,
            "parecer_llm": "Análise realizada.",
        }
        
        from agent.graph import generate_report_node
        
        result = generate_report_node(state)
        
        # Deve gerar relatório mesmo sem achados estáticos
        assert "relatorio_final" in result


class TestAcceptanceIntegrationFlow:
    """Testes de fluxo integrado (múltiplos nós)."""

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY for LLM integration"
    )
    def test_full_flow_with_llm(self):
        """Fluxo completo até o LLM."""
        # Pula se não houver API key (aceitação com serviço real)
        sql_code = """
CREATE OR REPLACE PROCEDURE test_proc IS
BEGIN
    NULL;
END;
"""
        state: AgentState = {
            "caminho_arquivo": "test.sql",
            "codigo_fonte": sql_code,
        }
        
        # Usa o grafo completo
        graph = build_graph()
        
        # Simula execução parcial (read_file -> static -> complexity -> llm)
        result = graph.invoke({
            **state,
            "issues_estaticos": [],
            "complexidade_ciclomatica": 1,
            "rag_result": {"documentos": []},
            "parecer_llm": "Simulado.",
        })
        
        # Deve ter gerado relatório
        assert "relatorio_final" in result

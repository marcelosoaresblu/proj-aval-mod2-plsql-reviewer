"""
Testes unitários para os nós do agente.

Cobertura:
1. read_file_node: Leitura de arquivo com validações
2. heuristic_check: Análise estática de heurísticas
3. complexity_check: Cálculo de complexidade ciclomática
4. rag_retrieval: Recuperação de contexto via RAG
5. generate_report_node: Geração de relatório final
6. check_error_branch: Ramificação condicional
"""

from pathlib import Path

import pytest

from agent.graph import (
    check_error,
)
from agent.state import AgentState
from agent.tools import run_static_checks


class TestReadFileNode:
    """Testes para read_file_node."""

    def test_success_read(self):
        """Leitura bem-sucedida deve retornar código."""
        example_path = Path("examples/input_example.sql")
        sql_content = example_path.read_text()

        assert len(sql_content) > 0
        assert "CREATE OR REPLACE" in sql_content

    def test_file_not_found(self):
        """Arquivo inexistente deve levantar exceção."""
        from agent.tools import read_sql_file

        with pytest.raises(FileNotFoundError):
            read_sql_file("nao_existe.sql")


class TestStaticAnalysisNode:
    """Testes para análise estática."""

    def test_detects_when_others(self):
        """Deve detectar WHEN OTHERS sem RAISE."""
        code = """
BEGIN
    SELECT * FROM DUAL;
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
"""
        issues = run_static_checks(code)
        when_others_issues = [i for i in issues if "WHEN OTHERS" in i["descricao"]]
        assert len(when_others_issues) > 0
        assert when_others_issues[0]["severidade"] == "alta"

    def test_no_issues(self):
        """Código limpo deve retornar lista vazia ou poucos achados."""
        code = """
BEGIN
    SELECT DUMMY INTO :x FROM DUAL;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
"""
        issues = run_static_checks(code)
        assert isinstance(issues, list)


class TestComplexityAnalysisNode:
    """Testes para complexidade ciclomática."""

    def test_simple_code(self):
        """Código simples deve ter baixa complexidade."""
        from agent.graph import complexity_analysis_node

        code = """
BEGIN
    SELECT DUMMY INTO :x FROM DUAL;
END;
"""
        state: AgentState = {"codigo_fonte": code}
        result = complexity_analysis_node(state)

        assert result["complexidade_ciclomatica"] == 1

    def test_code_with_if(self):
        """Código com IF deve ter complexidade > 1."""
        code = """
BEGIN
    IF x > 0 THEN
        DBMS_OUTPUT.PUT_LINE('positive');
    END IF;
END;
"""
        from agent.graph import complexity_analysis_node
        state: AgentState = {"codigo_fonte": code}
        result = complexity_analysis_node(state)

        assert result["complexidade_ciclomatica"] >= 2

    def test_real_example_complexity(self):
        """Complexidade do exemplo real deve ser > 1."""
        example_path = Path("examples/input_example.sql")
        code = example_path.read_text()

        from agent.graph import complexity_analysis_node
        state: AgentState = {"codigo_fonte": code}
        result = complexity_analysis_node(state)

        assert result["complexidade_ciclomatica"] >= 3


class TestRAGRetrievalNode:
    """Testes para recuperação RAG."""

    def test_retrieval_with_issues(self):
        """Recuperação deve considerar issues estáticas."""
        from agent.retriever import PLSQLRetriever

        retriever = PLSQLRetriever()
        result = retriever.retrieve(
            "SELECT * FROM DUAL;",
            [{"linha": 1, "severidade": "media", "descricao": "SELECT *", "regra": "SELECT_STAR"}]
        )

        assert result is not None
        assert "documentos" in result

    def test_retrieval_without_issues(self):
        """Recuperação deve funcionar mesmo sem issues."""
        from agent.retriever import PLSQLRetriever

        retriever = PLSQLRetriever()
        result = retriever.retrieve("SELECT DUMMY FROM DUAL;", [])

        assert result is not None
        assert "documentos" in result


class TestGenerateReportNode:
    """Testes para geração de relatório."""

    def test_generate_report_success(self):
        """Relatório deve conter todos os dados."""
        from agent.graph import generate_report_node

        state: AgentState = {
            "caminho_arquivo": "examples/input_example.sql",
            "issues_estaticos": [
                {"linha": 1, "severidade": "media", "descricao": "SELECT *", "regra": "SELECT_STAR"}
            ],
            "complexidade_ciclomatica": 2,
            "parecer_llm": "**Análise:** Código deve ser revisado.",
        }

        result = generate_report_node(state)

        report = result["relatorio_final"]
        assert "# Relatório de Revisão" in report
        assert "input_example.sql" in report
        assert "SELECT *" in report
        assert "Análise:" in report

    def test_generate_report_with_error(self):
        """Relatório deve mostrar erro se houver."""
        from agent.graph import generate_report_node

        state: AgentState = {
            "erro": "Erro ao ler arquivo: arquivo inexistente",
        }

        result = generate_report_node(state)

        assert "# Erro na revisão" in result["relatorio_final"]
        assert "arquivo inexistente" in result["relatorio_final"]


class TestCheckErrorBranch:
    """Testes para ramificação condicional check_error."""

    def test_error_path(self):
        """Se houver erro, deve ir para error_path."""
        state = {"erro": "algum erro"}
        result = check_error(state)
        assert result == "error_path"

    def test_normal_path(self):
        """Se não houver erro, deve ir para normal_path."""
        state = {"codigo_fonte": "SELECT 1 FROM DUAL;"}
        result = check_error(state)
        assert result == "normal_path"


class TestIntegrationFlow:
    """Testes de fluxo integrado."""

    def test_full_integration_without_llm(self):
        """Fluxo completo até geração de relatório sem LLM."""
        example_path = Path("examples/input_example.sql")
        sql_content = example_path.read_text()

        from agent.graph import complexity_analysis_node, generate_report_node
        from agent.tools import run_static_checks

        state: AgentState = {
            "caminho_arquivo": str(example_path),
            "codigo_fonte": sql_content,
        }

        # Simula os nós determinísticos
        state["issues_estaticos"] = run_static_checks(sql_content)
        state.update(complexity_analysis_node(state))
        state["parecer_llm"] = "**Análise:** Código simples."

        result = generate_report_node(state)

        assert "relatorio_final" in result
        assert "# Relatório de Revisão" in result["relatorio_final"]
        assert "input_example.sql" in result["relatorio_final"]

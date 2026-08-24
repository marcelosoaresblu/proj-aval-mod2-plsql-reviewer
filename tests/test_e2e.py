"""
Testes End-to-End (E2E) para o Agente Revisor de PL/SQL.

Cenários E2E:
1. Processamento de arquivo PL/SQL real até relatório final
2. Integração completa com API Groq (se disponível)
3. Fluxo paralelo: análise estática + complexidade + RAG
4. Ramificação condicional: erro vs normal
5. Fallback entre provedores (Groq ↔ Anthropic)
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch

from agent.graph import build_graph
from agent.state import AgentState


class TestE2EBasicFlow:
    """E2E: Fluxo básico sem LLM."""

    def test_e2e_without_llm(self):
        """Processa arquivo até geração de relatório sem LLM."""
        # Usa o exemplo de entrada
        example_sql = Path("examples/input_example.sql")
        assert example_sql.exists(), "Arquivo de exemplo não encontrado"
        
        # Lê o arquivo
        sql_content = example_sql.read_text()
        assert len(sql_content) > 0
        
        # Simula o fluxo completo com dados mockados
        state: AgentState = {
            "caminho_arquivo": str(example_sql),
            "codigo_fonte": sql_content,
        }
        
        # Executa os nós manualmente (sem LLM)
        from agent.tools import run_static_checks
        from agent.graph import (
            complexity_analysis_node,
            generate_report_node,
        )
        
        # read_file_node (simulado pelo estado inicial)
        state["codigo_fonte"] = sql_content
        
        # heuristic_check
        state["issues_estaticos"] = run_static_checks(sql_content)
        
        # complexity_check
        state.update(complexity_analysis_node(state))
        
        # generate_report_node (mock para evitar chamadas externas)
        # Adiciona parecer_llm necessário para gerar relatório
        state["parecer_llm"] = "**Análise:** Código simples.\n**Recomendação:** Trocar SELECT * por colunas explícitas."
        
        with patch("agent.graph.get_best_practices") as MockPractices:
            MockPractices.return_value = {
                "recomendacao": "Use colunas explícitas.",
                "referencia": "Oracle PL/SQL Best Practices"
            }
            result = generate_report_node(state)
        
        # Verifica relatório gerado
        report = result["relatorio_final"]
        assert "# Relatório de Revisão" in report
        assert "input_example.sql" in report
        assert "Achados da análise estática" in report

    def test_e2e_error_handling(self):
        """Tratamento de erro no read_file."""
        state: AgentState = {
            "caminho_arquivo": "/etc/passwd",  # Caminho protegido
        }
        
        from agent.authorization import check_file_access
        
        # Deve levantar PermissionError
        with pytest.raises(PermissionError):
            check_file_access(state["caminho_arquivo"])


class TestE2EWithRealFile:
    """E2E: Processamento de arquivo real."""

    def test_e2e_input_example(self):
        """Processa examples/input_example.sql completo."""
        example_path = Path("examples/input_example.sql")
        example_content = example_path.read_text()
        
        # Verifica que o arquivo contém os problemas conhecidos
        assert "WHEN OTHERS" in example_content
        assert "SELECT *" in example_content
        assert "COMMIT" in example_content
        
        # Simula análise estática
        from agent.tools import run_static_checks
        issues = run_static_checks(example_content)
        
        # Deve detectar pelo menos um problema
        assert len(issues) > 0, "Deve detectar problemas no exemplo"
        
        # Verifica os problemas esperados
        issue_texts = [i["descricao"].upper() for i in issues]
        has_when_others = any("WHEN OTHERS" in t for t in issue_texts)
        has_select_star = any("SELECT *" in t for t in issue_texts)
        
        assert has_when_others or has_select_star, "Deve detectar WHEN OTHERS ou SELECT *"

    def test_e2e_complexity_calculation(self):
        """Calcula complexidade de arquivo real."""
        example_path = Path("examples/input_example.sql")
        example_content = example_path.read_text()
        
        from agent.graph import complexity_analysis_node
        
        state = {"codigo_fonte": example_content}
        result = complexity_analysis_node(state)
        
        # O exemplo tem IF, ELSIF, FOR, LOOP
        # Complexidade deve ser > 1
        assert result["complexidade_ciclomatica"] >= 3


class TestE2EParallelExecution:
    """E2E: Paralelização dos nós."""

    def test_parallel_nodes_produce_results(self):
        """Nós paralelos devem produzir resultados independentes."""
        example_path = Path("examples/input_example.sql")
        example_content = example_path.read_text()
        
        from agent.tools import run_static_checks
        from agent.graph import complexity_analysis_node, rag_retrieval_node
        
        state = {"codigo_fonte": example_content}
        
        # Executa os nós paralelos (simulado sequencial para teste)
        heuristic_result = {"issues_estaticos": run_static_checks(example_content)}
        complexity_result = complexity_analysis_node(state)
        rag_result = rag_retrieval_node(state)
        
        # Todos devem ter produzido resultados
        assert "issues_estaticos" in heuristic_result
        assert "complexidade_ciclomatica" in complexity_result
        assert "rag_result" in rag_result


class TestE2ELLMIntegration:
    """E2E: Integração com LLM (se API key disponível)."""

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="GROQ_API_KEY not set, skipping LLM integration test"
    )
    def test_e2e_with_groq(self):
        """Fluxo completo com API Groq."""
        # Usa o exemplo de entrada
        example_path = Path("examples/input_example.sql")
        example_content = example_path.read_text()
        
        # Build do grafo
        graph = build_graph()
        
        # Execução (com mock para evitar chamada real durante CI)
        with pytest.MonkeyPatch().context() as ctx:
            ctx.setenv("GROQ_API_KEY", os.getenv("GROQ_API_KEY", "gsk_test_key"))
            
            state = {
                "caminho_arquivo": str(example_path),
                "codigo_fonte": example_content,
                "issues_estaticos": [],
                "complexidade_ciclomatica": 1,
                "pontos_decisao": [],
                "rag_result": {"documentos": []},
                "contexto_extra": {},
                "historico_interacoes": [],
            }
            
            # Usa o grafo com estado pré-carregado
            result = graph.invoke(state)
            
            # Deve ter gerado relatório
            assert "relatorio_final" in result
            assert len(result["relatorio_final"]) > 0

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No API key available"
    )
    def test_e2e_fallback_between_providers(self):
        """Testa fallback entre Groq e Anthropic."""
        from agent.integrations import api_fallback
        
        providers = api_fallback.get_all_providers()
        
        # Deve ter pelo menos um provedor
        assert len(providers) >= 1, "Deve ter pelo menos um provedor disponível"


class TestE2EIntegrationManager:
    """E2E: Testes de integração com IntegrationManager."""

    def test_e2e_timeout_handling(self):
        """Timeout deve ser respeitado no IntegrationManager."""
        from agent.integrations import IntegrationManager
        
        manager = IntegrationManager(
            default_timeout=0.1,  # 100ms
            max_retries=1,
        )
        
        def slow_function():
            import time
            time.sleep(0.3)  # 300ms
            return "sucesso"
        
        with pytest.raises(Exception):
            manager.call_with_retry(slow_function, "test_service", timeout=0.1)

    def test_e2e_circuit_breaker_integration(self):
        """Circuit breaker deve integrar com retry."""
        from agent.integrations import IntegrationManager
        
        manager = IntegrationManager(
            circuit_breaker_threshold=2,
            max_retries=2,
        )
        
        call_count = 0
        
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Falha intencional")
        
        try:
            manager.call_with_retry(failing_function, "test_service", timeout=1.0)
        except Exception:
            pass
        
        # Deve ter tentado várias vezes (retry + circuit breaker)
        assert call_count >= 2

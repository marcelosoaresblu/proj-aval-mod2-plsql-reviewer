"""
Estado compartilhado do agente revisor de PL/SQL.

Esse TypedDict é o "contexto" que passa por todos os nós do grafo.
Cada nó lê o que precisa e escreve o que descobriu, sem perder o que
os  nós anteriores já tinham colocado ali (memória de execução).
"""

from typing import TypedDict, List, Optional


class StaticIssue(TypedDict):
    """Um achado da análise estática (regex/heurísticas)."""
    linha: int
    severidade: str  # "alta", "media", "baixa"
    regra: str
    descricao: str


class AgentState(TypedDict):
    # --- entrada ---
    caminho_arquivo: str

    # --- preenchido pelo nó read_file ---
    codigo_fonte: Optional[str]

    # --- preenchido pelo nó static_analysis ---
    issues_estaticos: List[StaticIssue]

    # --- preenchido pelo nó llm_review ---
    parecer_llm: Optional[str]

    # --- preenchido pelo nó generate_report ---
    relatorio_final: Optional[str]

    # --- controle de erros ---
    erro: Optional[str]

"""
Estado compartilhado do agente revisor de PL/SQL.

Esse TypedDict é o "contexto" que passa por todos os nós do grafo.
Cada nó lê o que precisa e escreve o que descobriu, sem perder o que
os  nós anteriores já tinham colocado ali (memória de execução).

Adicionalmente, o agente usa:
- Checkpointer: persistência de estado entre sessões
- RAG: recuperação de documentação Oracle PL/SQL baseada no código
- Histórico: histórico de interações para contexto contínuo
"""

from typing import TypedDict, List, Optional, Dict, Any


class ChatMessage(TypedDict):
    """Uma mensagem de chat (para histórico de interações)."""
    role: str  # "user" ou "assistant"
    content: str
    timestamp: str  # ISO format

class StaticIssue(TypedDict):
    """Um achado da análise estática (regex/heurísticas)."""
    linha: int
    severidade: str  # "alta", "media", "baixa"
    regra: str
    descricao: str

class RAGResult(TypedDict):
    """Resultado de recuperação de contexto via RAG."""
    documentos: List[Dict[str, Any]]  # Documentos relevantes recuperados
    queries: List[str]  # Queries usadas na busca
    score: float  # Score médio de relevância (0-1)

class AgentState(TypedDict):
    # --- entrada ---
    caminho_arquivo: str
    session_id: Optional[str]  # ID da sessão para persistência
    contexto_extra: Optional[Dict[str, Any]]  # Contexto extra para enriquecer o prompt

    # --- preenchido pelo nó read_file ---
    codigo_fonte: Optional[str]

    # --- preenchido pelo nó static_analysis ---
    issues_estaticos: List[StaticIssue]

    # --- preenchido pelo nó rag_retrieval ---
    rag_result: Optional[RAGResult]

    # --- preenchido pelo nó llm_review ---
    parecer_llm: Optional[str]

    # --- preenchido pelo nó generate_report ---
    relatorio_final: Optional[str]

    # --- controle de erros ---
    erro: Optional[str]

    # --- histórico de interações (para persistência) ---
    historico_interacoes: List[ChatMessage]

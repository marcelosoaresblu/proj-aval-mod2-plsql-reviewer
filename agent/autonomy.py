"""
Módulo de definição de limites de autonomia para o agente revisor de PL/SQL.

Define quando uma ação pode ser executada, bloqueada ou requer aprovação humana.

Estrutura de autonomy levels:
- LEVEL_0 (automático): Ações seguras, sem custo, sem risco
- LEVEL_1 (monitorado): Ações com custo baixo ou risco moderado
- LEVEL_2 (aprovado): Ações com custo alto ou risco significativo
- LEVEL_3 (bloqueado): Ações proibidas, requerem intervenção humana explícita
"""

from enum import IntEnum
from typing import Any


class AutonomyLevel(IntEnum):
    """Níveis de autonomia."""
    BLOCKED = 3      # Bloqueado - requer aprovação humana explícita
    APPROVED = 2     # Aprovado - requer aprovação explícita
    MONITORED = 1    # Monitorado - pode executar com monitoramento
    AUTO = 0         # Automático - executa sem intervenção


class AutonomyPolicy:
    """Política de autonomia para o agente revisor de PL/SQL."""

    # Custo estimado por operação (em tokens)
    COSTS = {
        "read_file": 0,                    # Leitura local
        "static_analysis": 0,              # Análise regex
        "complexity_analysis": 0,          # Análise regex
        "rag_retrieval": 0,                # Busca local
        "llm_review": 1500,                # LLM (max_tokens)
        "get_best_practices": 0,           # Base local
        "generate_report": 0,              # Formatação
    }

    # Risco estimado por operação
    RISKS = {
        "read_file": "low",                # Acesso a arquivos locais
        "static_analysis": "low",          # Análise estática
        "complexity_analysis": "low",      # Análise estática
        "rag_retrieval": "low",            # Busca local
        "llm_review": "medium",            # API externa
        "get_best_practices": "low",       # Base local
        "generate_report": "low",          # Geração local
    }

    # Limites de custo por nível (exclusivo no limite superior)
    # Ex: AUTO até 1499, MONITORED até 4999, etc.
    COST_LIMITS = {
        AutonomyLevel.AUTO: 1499,          # Até 1499 tokens
        AutonomyLevel.MONITORED: 4999,     # Até 4999 tokens
        AutonomyLevel.APPROVED: 14999,     # Até 14999 tokens
        AutonomyLevel.BLOCKED: float('inf'),  # Ilimitado (mas bloqueado)
    }

    # Ações que nunca são automáticas
    FORBIDDEN_ACTIONS = {
        "execute_sql",        # Executar SQL no banco
        "delete_file",        # Deletar arquivos
        "modify_file",        # Modificar arquivos (exceto relatório)
        "deploy",             # Deploy em produção
        "send_notification",  # Enviar notificações externas
    }

    # Ações que sempre requerem aprovação
    ALWAYS_APPROVE = {
        "deploy_production",  # Deploy em produção
        "modify_schema",      # Modificar schema do banco
    }

    # Variáveis de ambiente que nunca devem ser expostas
    SENSITIVE_ENV_VARS = [
        "GROQ_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
    ]


def get_autonomy_level(action: str, params: dict[str, Any] | None = None) -> AutonomyLevel:
    """Determina o nível de autonomia para uma ação.
    
    Args:
        action: Nome da ação
        params: Parâmetros da ação (para cálculo de custo/risco)
        
    Returns:
        Nível de autonomia (AUTO, MONITORED, APPROVED, BLOCKED)
    """
    # Verificar se é uma ação proibida
    if action in AutonomyPolicy.FORBIDDEN_ACTIONS:
        return AutonomyLevel.BLOCKED

    # Verificar se é uma ação que sempre requer aprovação
    if action in AutonomyPolicy.ALWAYS_APPROVE:
        return AutonomyLevel.APPROVED

    # Calcular custo da ação
    cost = AutonomyPolicy.COSTS.get(action, 100)

    # Determinar nível baseado no custo (ordem crescente)
    # O primeiro limite que o custo atinge ou excede define o nível
    for level, limit in sorted(AutonomyPolicy.COST_LIMITS.items()):
        if cost <= limit:
            return level

    # Se o custo excede todos os limites, é BLOCKED
    return AutonomyLevel.BLOCKED


def can_execute(action: str, params: dict[str, Any] | None = None) -> bool:
    """Verifica se uma ação pode ser executada automaticamente.
    
    Args:
        action: Nome da ação
        params: Parâmetros da ação
        
    Returns:
        True se pode executar, False caso contrário
    """
    level = get_autonomy_level(action, params)
    return level <= AutonomyLevel.MONITORED


def requires_approval(action: str, params: dict[str, Any] | None = None) -> bool:
    """Verifica se uma ação requer aprovação humana.
    
    Args:
        action: Nome da ação
        params: Parâmetros da ação
        
    Returns:
        True se requer aprovação, False caso contrário
    """
    level = get_autonomy_level(action, params)
    return level >= AutonomyLevel.APPROVED


def is_blocked(action: str, params: dict[str, Any] | None = None) -> bool:
    """Verifica se uma ação está bloqueada.
    
    Args:
        action: Nome da ação
        params: Parâmetros da ação
        
    Returns:
        True se está bloqueada, False caso contrário
    """
    level = get_autonomy_level(action, params)
    return level >= AutonomyLevel.BLOCKED


def check_file_action(caminho: str) -> AutonomyLevel:
    """Verifica o nível de autonomia para ações de arquivo.
    
    Args:
        caminho: Caminho do arquivo
        
    Returns:
        Nível de autonomia
    """
    # Leitura de arquivos locais é sempre auto
    return AutonomyLevel.AUTO


def check_llm_action(model: str, max_tokens: int) -> AutonomyLevel:
    """Verifica o nível de autonomia para ações de LLM.
    
    Args:
        model: Nome do modelo
        max_tokens: Número máximo de tokens
        
    Returns:
        Nível de autonomia
    """
    # LLMs com max_tokens <= 1000 são auto
    if max_tokens <= 1000:
        return AutonomyLevel.AUTO

    # LLMs com max_tokens <= 5000 são monitorados
    if max_tokens <= 5000:
        return AutonomyLevel.MONITORED

    # LLMs com max_tokens > 5000 requerem aprovação
    return AutonomyLevel.APPROVED


def validate_autonomy(action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Valida a autonomia de uma ação e retorna informações detalhadas.
    
    Args:
        action: Nome da ação
        params: Parâmetros da ação
        
    Returns:
        Dicionário com:
        - allowed: Se a ação pode ser executada
        - level: Nível de autonomia
        - requires_approval: Se requer aprovação
        - reason: Motivo da decisão
    """
    level = get_autonomy_level(action, params)
    allowed = level <= AutonomyLevel.MONITORED
    requires_approval = level >= AutonomyLevel.APPROVED

    reason = f"Ação '{action}' tem nível {level.name} ({level})"

    if action in AutonomyPolicy.FORBIDDEN_ACTIONS:
        reason = f"Ação '{action}' é proibida por política de segurança"
    elif action in AutonomyPolicy.ALWAYS_APPROVE:
        reason = f"Ação '{action}' sempre requer aprovação humana"
    elif params and params.get("max_tokens", 0) > 1000:
        reason = f"Ação '{action}' usa muitos tokens ({params.get('max_tokens')})"

    return {
        "allowed": allowed,
        "level": level,
        "requires_approval": requires_approval,
        "reason": reason,
    }

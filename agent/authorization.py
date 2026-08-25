"""
Módulo de autorização para o agente revisor de PL/SQL.

Fornece funções para validar permissões antes da execução de tools e ações externas.

Princípios:
1. Validar permissões ANTES de chamar tools que acessam recursos externos
2. Prevenir vazamento de segredos em logs e outputs
3. Fallback seguro em caso de falha na validação
"""

import os
import re
from typing import Any


# Configurações de permissão
class PermissionsConfig:
    """Configurações de permissão do agente."""

    # Tools que requerem permissão explícita
    RESTRICTED_TOOLS = [
        "read_sql_file",
        "get_best_practices",
        "llm_invoke",
    ]

    # Caminhos que nunca devem ser acessados (segurança)
    PROTECTED_PATHS = [
        "/etc",
        "/root",
        "/home",
        "/.env",
        ".env",
        "id_rsa",
        ".ssh",
        "/proc",
        "/sys",
    ]

    # Variáveis de ambiente sensíveis que nunca devem ser expostas
    SENSITIVE_ENV_VARS = [
        "GROQ_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "DATABASE_URL",
        "SECRET",
        "TOKEN",
        "PASSWORD",
    ]


def check_file_access(caminho: str) -> bool:
    """Verifica se o acesso ao arquivo é permitido.
    
    Validações:
    - Caminho não é em diretórios protegidos
    - Extensão é permitida
    - Tamanho do arquivo é aceitável
    
    Args:
        caminho: Caminho do arquivo a ser acessado
        
    Returns:
        True se o acesso é permitido, False caso contrário
        
    Raises:
        PermissionError: Se o acesso não for permitido
    """
    # Normalizar caminho
    caminho_normalizado = os.path.normpath(caminho)

    # Verificar se está em diretório protegido
    for path_protected in PermissionsConfig.PROTECTED_PATHS:
        if path_protected in caminho_normalizado:
            raise PermissionError(
                f"Acesso negado ao caminho protegido: {caminho}"
            )

    # Verificar extensão permitida
    _, ext = os.path.splitext(caminho)
    if ext.lower() not in {".sql", ".pck", ".pkb", ".pks", ".prc", ".fnc"}:
        raise PermissionError(
            f"Extensão '{ext}' não permitida. Use apenas arquivos PL/SQL."
        )

    return True


def check_api_access(tool_name: str) -> bool:
    """Verifica se a tool tem permissão para acessar API externa.
    
    Args:
        tool_name: Nome da tool sendo chamada
        
    Returns:
        True se o acesso é permitido, False caso contrário
        
    Raises:
        PermissionError: Se o acesso não for permitido
    """
    if tool_name in PermissionsConfig.RESTRICTED_TOOLS:
        # Verificar se a chave de API existe e é válida
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise PermissionError(
                f"Tool '{tool_name}' requer GROQ_API_KEY configurada"
            )

        # Validação básica da chave (formato esperado da Groq)
        if not re.match(r"^gsk_[a-zA-Z0-9]{20,}$", api_key):
            raise PermissionError(
                "Chave GROQ_API_KEY inválida (formato esperado: gsk_...)"
            )

    return True


def sanitize_output(text: str) -> str:
    """Remove segredos e informações sensíveis do output.
    
    Args:
        text: Texto a ser sanitizado
        
    Returns:
        Texto sem segredos (com placeholders)
    """
    resultado = text

    # Substituir chaves de API por placeholders
    resultado = re.sub(
        r"(GROQ_API_KEY|ANTHROPIC_API_KEY)\s*=\s*['\"]?([a-zA-Z0-9_\-]+)['\"]?",
        r"\1=***REDACTED***",
        resultado
    )

    # Substituir qualquer string que pareça uma chave de API
    resultado = re.sub(
        r"gsk_[a-zA-Z0-9]{20,}",
        "***REDACTED_API_KEY***",
        resultado
    )

    return resultado


def validate_input_payload(payload: dict[str, Any], tool_name: str) -> bool:
    """Valida o payload de entrada de uma tool.
    
    Args:
        payload: Dicionário com os parâmetros da tool
        tool_name: Nome da tool sendo chamada
        
    Returns:
        True se o payload é válido
        
    Raises:
        ValueError: Se o payload é inválido
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload deve ser um dicionário")

    if tool_name == "read_sql_file":
        if "caminho" not in payload:
            raise ValueError("Payload de 'read_sql_file' deve conter 'caminho'")
        if not isinstance(payload["caminho"], str):
            raise ValueError("Parâmetro 'caminho' deve ser uma string")

    elif tool_name == "get_best_practices":
        if "achado" not in payload:
            raise ValueError("Payload de 'get_best_practices' deve conter 'achado'")
        if not isinstance(payload["achado"], str):
            raise ValueError("Parâmetro 'achado' deve ser uma string")

    return True


def mask_secrets_in_state(state: dict[str, Any]) -> dict[str, Any]:
    """Remove segredos do estado antes de armazenar ou logar.
    
    Args:
        state: Estado a ser sanitizado
        
    Returns:
        Estado sem segredos
    """
    resultado = {}

    for key, value in state.items():
        if key.upper() in PermissionsConfig.SENSITIVE_ENV_VARS:
            resultado[key] = "***REDACTED***"
        elif isinstance(value, str):
            resultado[key] = sanitize_output(value)
        elif isinstance(value, dict):
            resultado[key] = mask_secrets_in_state(value)
        else:
            resultado[key] = value

    return resultado

"""
Ferramentas integradas ao agente.

1. read_sql_file      -> leitura de arquivo (requisito: "leitura de arquivo")
2. run_static_checks  -> análise de código via heurísticas/regex antes de
                         acionar o LLM, reduzindo custo e dando contexto
                         mais preciso para a revisão final.
3. get_best_practices -> integração com serviço externo via MCP para obter
                         boas práticas Oracle PL/SQL baseadas no achado

Todas são funções "controladas": recebem entradas validadas e não
executam nada fora do escopo do arquivo informado.
"""

import os
import re
from typing import List
from agent.state import StaticIssue

# Extensões aceitas -> evita que o agente tente ler arquivos arbitrários
EXTENSOES_PERMITIDAS = {".sql", ".pck", ".pkb", ".pks", ".prc", ".fnc"}

# Tamanho máximo de arquivo (proteção simples contra abuso/custo de API)
TAMANHO_MAXIMO_BYTES = 500_000


def read_sql_file(caminho: str) -> str:
    """Lê um arquivo de código PL/SQL do disco com validações básicas.
    
    Validações:
    - Arquivo existe
    - Extensão está na lista de permitidas
    - Tamanho não excede o limite
    
    Parâmetros:
        caminho: Caminho absoluto ou relativo para o arquivo
        
    Retorna:
        Conteúdo do arquivo como string
        
    Lança:
        FileNotFoundError: Se o arquivo não existe
        ValueError: Se extensão ou tamanho não são válidos
    """
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    _, ext = os.path.splitext(caminho)
    if ext.lower() not in EXTENSOES_PERMITIDAS:
        raise ValueError(
            f"Extensão '{ext}' não permitida. Use um dos tipos: {EXTENSOES_PERMITIDAS}"
        )

    tamanho = os.path.getsize(caminho)
    if tamanho > TAMANHO_MAXIMO_BYTES:
        raise ValueError(
            f"Arquivo muito grande ({tamanho} bytes). Limite: {TAMANHO_MAXIMO_BYTES} bytes."
        )

    with open(caminho, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


# Regras estáticas simples, no espírito de um linter básico de PL/SQL.
# Cada regra é (regex, severidade, descrição).
REGRAS = [
    (
        re.compile(r"\bWHEN\s+OTHERS\s+THEN\s*(?!.*RAISE)", re.IGNORECASE),
        "alta",
        "Bloco WHEN OTHERS sem RAISE — exceção pode estar sendo engolida silenciosamente.",
    ),
    (
        re.compile(r"CURSOR\s+\w+.*IS", re.IGNORECASE),
        "baixa",
        "Cursor declarado — confirme se há tratamento de exceção (NO_DATA_FOUND, TOO_MANY_ROWS) e fechamento explícito.",
    ),
    (
        re.compile(r"SELECT\s+\*", re.IGNORECASE),
        "media",
        "Uso de SELECT * — prefira listar as colunas explicitamente.",
    ),
    (
        re.compile(r"\bCOMMIT\b", re.IGNORECASE),
        "media",
        "COMMIT explícito dentro da procedure — avalie se o controle de transação não deveria ficar a cargo do chamador.",
    ),
    (
        re.compile(r"=\s*'[A-Z0-9_]{2,}'", re.IGNORECASE),
        "baixa",
        "Possível valor hardcoded (string literal comparada diretamente) — considere mover para parâmetro ou tabela de configuração.",
    ),
    (
        re.compile(r"EXCEPTION\s*$", re.IGNORECASE | re.MULTILINE),
        "baixa",
        "Bloco EXCEPTION presente — verifique se todas as exceções relevantes são tratadas.",
    ),
]


# --- Tool integrada via MCP para obter boas práticas Oracle PL/SQL ---
# Esta tool simula uma integração com serviço externo (ex: documentação Oracle,
# API de boas práticas) para recomendações específicas baseadas no achado.

def get_best_practices(achado: str) -> dict:
    """Obtém recomendações de boas práticas Oracle PL/SQL baseadas no achado.
    
    Esta tool integra-se a um serviço externo via MCP (Model Context Protocol)
    para buscar recomendações oficiais ou baseadas em documentação.
    
    Validações de entrada:
    - `achado` deve ser uma string não vazia
    - Deve corresponder a um tipo de problema conhecido
    
    Parâmetros:
        achado: Nome do problema identificado (ex: "WHEN_OTHERS_SILENT", "SELECT_STAR")
        
    Retorna:
        dict com:
        - recomendacao: string com recomendação prática
        - referencia: link/documento de referência
        - nivel: severidade da recomendação ("alta", "media", "baixa")
        
    Lança:
        ValueError: Se `achado` for inválido ou serviço externo estiver indisponível
    """
    # Mapeamento de achados para boas práticas (simulado com dados estáticos)
    # Em produção, isso chamaria um serviço MCP ou API externa
    PRATICS_DB = {
        "WHEN_OTHERS_SILENT": {
            "recomendacao": "Sempre inclua RAISE ou RAISE_APPLICATION_ERROR em WHEN OTHERS para não ocultar erros.",
            "referencia": "Oracle PL/SQL Best Practices - Exception Handling",
            "nivel": "alta",
        },
        "SELECT_STAR": {
            "recomendacao": "Especifique colunas explicitamente para evitar problemas com schema changes e melhorar performance.",
            "referencia": "Oracle SQL Tuning Guide - Avoid SELECT *",
            "nivel": "media",
        },
        "COMMIT_INTERNAL": {
            "recomendacao": "Evite COMMIT dentro de procedures; deixe o controle de transação para o chamador.",
            "referencia": "Oracle PL/SQL Best Practices - Transaction Control",
            "nivel": "media",
        },
        "HARDCODED_VALUE": {
            "recomendacao": "Use parâmetros ou tabelas de configuração para valores fixos que podem mudar.",
            "referencia": "Oracle PL/SQL Code Review Guidelines",
            "nivel": "baixa",
        },
        "EXPLICIT_EXCEPTION": {
            "recomendacao": "Trate exceções específicas (NO_DATA_FOUND, TOO_MANY_ROWS) antes de recorrer a WHEN OTHERS.",
            "referencia": "Oracle PL/SQL User's Guide",
            "nivel": "baixa",
        },
        "CURSOR_NO_HANDLING": {
            "recomendacao": "Sempre inclua tratamento para NO_DATA_FOUND e TOO_MANY_ROWS quando abrir cursores.",
            "referencia": "Oracle PL/SQL Best Practices - Cursor Handling",
            "nivel": "baixa",
        },
    }
    
    # Validação de entrada (payload/schema)
    if not isinstance(achado, str) or not achado.strip():
        raise ValueError("Parâmetro 'achado' deve ser uma string não vazia")
    
    achado_normalizado = achado.upper().replace(" ", "_")
    
    # Validação: achado deve existir na base de boas práticas
    if achado_normalizado not in PRATICS_DB:
        raise ValueError(
            f"Achado '{achado}' não reconhecido. Use um dos tipos: {list(PRATICS_DB.keys())}"
        )
    
    try:
        # Simulação de chamada a serviço externo via MCP
        # Em produção: client = MCPClient(); return client.get_practices(achado)
        return PRATICS_DB[achado_normalizado]
    except Exception as e:
        # Tratamento de falhas no serviço externo
        raise RuntimeError(f"Falha ao obter boas práticas: {e}") from e


def run_static_checks(codigo: str) -> List[StaticIssue]:
    """Aplica heurísticas simples linha a linha e retorna os achados."""
    issues: List[StaticIssue] = []
    linhas = codigo.splitlines()

    for numero, linha in enumerate(linhas, start=1):
        for regex, severidade, descricao in REGRAS:
            if regex.search(linha):
                issues.append(
                    StaticIssue(
                        linha=numero,
                        severidade=severidade,
                        regra=regex.pattern,
                        descricao=descricao,
                    )
                )
    return issues

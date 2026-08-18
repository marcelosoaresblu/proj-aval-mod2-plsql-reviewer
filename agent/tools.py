"""
Ferramentas integradas ao agente.

1. read_sql_file      -> leitura de arquivo (requisito: "leitura de arquivo")
2. run_static_checks  -> análise de código via heurísticas/regex antes de
                         acionar o LLM, reduzindo custo e dando contexto
                         mais preciso para a revisão final.

Ambas  são funções "controladas": recebem entradas validadas e não
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
    """Lê um arquivo de código PL/SQL do disco com validações básicas."""
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

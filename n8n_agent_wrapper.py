#!/usr/bin/env python3
"""
Wrapper para integrar o agente PL/SQL com n8n.

Este script pode ser chamado por workflows do n8n via executeCommand node.
Ele processa um arquivo PL/SQL e gera um relatório.

Uso com n8n:
  command: python3 n8n_agent_wrapper.py {{ $json.file_path }} --output {{ $json.output_file }}

Parâmetros:
  arquivo: Caminho do arquivo .sql a ser revisado
  --output ou -o: Caminho do arquivo de saída (opcional)
"""

import argparse
import sys
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from agent.graph import build_graph

load_dotenv()  # lê variáveis de ambiente do arquivo .env


def main():
    parser = argparse.ArgumentParser(description="Wrapper do Agente Revisor de PL/SQL para n8n")
    parser.add_argument("arquivo", help="Caminho do arquivo .sql a revisar")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Caminho do arquivo de saída (.md). Se omitido, imprime no terminal.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Retorna saída em formato JSON para processamento pelo n8n",
    )
    args = parser.parse_args()

    # Verificar se o arquivo existe
    arquivo_path = Path(args.arquivo)
    if not arquivo_path.exists():
        error_msg = f"Arquivo não encontrado: {args.arquivo}"
        if args.json:
            print(json.dumps({
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat(),
            }))
        else:
            print(f"❌ {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Executar o agente
    agente = build_graph()
    resultado = agente.invoke({"caminho_arquivo": str(arquivo_path)})

    # Processar resultado
    if resultado.get("erro"):
        error_msg = resultado["erro"]
        if args.json:
            print(json.dumps({
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat(),
            }))
        else:
            print(f"❌ Erro na análise: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Salvar ou retornar relatório
    relatorio = resultado["relatorio_final"]

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(relatorio)

        if args.json:
            print(json.dumps({
                "success": True,
                "file_analyzed": str(arquivo_path),
                "output_file": str(output_path),
                "report_size": len(relatorio),
                "timestamp": datetime.now().isoformat(),
            }))
        else:
            print(f"✅ Relatório salvo em: {output_path}")
    else:
        if args.json:
            print(json.dumps({
                "success": True,
                "file_analyzed": str(arquivo_path),
                "report_content": relatorio,
                "report_size": len(relatorio),
                "timestamp": datetime.now().isoformat(),
            }))
        else:
            print(relatorio)


if __name__ == "__main__":
    main()

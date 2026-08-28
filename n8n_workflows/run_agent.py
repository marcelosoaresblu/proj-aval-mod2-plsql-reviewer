#!/usr/bin/env python3
"""
Script para ser chamado pelo n8n via HTTP.
Recebe file_path e output_file via argumentos ou variáveis de ambiente.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from agent.graph import build_graph

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Executar agente PL/SQL via HTTP")
    parser.add_argument("--file_path", default=os.getenv("FILE_PATH"), help="Caminho do arquivo .sql")
    parser.add_argument("--output_file", default=os.getenv("OUTPUT_FILE"), help="Caminho do arquivo de saída")
    parser.add_argument("--json_output", action="store_true", help="Retornar JSON")
    args = parser.parse_args()

    if not args.file_path or not args.output_file:
        error = {"success": False, "error": "file_path e output_file são obrigatórios"}
        print(json.dumps(error))
        sys.exit(1)

    arquivo_path = Path(args.file_path)
    if not arquivo_path.exists():
        error = {"success": False, "error": f"Arquivo não encontrado: {args.file_path}"}
        print(json.dumps(error))
        sys.exit(1)

    try:
        agente = build_graph()
        resultado = agente.invoke({"caminho_arquivo": str(arquivo_path)})

        if resultado.get("erro"):
            error = {"success": False, "error": resultado["erro"]}
            print(json.dumps(error))
            sys.exit(1)

        relatorio = resultado["relatorio_final"]
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(relatorio)

        success = {
            "success": True,
            "file_analyzed": str(arquivo_path),
            "output_file": str(output_path),
            "report_size": len(relatorio),
            "timestamp": "2026-08-26T22:37:00.000Z"
        }
        print(json.dumps(success))

    except Exception as e:
        error = {"success": False, "error": str(e)}
        print(json.dumps(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
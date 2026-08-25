"""
CLI de entrada do agente revisor de PL/SQL.

Uso:
    python -m agent.main examples/input_example.sql
    python -m agent.main examples/output_example.md --saida relatorio.md

Requer a variável de ambiente GROQ_API_KEY configurada (via .env ou
exportada no shell).
"""

import argparse
import sys

from dotenv import load_dotenv

from agent.graph import build_graph

load_dotenv()  # lê o arquivo .env, se existir, e popula os env vars


def main():
    parser = argparse.ArgumentParser(description="Agente revisor de PL/SQL")
    parser.add_argument("arquivo", help="Caminho do arquivo .sql/.pck a revisar")
    parser.add_argument(
        "--saida",
        default=None,
        help="Caminho do arquivo de saída (.md). Se omitido, imprime no terminal.",
    )
    args = parser.parse_args()

    agente = build_graph()
    resultado = agente.invoke({"caminho_arquivo": args.arquivo})

    relatorio = resultado["relatorio_final"]

    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(relatorio)
        print(f"Relatório salvo em: {args.saida}")
    else:
        print(relatorio)

    if resultado.get("erro"):
        sys.exit(1)


if __name__ == "__main__":
    main()

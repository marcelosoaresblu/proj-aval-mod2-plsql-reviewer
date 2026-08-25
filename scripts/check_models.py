#!/usr/bin/env python3
"""
Script para verificar modelos disponíveis na API Groq.

Uso:
    python scripts/check_models.py
"""

import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def check_models():
    """Lista os modelos disponíveis para a chave de API."""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print("❌ GROQ_API_KEY não encontrada no .env")
        print("Crie um arquivo .env com: GROQ_API_KEY=gsk_...")
        return False

    print(f"✅ GROQ_API_KEY encontrada (formato: {api_key[:8]}...)")

    try:
        client = Groq(api_key=api_key)
        models = client.models.list()

        if not models.data:
            print("⚠️  Nenhum modelo retornado pela API")
            return False

        print("\n📦 Modelos disponíveis:")
        for model in sorted(models.data, key=lambda x: x.id):
            print(f"  - {model.id}")

        return True

    except Exception as e:
        print(f"❌ Erro ao consultar modelos: {e}")
        print("\nDicas:")
        print("  1. Verifique se sua chave GROQ_API_KEY é válida")
        print("  2. Acesse https://console.groq.com/keys para verificar sua chave")
        print("  3. Veja os modelos disponíveis em https://console.groq.com/docs/models")
        return False


if __name__ == "__main__":
    check_models()

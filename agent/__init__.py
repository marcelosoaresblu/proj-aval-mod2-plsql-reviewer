"""
Inicialização do pacote do agente revisor de PL/SQL.

Carrega variáveis de ambiente do .env antes de qualquer outro módulo.
Isso garante que api_fallback e outros componentes tenham acesso às chaves.
"""

from dotenv import load_dotenv

load_dotenv()

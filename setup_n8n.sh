#!/bin/bash

# Configuração do ambiente n8n
echo "=== Configuração do Revisor PL/SQL com n8n ==="

# Verificar se o n8n está instalado
if ! command -v n8n &> /dev/null; then
    echo "n8n não encontrado. Instalando..."
    npm install -g n8n
fi

# Criar diretório para workflows
mkdir -p n8n_workflows

# Copiar workflows
echo "Copiando workflows para o diretório..."
cp n8n_workflow.json n8n_workflows/
cp n8n_workflow_watch.json n8n_workflows/
cp n8n_agent_wrapper.py n8n_workflows/

# Criar .env para n8n
cat > n8n_workflows/.env << EOF
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_HOST=localhost
WEBHOOK_URL=http://localhost:5678/webhook
EOF

echo "✅ Configuração concluída!"
echo ""
echo "Para iniciar o n8n:"
echo "  export DISCORD_WEBHOOK_URL='seu_webhook_discord'"
echo "  n8n start --tunnel"
echo ""
echo "Para importar o workflow:"
echo "  1. Acesse http://localhost:5678"
echo "  2. Clique em 'Import from File'"
echo "  3. Selecione o arquivo em n8n_workflows/"
echo ""
echo "Para testar via webhook:"
echo "  curl -X POST http://localhost:5678/webhook/webhook-plsql-review \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"file_path\": \"examples/input_example.sql\", \"notify_channel\": \"test\"}'"
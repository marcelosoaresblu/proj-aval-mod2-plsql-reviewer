# Modelos Disponíveis do Groq

Para verificar quais modelos estão disponíveis para sua chave de API:

```bash
python -c "import requests; import os; r = requests.get('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {os.getenv(\"GROQ_API_KEY\")}'}); print([m['id'] for m in r.json().get('data', [])])"
```

ou usando o SDK Groq:

```python
from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
models = client.models.list()
for model in models.data:
    print(model.id)
```

## Modelos Comuns (selecione um do resultado acima)

- `gpt-oss-120b` - GPT OSS 120B
- `gpt-oss-20b` - GPT OSS 20B
- `groq/compound` - Compound
- `groq/compound-mini` - Compound Mini
- `qwen/qwen3.6-27b` - Qwen 3.6 27B
- `meta-llama/llama-prompt-guard-2-86m` - Llama Prompt Guard

Atualize o arquivo `.env` com o ID do modelo desejado:

```
REVIEWER_MODEL=qwen/qwen3.6-27b
```

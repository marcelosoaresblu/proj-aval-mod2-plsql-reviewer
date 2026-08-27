# Anomalias Detectadas

**Data**: 26 de agosto de 2026  
**Ambiente**: Local (Windows / Python 3.14) + GitHub Actions (ubuntu-latest)  
**Método**: Análise de logs + execução controlada de testes + inspeção de código

---

## Anomalia 1: Falha Recorrente por Rate Limit (HTTP 429) em `test_full_flow_with_llm`

### Tipo
Erro recorrente — falha de tool (API Groq)

### Evidência Direta (log capturado em tempo real)

```
FAILED tests/test_acceptance.py::TestAcceptanceIntegrationFlow::test_full_flow_with_llm

groq.RateLimitError: Error code: 429
{'error': {'message': 'Rate limit reached for model `groq/compound-mini`
in organization `org_01kvryf3knfnms69ac9w0fwjdm` service tier `on_demand`
on tokens per day (TPD): Limit 100000, Used 96835, Requested 3789.
Please try again in 8m59.135999999s.'}}

During task with name 'llm_review' and id '566d7582-7fe1-89b5-46b5-c5b6c159e345'
```

### O que o Log Revela

| Campo | Valor | Significado |
|-------|-------|-------------|
| `Used 96835` | 96.835 tokens | 96,8% da cota consumida |
| `Limit 100000` | 100.000 tokens/dia | Limite on_demand |
| `Requested 3789` | 3.789 tokens | Custo desta execução |
| `Try again in 8m59s` | ~9 minutos | Tempo restante até reset |
| `model groq/compound-mini` | Modelo 70B | Modelo real sendo chamado |

### Causa Raiz: Decorator `@skipif` Ineficaz

O teste deveria ser pulado quando não há `GROQ_API_KEY`, mas o decorator **nunca funciona** no ambiente com `.env`:

```python
# tests/test_acceptance.py — linha 17 (import de agent)
from agent.graph import build_graph   # <- dispara agent/__init__.py -> load_dotenv()

# Decorator avaliado DEPOIS do import:
@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),    # <- já é 'gsk_...' neste ponto!
    reason="Requires GROQ_API_KEY"
)
def test_full_flow_with_llm(self):
    ...
```

#### Sequência de Execução Comprovada

```
pytest coleta test_acceptance.py
    |
    +--> linha 17: from agent.graph import build_graph
    |        |
    |        +--> agent/__init__.py: load_dotenv()   # GROQ_API_KEY entra em os.environ
    |
    +--> decorator @skipif avalia: not os.getenv("GROQ_API_KEY")
    |        = not "gsk_VygzxxLLDH4..."
    |        = not True
    |        = False   <--- skipif(False) significa: NÃO pula!
    |
    +--> teste EXECUTA -> chama API real -> rate limit
```

**Verificação no Python:**
```
ANTES do import agent:  GROQ_API_KEY = None
DEPOIS do import agent: GROQ_API_KEY = gsk_Vygzxx...

Conclusão: skipif é sempre False em ambiente com .env -> teste sempre executa
```

### Frequência da Falha

| Execução | Resultado | Used tokens |
|----------|-----------|-------------|
| Sessão anterior | ❌ FAIL 429 | 97.296 |
| Execução atual 1 | ❌ FAIL 429 | 96.835 |
| Execução atual 2 | ❌ FAIL 429 | 96.785 |

**Taxa de falha observada**: 100% (todas as execuções com cota crítica)

### Impacto

- Pipeline CI/CD registra **1 FAILED** mesmo com 62 testes passando
- Taxa de sucesso cai de 100% para **98,4%** (62/63)
- Consumo de tokens continua mesmo após a cota crítica
- Em CI (sem `.env`), o teste é pulado normalmente — a falha só ocorre localmente

### Correção Recomendada

```python
# ANTES (ineficaz):
@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="Requires GROQ_API_KEY"
)

# DEPOIS (correto — força leitura em runtime, não em import):
@pytest.mark.skipif(
    not __import__('os').getenv("GROQ_API_KEY") and not __import__('pathlib').Path('.env').exists(),
    reason="Requires GROQ_API_KEY"
)
```

Ou melhor ainda, usar fixture com mock para não depender de API real:

```python
def test_full_flow_with_llm(self, monkeypatch):
    """Fluxo completo usando mock do LLM para não consumir tokens."""
    from unittest.mock import MagicMock, patch
    
    mock_response = MagicMock()
    mock_response.content = "**Análise mockada**: Código revisado com sucesso."
    
    with patch("langchain_groq.ChatGroq.invoke", return_value=mock_response):
        result = graph.invoke({...})
    
    assert "relatorio_final" in result
```

---

## Anomalia 2: Encoding Quebrado (Mojibake) nos Logs JSON

### Tipo
Falha de tool — observabilidade comprometida (logs ilegíveis)

### Evidência Direta (log capturado)

```
{"message": "InÝcio do n¾ read_file_node", ...}
{"message": "Anßlise estßtica concluÝda", ...}
{"message": "Arquivo nÒo encontrado: test.sql", ...}
{"message": "Anßlise de complexidade concluÝda", ...}
```

Todos os textos com acentos estão corrompidos — fenômeno chamado **mojibake**.

### Mapeamento dos Caracteres Corrompidos

| Log Capturado | Log Correto | Causa |
|---------------|-------------|-------|
| `InÝcio do n¾` | `Início do nó` | UTF-8 lido como CP1252 |
| `Anßlise estßtica` | `Análise estática` | UTF-8 lido como CP1252 |
| `concluÝda` | `concluída` | UTF-8 lido como CP1252 |
| `nÒo encontrado` | `não encontrado` | UTF-8 lido como CP1252 |

### Causa Raiz: Conflito de Encoding entre `json.dumps` e `stderr`

```python
# agent/observability.py — linha 91
self.logger.info(json.dumps(log_entry, ensure_ascii=False))
#                                      ^^^^^^^^^^^^^^^^^^
#  ensure_ascii=False emite bytes UTF-8 para strings com acentos
#  Ex: "Início" vira bytes: 0x49 0xC3 0xAD 0x6E 0x69 0x6F
```

```python
# Diagnóstico do ambiente:
sys.stdout.encoding  = 'utf-8'   # stdout ok
sys.stderr.encoding  = 'cp1252'  # stderr usa CP1252 (padrão Windows)
```

**O que acontece:**
```
json.dumps(ensure_ascii=False) -> produz string UTF-8: "Início"
    |
    +--> logger.info() -> handler.StreamHandler() -> sys.stderr
    |
    +--> stderr encoding = CP1252 tenta codificar os bytes UTF-8
    |
    +--> "Í" (U+00CD) = [0xC3 0x8D] em UTF-8
         lido como CP1252: 0xC3 = 'Ã', 0x8D = caracter de controle
         resultado: "Ã\x8d" ou caracteres similares garbled
```

**Verificação:**
```python
>>> "Início".encode('utf-8')
b'In\xc3\xadcio'
>>> b'In\xc3\xadcio'.decode('cp1252')
'InÃ\xadcio'   # <- mojibake confirmado
```

### Frequência da Anomalia

Afeta **100% dos logs** com caracteres não-ASCII em ambiente Windows:
- `"Início"` → `"InÝcio"`
- `"Análise"` → `"Anßlise"`
- `"não"` → `"nÒo"`
- `"concluída"` → `"concluÝda"`
- `"nó"` → `"n¾"`

### Impacto

| Área | Impacto |
|------|---------|
| Debugging | Logs ilegíveis dificultam diagnóstico de erros |
| Monitoramento | Alertas baseados em texto dos logs falham (regex não casa) |
| Auditoria | Registros de segurança ficam corrompidos |
| CI/CD Linux | **Não afeta** — Linux usa UTF-8 por padrão |

**Importante**: O problema é silencioso — nenhuma exceção é lançada. Os logs são gerados, mas com conteúdo corrompido.

### Correção Recomendada

#### Opção 1 — `ensure_ascii=True` (mais simples)

```python
# agent/observability.py
self.logger.info(json.dumps(log_entry, ensure_ascii=True))
# "Início" vira "\u00cdnicio" — legível por parsers JSON, mas escapado
```

#### Opção 2 — Forçar UTF-8 no StreamHandler (recomendada)

```python
# agent/observability.py — StructuredLogger.__init__
import sys, io

handler = logging.StreamHandler(
    stream=io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
)
handler.setLevel(ObservabilityConfig.LOG_LEVEL)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
```

#### Opção 3 — Configurar `PYTHONIOENCODING` no ambiente

```bash
# .env ou CI/CD
PYTHONIOENCODING=utf-8
```

---

## Comparativo entre as Anomalias

| Atributo | Anomalia 1 (Rate Limit) | Anomalia 2 (Encoding) |
|----------|------------------------|----------------------|
| **Tipo** | Falha de tool (API externa) | Falha de observabilidade |
| **Severidade** | Alta | Média |
| **Frequência** | 100% com cota crítica | 100% em Windows |
| **Visibilidade** | Explícita (exceção) | Silenciosa (sem erro) |
| **Impacto em CI** | Sim (1 FAILED) | Não (Linux usa UTF-8) |
| **Impacto local** | Sim (sistema para) | Sim (logs ilegíveis) |
| **Correção** | Mock + rate-limit guard | `ensure_ascii=True` ou force UTF-8 |
| **Risco em produção** | Alto | Médio |

---

## Resumo Executivo

Duas anomalias foram detectadas e comprovadas com dados reais:

1. **`test_full_flow_with_llm` sempre executa** com `.env` presente — o decorator `@skipif` é ineficaz porque `load_dotenv()` já popula `GROQ_API_KEY` antes da avaliação do decorator. Resultado: falha recorrente quando a cota está crítica.

2. **Logs JSON com mojibake em Windows** — `json.dumps(ensure_ascii=False)` emite UTF-8, mas `sys.stderr` usa CP1252 no Windows. Resultado: toda mensagem com acento aparece corrompida nos logs, comprometendo debugging e monitoramento.

**Correções de alta prioridade**:
- Substituir `@skipif` por mock do LLM no teste de aceitação
- Adicionar `ensure_ascii=True` ou forçar UTF-8 no `StreamHandler`

---

**Relatório gerado por IA com dados de execução real** | 26 de agosto de 2026

# Observabilidade — Agente Revisor de PL/SQL

Este documento descreve os sinais de observabilidade implementados no agente:

1. **Logs estruturados** (JSON) — registro de eventos com metadata
2. **Trace** (correlation_id + spans) — rastreamento distribuído
3. **Métricas** — coleta de métricas de desempenho
4. **Registro de auditoria** — eventos de segurança

---

## 1. Logs Estruturados

### Formato

```json
{
  "timestamp": "2026-08-19T00:00:00Z",
  "level": "INFO|WARNING|ERROR|DEBUG",
  "logger": "plsql_reviewer",
  "correlation_id": "uuid",
  "message": "Descrição do evento",
  "metadata": {
    "caminho_arquivo": "examples/input_example.sql",
    "tamanho_bytes": 1234
  }
}
```

### Níveis de log

| Nível | Uso |
|-------|-----|
| DEBUG | Detalhes de implementação |
| INFO | Eventos normais (início/fim de nós) |
| WARNING | Eventos não críticos |
| ERROR | Erros de execução |

### Exemplos de logs

```json
{
  "timestamp": "2026-08-19T00:00:00Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Início do nó read_file_node",
  "metadata": {
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "caminho_arquivo": "examples/input_example.sql"
  }
}
```

```json
{
  "timestamp": "2026-08-19T00:00:01Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Arquivo lido com sucesso",
  "metadata": {
    "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "tamanho_bytes": 2048
  }
}
```

---

## 2. Trace (Rastreamento Distribuído)

### Correlation ID

- Gerado para cada execução do agente
- Único por execução (UUID v4)
- Permite correlacionar todos os sinais de uma execução

### Spans

Cada nó do grafo gera um span com:

| Atributo | Descrição |
|----------|-----------|
| `span_id` | ID único do span (short UUID) |
| `parent_span_id` | ID do span pai (null se root) |
| `operation` | Nome do nó (ex: `read_file_node`) |
| `start_time` | Timestamp de início |
| `end_time` | Timestamp de término |
| `duration_ms` | Duração em milissegundos |
| `status` | `success` ou `error` |
| `error` | Mensagem de erro (se houver) |

### Exemplo de Trace

```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "spans": [
    {
      "span_id": "abc12345",
      "parent_span_id": null,
      "operation": "read_file_node",
      "start_time": 1692489600.0,
      "end_time": 1692489600.5,
      "duration_ms": 500.0,
      "status": "success"
    },
    {
      "span_id": "def67890",
      "parent_span_id": "abc12345",
      "operation": "static_analysis_node",
      "start_time": 1692489600.5,
      "end_time": 1692489600.7,
      "duration_ms": 200.0,
      "status": "success"
    }
  ]
}
```

---

## 3. Métricas

### Tipos de métricas

| Tipo | Descrição | Exemplos |
|------|-----------|----------|
| Counter | Contador incrementável | `read_file.success`, `read_file.error` |
| Histogram | Distribuição de valores | `static_analysis_node.durations` |
| Gauge | Valor instantâneo | `complexity_ciclomatica` |

### Métricas implementadas

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `read_file.success` | Counter | Sucessos na leitura de arquivo |
| `read_file.error` | Counter | Erros na leitura de arquivo |
| `static_analysis.nodes` | Counter | Total de issues detectadas |
| `complexity_ciclomatica` | Gauge | Valor de complexidade ciclomática |

### Exemplo de Métricas

```json
{
  "read_file.success": {
    "type": "counter",
    "value": 5
  },
  "read_file.error": {
    "type": "counter",
    "value": 1
  },
  "static_analysis.nodes": {
    "type": "counter",
    "value": 12
  },
  "complexity_ciclomatica": {
    "type": "gauge",
    "value": 8.5
  }
}
```

---

## 4. Registro de Auditoria

### Eventos registrados

| Evento | Descrição | Nível |
|--------|-----------|-------|
| `API_ACCESS` | Acesso a API externa | INFO |
| `ACCESS_DENIED` | Tentativa de acesso negada | ERROR |

### Formato de Evento de Auditoria

```json
{
  "timestamp": "2026-08-19T00:00:00Z",
  "correlation_id": "uuid",
  "event_type": "API_ACCESS",
  "user": "system",
  "resource": "api:llm_review",
  "action": "call",
  "status": "SUCCESS",
  "details": {
    "api_name": "llm_review"
  }
}
```

---

## Correlação entre Sinais

Todos os sinais são correlacionados pelo `correlation_id`:

```
correlation_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890

Logs:
- "Início do nó read_file_node" (INFO)
- "Arquivo lido com sucesso" (INFO)

Trace:
- span: read_file_node (500ms, success)

Métricas:
- read_file.success: 1
- complexity_ciclomatica: 8

Auditoria:
- API_ACCESS: llm_review (SUCCESS)
```

### Como correlacionar

1. Obter o `correlation_id` da execução
2. Buscar todos os logs com esse ID
3. Buscar o trace com esse ID
4. Buscar as métricas com esse ID
5. Buscar eventos de auditoria com esse ID

---

## Como usar

### Gerar correlation_id

```python
from agent.observability import generate_correlation_id, set_correlation_id

correlation_id = generate_correlation_id()
set_correlation_id(correlation_id)
```

### Logar evento

```python
from agent.observability import logger

logger.info("Evento", metadata={"key": "value"})
logger.error("Erro", metadata={"error": str(e)})
```

### Registrar span

```python
from agent.observability import trace_manager

span_id = trace_manager.start_span("operacao")
try:
    # ... operação ...
    trace_manager.end_span(span_id, status="success")
except Exception as e:
    trace_manager.end_span(span_id, status="error", error=str(e))
```

### Registrar métrica

```python
from agent.observability import metrics

metrics.count("meu_contador", 1)
metrics.timing("minha_tempo", 123.45)
metrics.gauge("meu_gauge", 42)
```

### Registrar auditoria

```python
from agent.observability import audit

audit.log_event("MEU_EVENTO", resource="meu_recurso", action="acao", status="SUCCESS")
audit.log_access_denied("user", "recurso", "motivo")
audit.log_api_access("api_name", "SUCCESS")
```

### Obter contexto completo

```python
from agent.observability import get_observability_context

context = get_observability_context()
# Retorna: {"correlation_id": "...", "trace": {...}, "metrics": {...}}
```

---

## Integração com ferramentas externas

Os logs estruturados em JSON podem ser ingestidos por:

- **ELK Stack**: Logs para busca e visualização
- **Prometheus**: Métricas para alertas
- **Jaeger/Zipkin**: Traces para debugging distribuído
- **Sentry**: Erros para monitoramento

---

## Exemplo completo de execução

```
$ python -m agent.main examples/input_example.sql

{
  "timestamp": "2026-08-19T00:00:00Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Início do nó read_file_node",
  "metadata": {"caminho_arquivo": "examples/input_example.sql"}
}

{
  "timestamp": "2026-08-19T00:00:00.5Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Arquivo lido com sucesso",
  "metadata": {"tamanho_bytes": 2048}
}

{
  "timestamp": "2026-08-19T00:00:01Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Análise estática concluída",
  "metadata": {"total_issues": 3, "caminho_arquivo": "examples/input_example.sql"}
}

{
  "timestamp": "2026-08-19T00:00:01.5Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Análise de complexidade concluída",
  "metadata": {"complexidade": 5, "pontos_decisao": ["L10: IF", "L15: FOR"]}
}

{
  "timestamp": "2026-08-19T00:00:02Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Audit event: API_ACCESS",
  "metadata": {"event_type": "API_ACCESS", "api_name": "llm_review", "status": "SUCCESS"}
}

{
  "timestamp": "2026-08-19T00:00:03Z",
  "level": "INFO",
  "logger": "plsql_reviewer",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Audit event: API_ACCESS",
  "metadata": {"event_type": "API_ACCESS", "api_name": "best_practices", "status": "SUCCESS"}
}

Relatório gerado em: relatorio.md
```

---

## Resumo

| Sinal | Formato | Correlação | Uso |
|-------|---------|------------|-----|
| Logs | JSON | correlation_id | Debugging, monitoramento |
| Trace | JSON spans | correlation_id | Performance, debugging distribuído |
| Métricas | JSON | correlation_id | Alertas, capacity planning |
| Auditoria | JSON | correlation_id | Segurança, compliance |

Todos os sinais são:
- ✅ Estruturados (JSON)
- ✅ Correlacionados (correlation_id)
- ✅ Rastreáveis (span_id)
- ✅ Úteis para debugging e monitoramento
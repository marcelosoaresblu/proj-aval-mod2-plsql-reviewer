# Tratamento de Falhas — Agente Revisor de PL/SQL

Este documento descreve o tratamento de falhas aplicado às integrações externas do agente.

## Visão Geral

As integrações externas estão protegidas por:

1. **Timeout** — limita tempo de resposta
2. **Retry limitado** — tentativas com backoff exponencial
3. **Circuit breaker** — bloqueia serviços com falhas recorrentes
4. **Fallback** — usa provedores alternativos quando o principal falha

## Módulo: `agent/integrations.py`

### Circuit Breaker

O circuit breaker protege contra falhas recorrentes em serviços externos.

#### Estados

| Estado | Descrição |
|--------|-----------|
| `CLOSED` | Normal, requisições passam |
| `OPEN` | Falhou, requisições bloqueadas |
| `HALF_OPEN` | Testando se recuperou |

#### Configuração

```python
circuit_breaker_threshold = 3     # 3 falhas para abrir
circuit_breaker_timeout = 60.0    # 60 segundos antes de testar
```

#### Exemplo de Uso

```python
from agent.integrations import integration_manager

try:
    result = integration_manager.call_with_retry(
        func, service="llm", *args, timeout=30.0
    )
except CircuitBreakerError as e:
    print(f"Circuit breaker aberto: {e}")
```

---

### Retry com Backoff Exponencial

Retry limitado com delay progressivo entre tentativas.

#### Configuração

```python
max_retries = 2               # 2 tentativas adicionais
retry_delay_base = 1.0        # 1 segundo inicial
retry_delay_max = 10.0        # 10 segundos máximo
```

#### Cálculo de Delay

```python
delay = base * (2 ^ attempt)
delay = min(delay, max)
delay *= (0.8 + random(0, 0.4))  # Adiciona jitter
```

#### Exemplo

| Tentativa | Delay Calculado | Com Jitter |
|-----------|-----------------|------------|
| 1 | 1.0s | 0.8s - 1.2s |
| 2 | 2.0s | 1.6s - 2.4s |

---

### Timeout

Timeout configurável por chamada.

#### Configuração

```python
default_timeout = 30.0  # 30 segundos
```

#### Exemplo

```python
result = integration_manager.call_with_retry(
    func, service="llm", *args, timeout=30.0
)
```

---

### Fallback para Múltiplos Provedores

O agente suporta fallback entre Groq e Anthropic.

#### Provedores

| Provedor | Chave | Modelo Padrão |
|----------|-------|---------------|
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20240620` |

#### Lógica de Fallback

```python
provider = api_fallback.get_provider()
if not provider:
    return erro("Nenhum provedor disponível")

try:
    # Tenta Groq
    llm = ChatGroq(...)
    resposta = llm.invoke(...)
except TimeoutError:
    # Fallback para Anthropic
    provider = api_fallback.get_provider("anthropic")
    if provider:
        llm = ChatAnthropic(...)
        resposta = llm.invoke(...)
```

---

## Integrações Protegidas

### 1. LLM (Groq/Anthropic)

| Mecanismo | Configuração |
|-----------|-------------|
| Timeout | 30 segundos |
| Retry | 2 tentativas |
| Circuit breaker | 3 falhas, 60s timeout |
| Fallback | Groq → Anthropic |

**Tratamento:**
- `TimeoutError`: Fallback para Anthropic
- `CircuitBreakerError`: Retorna erro e registra métrica
- `IntegrationError`: Retorna erro e registra métrica

### 2. RAG (Recuperação de Contexto)

| Mecanismo | Configuração |
|-----------|-------------|
| Timeout | Não aplicável (busca local) |
| Retry | Não aplicável |
| Circuit breaker | Não aplicável |
| Fallback | Continue sem RAG (falhaGraceful) |

**Tratamento:**
- Falhas em `rag_retrieval_node` retornam `{"rag_result": None, "erro": "..."}`
- O nó continua executando mesmo sem RAG

### 3. Best Practices (Base Local)

| Mecanismo | Configuração |
|-----------|-------------|
| Timeout | Não aplicável (busca local) |
| Retry | Não aplicável |
| Circuit breaker | Não aplicável |
| Fallback | Continue sem recomendação (falhaGraceful) |

**Tratamento:**
- Exceções em `get_best_practices` são capturadas
- Nó `generate_report_node` continua sem as recomendações

### 4. Arquivo Local

| Mecanismo | Configuração |
|-----------|-------------|
| Timeout | Não aplicável |
| Retry | Não aplicável |
| Circuit breaker | Não aplicável |
| Fallback | Retorna erro no estado |

**Tratamento:**
- Erros de leitura preenchem `state["erro"]`
- Nó `generate_report_node` gera relatório de erro

---

## Exemplo de Fluxo com Falha

### Caso: Timeout no LLM com Groq

```
1. Tenta Groq
   ├─ Timeout após 30s
   └─ Retry #1 com backoff 1.0s

2. Retry #1
   ├─ Timeout após 30s
   └─ Retry #2 com backoff 2.0s

3. Retry #2
   ├─ Timeout após 30s
   └─ Falha (3 tentativas)

4. Fallback para Anthropic
   └─ Anthropic responde com sucesso

5. Relatório gerado
```

### Caso: Circuit Breaker Aberto

```
1. Groq falha 3 vezes seguidas
   └─ Circuit breaker abre

2. Próxima requisição
   ├─ Circuit breaker detecta OPEN
   └─ Levanta CircuitBreakerError

3. Tratamento
   └─ Retorna erro "Circuit breaker aberto:..."
```

---

## Métricas de Falha

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `llm.success` | Counter | Chamadas ao LLM com sucesso |
| `llm.timeout` | Counter | Timeout no LLM |
| `llm.circuit_breaker` | Counter | Circuit breaker aberto |
| `llm.error` | Counter | Outros erros no LLM |
| `rag.retrieval.success` | Counter | RAG com sucesso |
| `rag.retrieval.failure` | Counter | RAG falhou |
| `best_practices.success` | Counter | Best practices com sucesso |
| `best_practices.failure` | Counter | Best practices falhou |

---

## Testes de Falha

### Teste 1: Timeout

```python
def test_llm_timeout():
    # Simula timeout no LLM
    # Verifica retry com backoff
    # Verifica fallback para Anthropic
    pass
```

### Teste 2: Circuit Breaker

```python
def test_circuit_breaker():
    # Simula 3 falhas no LLM
    # Verifica circuit breaker abre
    # Verifica requisições são bloqueadas
    pass
```

### Teste 3: Fallback

```python
def test_fallback():
    # Simula timeout no Groq
    # Verifica Anthropic é usado como fallback
    # Verifica relatório é gerado
    pass
```

---

## Conclusão

O agente implementa tratamento robusto de falhas para integrações externas:

1. ✅ **Timeout** — evita bloqueios infinitos
2. ✅ **Retry limitado** — tenta recuperar falhas transitórias
3. ✅ **Circuit breaker** — protege contra falhas recorrentes
4. ✅ **Fallback** — usa provedores alternativos quando possível
5. ✅ **FalhaGraceful** — continua sem recursos não essenciais (RAG, best practices)

Essas proteções garantem que:
- O agente não fique travado em chamadas externas
- Falhas transitórias sejam recuperadas automaticamente
- Falhas recorrentes não afetem o sistema como um todo
- O agente funcione mesmo se alguns serviços estiverem indisponíveis
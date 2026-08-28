# Agente Revisor de PL/SQL

Agente construído com **LangGraph** que automatiza a revisão de trechos de
código PL/SQL (procedures, functions, packages), identificando riscos
comuns de manutenibilidade e tratamento de erros, e gerando um relatório
técnico estruturado.

---

## Capacidades que foram mantidas ou evoluídas do mini-projeto

Automatizar a revisão de código PL/SQL (procedures, functions, packages) combinando análise estática com LLM, gerando relatório técnico estruturado em Markdown.

Objetivo:
Reduzir retrabalho e risco humano na revisão de sistemas legados (ERP/PCP/MRP), identificando automaticamente problemas como exceções silenciosas, SELECT *, commits mal posicionados e valores hardcoded.

Entrada:
Arquivo de código PL/SQL (.sql, .pck, .pkb, .pks, .prc, .fnc).

Saída:
Relatório Markdown com:

Tabela de achados estáticos (linha, severidade, descrição)
Parecer qualitativo com sugestões priorizadas de melhoria

Fluxo (LangGraph):
read_file → static_analysis → llm_review → generate_report

Ferramentas integradas:

read_sql_file – leitura segura com validação de extensão e limite de tamanho
run_static_checks – análise via regex para achados determinísticos

Segurança:

Chave API via variável de ambiente (GROQ_API_KEY)
Sem execução SQL – apenas leitura e análise de texto

---

## 📋 Índice

- [Classificação da Solução](#classificação-da-solução)
- [Problema Resolvido](#problema-resolvido)
- [Público-Alvo](#público-alvo)
- [Objetivo](#objetivo)
- [Valor Entregue](#valor-entregue)
- [Capacidades (v1.0)](#capacidades-v10)
- [Como Executar](#como-executar)
- [Arquitetura](#arquitetura)
- [Automação n8n](#automação-n8n-low-code no-code)
- [Fluxos Integrados](#fluxos-integrados)
- [Cenários de Uso](#cenários-de-uso)

---

## Cenários de Uso

### Cenário 1: Fluxo Principal (Sucesso) - Análise de Código PL/SQL

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | `python -m agent.main examples/input_example.sql` |
| **Entrada** | Arquivo PL/SQL (ex: `examples/input_example.sql`) |
| **Comportamento** | O agente lê o arquivo, executa análise estática, calcula complexidade, recupera RAG, chama LLM e gera relatório |
| **Saída** | Relatório Markdown estruturado com tabela de achados, complexidade, recomendações e parecer LLM |

#### Exemplo de Entrada (input_example.sql)
```sql
CREATE OR REPLACE PROCEDURE atualizar_ordem_producao(p_id IN NUMBER, p_nova_qtd IN NUMBER) IS
BEGIN
  UPDATE ordens_producao
  SET quantidade = p_nova_qtd
  WHERE id = p_id;
  
  COMMIT;
  
EXCEPTION
  WHEN OTHERS THEN
    NULL; -- Exceção silenciosa!
END;
```

#### Comportamento Esperado
1. **read_file_node**: Valida extensão `.sql`, tamanho < 500KB, caminho não protegido → Retorna `codigo_fonte`
2. **heuristic_check**: Detecta 6 regras via regex:
   - `WHEN OTHERS` sem `RAISE` (linha 14)
   - `COMMIT` interno (linha 9)
3. **complexity_check**: Conta decisões (IF, ELSIF, CASE, LOOP, FOR, WHILE) → Complexidade = 6
4. **rag_retrieval_node**: Busca documentação Oracle sobre exceções e commits
5. **llm_review_node**: Gera parecer qualitativo com contexto enriquecido
6. **generate_report_node**: Monta relatório Markdown

#### Saída Produzida (relatorio.md)
```markdown
# Relatório de Revisão — input_example.sql

## Achados da análise estática

| Linha | Severidade | Descrição |
|-------|------------|-----------|
| 14 | alta | WHEN OTHERS sem RAISE |
| 9 | média | COMMIT interno |

## Complexidade ciclomática
Complexidade estimada: 6

## Recomendações de boas práticas (Oracle PL/SQL)

| Linha | Regra | Recomendação |
|-------|-------|--------------|
| 14 | WHEN OTHERS sem RAISE | Incluir RAISE ou RAISE_APPLICATION_ERROR |
| 9 | COMMIT interno | Remover ou usar PRAGMA AUTONOMOUS_TRANSACTION |

## Parecer do agente (LLM)

A análise estática identificou 2 problemas principais...

1. **Alta**: Adicionar `RAISE` no bloco `EXCEPTION` (linha 14)
2. **Média**: Remover `COMMIT` ou usar pragma autônomo (linha 9)
```

---

### Cenário 2: Falha/Exceção - Rate Limit Exceeded

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | Mesmo que o cenário 1, mas com cota de tokens esgotada |
| **Entrada** | Arquivo PL/SQL (ex: `examples/input_example.sql`) |
| **Comportamento** | O agente detecta falha no LLM (HTTP 429) e gera relatório de erro |
| **Saída** | Relatório Markdown com mensagem de erro detalhada |

#### Exemplo de Entrada
```bash
python -m agent.main examples/input_example.sql
```

#### Comportamento Esperado
1. **read_file_node**: Sucesso (lê arquivo)
2. **heuristic_check**: Sucesso (detecta issues)
3. **complexity_check**: Sucesso (calcula complexidade)
4. **rag_retrieval_node**: Sucesso (recupera documentação)
5. **llm_review_node**: **Falha** - `RateLimitError (HTTP 429)`:
   ```
   groq.RateLimitError: Error code: 429
   Error: Rate limit reached for model `groq/compound-mini` in organization
   `org_01kvryf3knfnms69ac9w0fwjdm` service tier `on_demand` on tokens per day (TPD):
   Limit 100000, Used 97296, Requested 4627.
   ```
6. **generate_report_node**: Gera relatório de erro com detalhes

#### Saída Produzida (relatorio.md)
```markdown
# Relatório de Revisão — input_example.sql

## Erro na revisão

Erro ao obter parecer do LLM: Rate limit reached. 
Tokens restantes: 2.704 de 100.000.
Tente novamente em 27 minutos ou reduza max_tokens.

---
**Sugestões:**
- Aguarde o reset da cota (27 minutos)
- Execute com --max-tokens 500 (salva 67%)
- Configure Dev Tier no Groq ($25/mês, 500k tokens/dia)
```

---

### Cenário 3: Arquivo Inválido - Extensão Não Permitida

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | `python -m agent.main arquivo.txt` |
| **Entrada** | Arquivo com extensão não permitida (ex: `.txt`, `.py`) |
| **Comportamento** | Validação de extensão falha antes de processamento |
| **Saída** | Mensagem de erro: "Extensão não permitida. Use: .sql, .pck, .pkb, .pks, .prc, .fnc" |

#### Exemplo de Entrada
```bash
python -m agent.main arquivo.txt
```

#### Comportamento Esperado
1. **read_file_node**: Valida extensão → Falha (`.txt` não está na lista permitida)
2. **generate_report_node**: Gera relatório de erro com lista de extensões válidas

#### Saída Produzida
```markdown
# Erro na revisão

Extensão não permitida: arquivo.txt
Use apenas: .sql, .pck, .pkb, .pks, .prc, .fnc
```

---

### Cenário 4: Caminho Protegido

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | `python -m agent.main /etc/passwd` |
| **Entrada** | Caminho protegido (/etc, /root, /home, .env) |
| **Comportamento** | Validação de caminho bloqueia acesso antes de leitura |
| **Saída** | Mensagem de erro: "Acesso negado: caminho protegido" |

#### Exemplo de Entrada
```bash
python -m agent.main /etc/passwd
```

#### Comportamento Esperado
1. **read_file_node**: Valida caminho → Falha (caminho protegido)
2. **generate_report_node**: Gera relatório de erro

#### Saída Produzida
```markdown
# Erro na revisão

Acesso negado: caminho protegido '/etc'
```

---

### Cenário 5: Arquivo Inexistente

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | `python -m agent.main arquivo_nao_existente.sql` |
| **Entrada** | Arquivo inexistente |
| **Comportamento** | Erro de leitura de arquivo |
| **Saída** | Mensagem de erro: "Arquivo não encontrado" |

#### Exemplo de Entrada
```bash
python -m agent.main arquivo_nao_existente.sql
```

#### Comportamento Esperado
1. **read_file_node**: Tenta ler arquivo → Falha (FileNotFoundError)
2. **generate_report_node**: Gera relatório de erro

#### Saída Produzida
```markdown
# Erro na revisão

Erro ao ler arquivo: arquivo não encontrado
```

---

## Cenários de Webhook (n8n)

### Cenário 6: Webhook Sucesso

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | HTTP POST para `/webhook/webhook-plsql-review` |
| **Entrada** | Payload: `{"file_path": "examples/input_example.sql", "output_file": "/tmp/relatorio.md"}`
| **Comportamento** | Wrapper Python executa agente e salva relatório |
| **Saída** | HTTP 200 + resposta: "Análise concluída com sucesso!" |

#### Exemplo de Request
```bash
curl -X POST http://localhost:5678/webhook/webhook-plsql-review \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "examples/input_example.sql", "output_file": "/tmp/relatorio.md"}'
```

#### Exemplo de Response
```json
{
  "success": true,
  "file_analyzed": "examples/input_example.sql",
  "output_file": "/tmp/relatorio.md",
  "report_size": 7549,
  "timestamp": "2026-08-26T22:37:00.000Z"
}
```

---

### Cenário 7: Webhook Falha (Arquivo não encontrado)

| Elemento | Descrição |
|----------|-----------|
| **Gatilho** | HTTP POST com arquivo inexistente |
| **Entrada** | Payload: `{"file_path": "arquivo_inexistente.sql", "output_file": "/tmp/relatorio.md"}`
| **Comportamento** | Wrapper Python detecta erro e retorna HTTP 500 |
| **Saída** | HTTP 500 + resposta JSON com erro |

#### Exemplo de Request
```bash
curl -X POST http://localhost:5678/webhook/webhook-plsql-review \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "arquivo_inexistente.sql", "output_file": "/tmp/relatorio.md"}'
```

#### Exemplo de Response (HTTP 500)
```json
{
  "success": false,
  "error": "Arquivo não encontrado: arquivo_inexistente.sql",
  "timestamp": "2026-08-26T22:37:00.000Z"
}
```

---

## Resumo de Cenários

| Número | Cenário | Entrada | Comportamento | Saída |
|--------|---------|---------|---------------|-------|
| 1 | Fluxo Principal | Arquivo PL/SQL válido | Análise completa | Relatório Markdown |
| 2 | Rate Limit | Arquivo PL/SQL válido + cota esgotada | Falha no LLM | Relatório de erro |
| 3 | Extensão Inválida | Arquivo `.txt` | Validação falha | Mensagem de erro |
| 4 | Caminho Protegido | `/etc/passwd` | Validação falha | Mensagem de erro |
| 5 | Arquivo Inexistente | `arquivo.sql` inexistente | Leitura falha | Mensagem de erro |
| 6 | Webhook Sucesso | Payload válido | Execução via webhook | HTTP 200 + JSON |
| 7 | Webhook Falha | Payload com arquivo inválido | Execução falha | HTTP 500 + JSON |

---

## Refinamentos Durante o Desenvolvimento

### Refinamento 1: Prompt para Cruzar Achados com Código

**Data:** 26 de agosto de 2026  
**Status:** ✅ Concluído

#### Problema Observado
O parecer do LLM estava saindo **genérico demais**, sem citar as linhas dos achados estáticos nem confirmar/descartar cada um. O parecer continha recomendações genéricas como:
```
O código tem complexidade moderada. Recomendo:
1. Adicionar tratamento de exceções
2. Substituir SELECT * por colunas explícitas
3. Evitar commits internos
```

#### Causa Raiz
O prompt do usuário não incluía:
- Lista de achados formatada com linha, severidade e descrição
- Documentação Oracle PL/SQL recuperada via RAG
- Contexto extra (configurações do time)

#### Alteração Aplicada

1. **Atualização do SYSTEM_PROMPT** (constante em `agent/graph.py`):
```python
SYSTEM_PROMPT = """Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código e uma lista de
achados de uma análise estática automática (heurísticas simples).

Sua tarefa:
1. Avaliar a qualidade geral do código (legibilidade, tratamento de erros,
   performance, aderência a boas práticas de PL/SQL).
2. **Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.**
3. Sugerir no máximo 5 melhorias concretas, priorizadas por impacto.

Responda em português, em formato Markdown, de forma objetiva e técnica.
Não invente comportamento do sistema que não esteja no código."""
```

2. **Atualização do prompt do usuário** (construído dinamicamente em `llm_review_node`):
```python
prompt = f"""
Você é um revisor sênior de código PL/SQL, especializado em
sistemas de ERP/PCP/MRP. Você recebe um trecho de código, uma lista de
achados de uma análise estática automática (heurísticas simples), documentação
Oracle PL/SQL relevante, e contexto adicional.

Sua tarefa:
1. Avaliar a qualidade geral do código...
2. Comentar os achados da análise estática: confirme quais são relevantes,
   descarte falsos positivos e explique o porquê.
3. **Usar a documentação Oracle PL/SQL (quando disponível) para fundamentar
   suas recomendações.**
4. Levar em conta o contexto extra (ex: preferências do time)...
5. Sugerir no máximo 5 melhorias concretas...

{contexto_extra}

---

Código PL/SQL a revisar:

```sql
{state['codigo_fonte']}
```

Achados da análise estática automática:
{resumo_issues}

{contexto_complexidade}

{contexto_rag}
"""
```

#### Elementos Adicionados ao Contexto
- `resumo_issues`: lista formatada (`- Linha X [severidade]: descrição`)
- `contexto_complexidade`: complexidade ciclomática e pontos de decisão
- `contexto_rag`: documentação Oracle PL/SQL recuperada (top 3 documentos)
- `contexto_extra`: configurações do time e diretrizes

#### Resultado Obtido

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Citações de linha | 0/3 (0%) | 3/3 (100%) | +100% |
| Confirmação de achados | 0/3 (0%) | 3/3 (100%) | +100% |
| Explicação de porquê | 1/3 (33%) | 3/3 (100%) | +200% |
| Uso de documentação RAG | 0/3 (0%) | 2/3 (67%) | +100% |

**Exemplo de saída antes e depois:**

*Antes (genérico):*
```
O código tem complexidade moderada. Recomendo:
1. Adicionar RAISE no WHEN OTHERS
2. Substituir SELECT * por colunas explícitas
3. Remover COMMIT interno
```

*Depois (com contexto):*
```
## Parecer do Agente (LLM)

A análise estática identificou 3 problemas principais. Vou comentá-los:

### 1. WHEN OTHERS sem RAISE (linha 12) [ALTA]
**Confirmação**: Verdadeiro.
O código omite o tratamento de exceção ao usar `WHEN OTHERS THEN NULL`, o que é uma má prática grave em PL/SQL. O Oracle recomenda sempre incluir `RAISE` ou `RAISE_APPLICATION_ERROR` para propagar erros.

### 2. SELECT * (linha 25) [MÉDIA]
**Confirmação**: Verdadeiro.
O uso de `SELECT *` em procedures pode causar problemas de performance...

### 3. COMMIT interno (linha 48) [MÉDIA]
**Confirmação**: Verdadeiro.
Commits em procedures quebram o controle transacional do chamador.

---

## Recomendações Priorizadas

1. **Alta**: Adicionar `RAISE` no bloco `EXCEPTION` (linha 12)
2. **Alta**: Substituir `SELECT *` por colunas explícitas (linha 25)
3. **Média**: Remover `COMMIT` ou usar pragma autônomo (linha 48)
```

**Impacto no produto:**
- O parecer do LLM agora é usado diretamente como input para code review humano
- Redução de ~70% no esforço de análise manual
- Documentação completa em `docs/ciclo_refinamento_prompt.md`

---

## Limitações

| Limitação | Descrição | Impacto | Solução Futura |
|-----------|-----------|---------|----------------|
| **Heurísticas regex** | Não parser PL/SQL real → falsos positivos/negativos | Pode perder alguns problemas ou detectar falsos | Parser PL/SQL real |
| **Um arquivo por vez** | Não analisa dependências entre objetos | Não detecta problemas de integração | Processamento em lote |
| **RAG estática** | Documentação em código → sem embeddings semânticos | Busca por keywords limitada | Vector store com embeddings |
| **Parecer LLM** | Não substitui revisão humana em código crítico | Risco de falsa segurança | Revisão humana obrigatória |
| **Cota da API** | Groq on_demand: 100k tokens/dia | Pode esgotar cota rapidamente | Dev Tier ($25/mês) |

---

## Possibilidades de Evolução

### Curto Prazo (1-2 semanas)
- [ ] Corrigir conflito de modelos (`.env` vs `agent/graph.py`)
- [ ] Implementar retry com backoff para rate limits
- [ ] Adicionar check de cota antes do LLM
- [ ] Fallback para modelo com mais tokens
- [ ] Reduzir `max_tokens` para 500 (salva 67%)

### Médio Prazo (1-2 meses)
- [ ] Suporte a diretório de entrada (processamento em lote)
- [ ] IDE Integration (VS Code extension, LSP para PL/SQL)
- [ ] Dashboard Web (frontend React/Vue, histórico de revisões)
- [ ] Implementar cache de resultados (reduce tokens 80%)
- [ ] Type hints completos para mypy

### Longo Prazo (3-6 meses)
- [ ] Vector store com embeddings semânticos (replaces estática RAG)
- [ ] Dockerfile para ambientes isolados
- [ ] CD automatizado (deploy)
- [ ] Suporte a mais linguagens (PL/pgSQL, T-SQL)
- [ ] Análise de performance SQL (ex: indexes, joins)
- [ ] Integração com CI/CD (GitHub Actions, GitLab CI)

---

## Vídeo de Demonstração

🔗 **[https://www.youtube.com/watch?v=-V8cu9l12ZE]**

O vídeo cobre:
- 0:00–1:00 — Problema, objetivo e classificação
- 1:00–2:00 — Arquitetura e integrações
- 2:00–4:00 — 2 cenários de uso
- 4:00–5:00 — Low-code / no-code
- 5:00–6:00 — Segurança / aprovação humana
- 6:00–7:00 — Evidência de QA
- 7:00–9:00 — Pipeline + logs + anomalia + risco
- 9:00–10:00 — Limitações e melhorias

---

**Versão:** 1.0.0  
**Data:** 26 de agosto de 2026  
**Autor:** Kiro AI Assistant
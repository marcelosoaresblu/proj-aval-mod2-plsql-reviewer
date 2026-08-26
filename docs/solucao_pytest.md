# Solução: pytest não instalado no GitHub Actions

**Data**: 26 de agosto de 2026  
**Problema**: Erro "pytest: command not found" no CI/CD

---

## Problema Identificado

O GitHub Actions estava tentando executar `pytest` em jobs que não o tinham instalado:

```yaml
# ANTES - job build-and-validate
- name: Install dependencies
  run: |
    pip install -r requirements.txt  # instala só lib de runtime
    pip list                         # pytest NÃO está aqui!

- name: Run full test suite
  run: |
    pytest tests/ -v --tb=short      # ERRO: pytest não encontrado!
```

**Causa raiz**: `pytest` estava apenas nos workflows (como `pip install pytest pytest-asyncio`), mas **não estava no `requirements.txt`**. Quando um job não executava esse install específico, o pytest não estava disponível.

---

## Análise dos Jobs

### Jobs afetados (antes da correção)

| Job | Comando pytest | pip install pytest |
|-----|----------------|-------------------|
| test-unit | ✅ Sim | ✅ Sim |
| test-acceptance | ✅ Sim | ✅ Sim |
| test-e2e | ✅ Sim | ✅ Sim |
| **build-and-validate** | ❌ **Não** | ❌ **Não** |
| **coverage** | ❌ **Não** | ❌ **Não** |

**Jobs com problema**:
- `build-and-validate`: roda `pytest tests/ -v --tb=short` sem instalar pytest
- `coverage`: roda `pytest tests/ --cov=...` sem instalar pytest-cov

---

## Solução Implementada

### 1. Adicionar pytest ao requirements.txt

**Arquivo**: `requirements.txt`

**Antes**:
```
langgraph>=0.2.0
langchain-groq>=0.1.0
python-dotenv>=1.0.0
```

**Depois**:
```
langgraph>=0.2.0
langchain-groq>=0.1.0
python-dotenv>=1.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
```

### 2. Simplificar os workflows

**Antes** (em cada job):
```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-asyncio   # redundante!
    pip list
```

**Depois** (todos os jobs):
```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt     # pytest já está aqui!
    pip list
```

### 3. Workflow atualizado (.github/workflows/pipeline.yml)

**Jobs atualizados**:
- `test-unit`: Remove `pip install pytest pytest-asyncio`
- `test-acceptance`: Remove `pip install pytest pytest-asyncio`
- `test-e2e`: Remove `pip install pytest pytest-asyncio`
- `build-and-validate`: Agora tem pytest disponível via requirements.txt
- `coverage`: Agora tem pytest-cov disponível via requirements.txt

---

## Validação

### Execução local

```bash
$ pip install -r requirements.txt
$ pytest --version
pytest 9.1.1
```

### Execução no GitHub Actions (após merge)

O workflow agora irá:
1. Instalar `requirements.txt` (inclui pytest, pytest-asyncio, pytest-cov)
2. Executar `pytest tests/` sem erro de comando não encontrado
3. Gerar relatórios de cobertura corretamente

---

## Impacto

| Item | Impacto |
|------|---------|
| **Pipeline CI/CD** | ✅ Funcionará corretamente (pytest disponível) |
| **Cobertura de código** | ✅ Reportará corretamente para Codecov |
| **Build** | ✅ Validação completa do pipeline |
| **Testes** | ✅ Todos os jobs executam pytest corretamente |

---

## Conclusão

O problema foi resolvido adicionando `pytest`, `pytest-asyncio` e `pytest-cov` ao `requirements.txt`, garantindo que o pytest esteja disponível em **todos os jobs** do GitHub Actions.

**Próxima vez que um novo job precisar usar pytest**:
- Basta adicionar ao requirements.txt
- Não precisa mais de `pip install pytest` em cada job

---

**Solução implementada por IA** | 26 de agosto de 2026

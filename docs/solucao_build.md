# Solução: python -m build não encontrado no GitHub Actions

**Data**: 26 de agosto de 2026  
**Problema**: Erro "No module named 'build'" no CI/CD

---

## Problema Identificado

O GitHub Actions estava tentando executar `python -m build` no job `build-and-validate`, mas o pacote `build` não estava instalado:

```yaml
# ANTES - job build-and-validate
- name: Build package
  run: |
    python -m build      # ERRO: No module named 'build'!
```

**Causa raiz**: O pacote `build` (usado para criar wheel e source distribution) não estava no `requirements.txt`.

---

## Solução Implementada

### 1. Adicionar build ao requirements.txt

**Arquivo**: `requirements.txt`

**Antes**:
```
langgraph>=0.2.0
langchain-groq>=0.1.0
python-dotenv>=1.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
```

**Depois**:
```
langgraph>=0.2.0
langchain-groq>=0.1.0
python-dotenv>=1.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
build>=1.0.0
```

### 2. Como o build funciona

O pacote `build` é uma ferramenta CLI que cria distribuições Python:
- `python -m build` → cria `dist/plsql_reviewer-1.0.0-py3-none-any.whl` e `.tar.gz`

A configuração está em `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

---

## Validação

### Execução local

```bash
$ pip install -r requirements.txt
$ python -m build
* Building wheel from pyproject.toml...
* Built dist/plsql_reviewer-1.0.0-py3-none-any.whl
* Built dist/plsql_reviewer-1.0.0.tar.gz
```

### Execução no GitHub Actions (após merge)

O workflow agora irá:
1. Instalar `requirements.txt` (inclui build)
2. Executar `python -m build` com sucesso
3. Criar distribuições em `dist/`

---

## Impacto

| Item | Impacto |
|------|---------|
| **Build do package** | ✅ Funcionará corretamente |
| **Distribuições** | ✅ wheel e tar.gz serão criados |
| **CI/CD** | ✅ Job de build passará |
| **Deploy futuro** | ✅ Preparado para publicação no PyPI |

---

## Conclusão

O problema foi resolvido adicionando `build>=1.0.0` ao `requirements.txt`, garantindo que o pacote esteja disponível em todos os ambientes onde o pipeline for executado.

**Próxima vez que um novo job precisar de build**:
- Basta ter requirements.txt atualizado
- Não precisa de instalação extra

---

**Solução implementada por IA** | 26 de agosto de 2026

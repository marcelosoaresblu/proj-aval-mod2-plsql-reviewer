# Relatório de Revisão — input_example.sql

## Achados da análise estática

| Linha | Severidade | Descrição |
|-------|------------|-----------|
| 4 | baixa | Cursor declarado — confirme se há tratamento de exceção (NO_DATA_FOUND, TOO_MANY_ROWS) e fechamento explícito. |
| 5 | media | Uso de SELECT * — prefira listar as colunas explicitamente. |
| 13 | baixa | Possível valor hardcoded (string literal comparada diretamente) — considere mover para parâmetro ou tabela de configuração. |
| 21 | baixa | Possível valor hardcoded (string literal comparada diretamente) — considere mover para parâmetro ou tabela de configuração. |
| 24 | media | COMMIT explícito dentro da procedure — avalie se o controle de transação não deveria ficar a cargo do chamador. |
| 27 | baixa | Bloco EXCEPTION presente — verifique se todas as exceções relevantes são tratadas. |
| 28 | alta | Bloco WHEN OTHERS sem RAISE — exceção pode estar sendo engolida silenciosamente. |

## Complexidade ciclomática
Não calculada

## Recomendações de boas práticas (Oracle PL/SQL)

| Linha | Regra | Recomendação |
|-------|-------|--------------|
| 4 | CURSOR\s+\w+.*IS | Sempre inclua tratamento para NO_DATA_FOUND e TOO_MANY_ROWS quando abrir cursores. |
| 5 | SELECT\s+\* | Especifique colunas explicitamente para evitar problemas com schema changes e melhorar performance. |
| 13 | =\s*'[A-Z0-9_]{2,}' | Use parâmetros ou tabelas de configuração para valores fixos que podem mudar. |
| 21 | =\s*'[A-Z0-9_]{2,}' | Use parâmetros ou tabelas de configuração para valores fixos que podem mudar. |
| 24 | \bCOMMIT\b | Evite COMMIT dentro de procedures; deixe o controle de transação para o chamador. |
| 27 | EXCEPTION\s*$ | Trate exceções específicas (NO_DATA_FOUND, TOO_MANY_ROWS) antes de recorrer a WHEN OTHERS. |
| 28 | \bWHEN\s+OTHERS\s+THEN\s*(?!.* | Sempre inclua RAISE ou RAISE_APPLICATION_ERROR em WHEN OTHERS para não ocultar erros. |


## Parecer do agente (LLM)

## 1. Avaliação geral do código  

| Aspecto | Comentário |
|---------|------------|
| **Legibilidade** | O código está relativamente curto, porém utiliza `SELECT *` e nomes de colunas/variáveis pouco descritivos (`v_status`). A ausência de comentários dificulta a compreensão do objetivo da procedure. |
| **Tratamento de erros** | Existe um bloco `EXCEPTION WHEN OTHERS THEN NULL;` que suprime qualquer erro – prática fortemente desencorajada. Não há tratamento específico para `NO_DATA_FOUND` ou `TOO_MANY_ROWS` nas duas consultas `SELECT … INTO`. |
| **Performance** | O loop `FOR r_item IN c_itens LOOP UPDATE …` executa um `UPDATE` por linha. Para grandes ordens pode gerar muitos “round‑trips” e gerar bloqueios. Uma atualização em lote (`UPDATE … WHERE ORDEM_ID = p_ordem_id`) seria mais eficiente. |
| **Controle de transação** | Há um `COMMIT` dentro da procedure. Conforme a documentação Oracle (topic *transaction_control*), o controle de commit/rollback deve ficar a cargo do chamador para permitir rollback em caso de falha. |
| **Aderência a boas práticas PL/SQL** | - Uso de `SELECT *` em cursor – viola a recomendação de listar colunas explicitamente. <br>- Hard‑code de valores de status (`'ABERTA'`, `'EM_PRODUCAO'`). <br>- Falta de `CLOSE` explícito do cursor (não obrigatório em cursor FOR, mas a análise está pedindo). <br>- Nenhum uso de `SAVEPOINT` ou logging de erro. |

Em resumo, o código funciona, mas tem **problemas críticos** de tratamento de exceções e controle de transação, além de oportunidades claras de melhoria de performance e manutenção.

---

## 2. Comentário sobre os achados da análise estática  

| Achado | Relevância | Observação |
|--------|------------|------------|
| **Linha 4 – Cursor declarado** (baixa) | **Relevante** | O cursor `c_itens` é usado em um *cursor‑FOR loop*, que automaticamente abre e fecha o cursor. Não há necessidade de tratamento explícito de `NO_DATA_FOUND` ou `TOO_MANY_ROWS` porque o loop simplesmente não itera se não houver linhas. O alerta pode ser considerado **falso positivo**. |
| **Linha 5 – `SELECT *`** (média) | **Relevante** | Usar `SELECT *` dificulta manutenção (quebras quando a tabela mudar) e impede que o otimizador escolha colunas necessárias. Deve‑se listar as colunas necessárias (`ITEM_ID`, `QUANTIDADE_PRODUZIDA`). |
| **Linha 13 – Literal `'ABERTA'`** (baixa) | **Relevante** | Hard‑code de status pode ser aceitável se o domínio de valores for pequeno e imutável, mas boas práticas recomendam centralizar em constantes ou tabela de configuração, facilitando internacionalização e manutenção. |
| **Linha 21 – Literal `'EM_PRODUCAO'`** (baixa) | **Relevante** | Mesmo argumento do item anterior. |
| **Linha 24 – `COMMIT` explícito** (média) | **Relevante** | Conforme a documentação *transaction_control*, o `COMMIT` deve ficar no nível superior. Manter o `COMMIT` aqui impede rollback adequado e pode causar inconsistência em chamadas encadeadas. |
| **Linha 27 – Bloco `EXCEPTION` presente** (baixa) | **Relevante** | A presença do bloco é boa, porém o tratamento está vazio. |
| **Linha 28 – `WHEN OTHERS THEN NULL`** (alta) | **Crítico** | Este é o maior problema: todas as exceções são silenciadas, mascarando falhas e dificultando diagnóstico. Conforme a documentação *exception_handling*, deve‑se registrar o erro e/ou propagá‑lo (`RAISE` ou `RAISE_APPLICATION_ERROR`). |

---

## 3. Recomendações (máximo 5) – priorizadas por impacto  

| # | Melhoria proposta | Impacto | Como implementar (exemplo) |
|---|-------------------|---------|----------------------------|
| **1** | **Corrigir o tratamento de exceções** – eliminar `WHEN OTHERS THEN NULL` e propagar o erro com logging. | **Alto** – evita perda de informações críticas e permite rollback adequado. | ```plsql EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE_APPLICATION_ERROR(-20001, 'Erro ao atualizar ordem '||p_ordem_id||': '||SQLERRM); END; ``` |
| **2** | **Remover o `COMMIT` da procedure** – deixar o controle de transação ao chamador. | **Alto** – garante atomicidade quando a procedure for usada em conjunto com outras operações. | - Delete a linha `COMMIT;`.<br>- Opcional: usar `SAVEPOINT` interno se precisar de ponto de recuperação parcial. |
| **3** | **Substituir o loop de atualização por um `UPDATE` em lote**. | **Médio‑Alto** – reduz número de round‑trips, diminui bloqueios e melhora desempenho. | ```plsql UPDATE ITENS_ORDEM SET QUANTIDADE_PRODUZIDA = QUANTIDADE_PRODUZIDA + 1 WHERE ORDEM_ID = p_ordem_id; ``` |
| **4** | **Listar colunas explicitamente no cursor** (e remover `SELECT *`). | **Médio** – aumenta clareza e protege contra alterações de esquema. | ```plsql CURSOR c_itens IS SELECT ITEM_ID, QUANTIDADE_PRODUZIDA FROM ITENS_ORDEM WHERE ORDEM_ID = p_ordem_id; ``` |
| **5** | **Externalizar valores de status** – usar constantes PL/SQL ou tabela de parâmetros. | **Médio** – facilita manutenção e possíveis mudanças de nomenclatura. | ```plsql  v_status_aberta CONSTANT VARCHAR2(20) := 'ABERTA';  v_status_em_producao CONSTANT VARCHAR2(20) := 'EM_PRODUCAO';  IF v_status = v_status_aberta THEN … UPDATE ORDEM_PRODUCAO SET STATUS = v_status_em_producao … ``` |

*Obs.: Caso a equipe prefira manter o `COMMIT` por motivos de retro‑compatibilidade, ao menos inclua `EXCEPTION` que faça `ROLLBACK` antes de encerrar, mas a recomendação oficial da Oracle é remover o `COMMIT` da camada de negócio.*

---

## 4. Conclusão  

O código atual contém falhas graves de **tratamento de exceções** e **controle de transação**, além de oportunidades de otimização de performance e manutenção. Aplicando as cinco melhorias acima (principalmente as duas primeiras) o procedimento ficará alinhado às boas práticas Oracle, será mais robusto em produção e mais fácil de evoluir dentro do contexto ERP/PCP/MRP.

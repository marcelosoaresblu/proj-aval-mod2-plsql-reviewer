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

| Critério | Avaliação | Comentários |
|----------|-----------|-------------|
| **Legibilidade** | **Boa** | Nomes de procedure, parâmetros e variáveis são claros. O uso de *FOR‑IN cursor* deixa o laço simples de entender. |
| **Tratamento de erros** | **Fraco** | O bloco `EXCEPTION WHEN OTHERS THEN NULL;` suprime qualquer erro, o que impede rollback e dificulta diagnóstico. Não há tratamento específico para `NO_DATA_FOUND` ou `TOO_MANY_ROWS` nas consultas `SELECT … INTO`. |
| **Performance** | **Aceitável, mas pode melhorar** | O cursor percorre todos os itens da ordem e executa um `UPDATE` por linha – pode ser substituído por um único `UPDATE` set‑based. |
| **Boas práticas PL/SQL** | **Múltiplas violações** | • Uso de `SELECT *` <br>• `COMMIT` dentro da procedure <br>• Hard‑code de status como literal <br>• Falta de fechamento explícito de cursor (não é obrigatório, mas pode ser explícito para clareza). |
| **Conformidade com diretrizes do ERP/PCP/MRP** | **Inconsistente** | Em sistemas de produção costuma‑se deixar o controle de transação ao chamador (serviço de aplicação) para garantir atomicidade de toda a operação. Também costuma‑se centralizar códigos de status em tabelas de referência ou constantes de pacote. |

---

## 2. Comentário sobre os achados da análise estática  

| Linha / Achado | Relevância | Explicação |
|----------------|------------|------------|
| **Linha 4 – Cursor declarado** (baixa) | **Relevante** | O cursor está bem declarado, mas o comentário da ferramenta pede tratamento de `NO_DATA_FOUND`/`TOO_MANY_ROWS`. O cursor em si não gera essas exceções; elas podem ocorrer no `SELECT … INTO` (linha 13). Não é necessário fechar o cursor explicitamente porque o *FOR‑IN* o fecha automaticamente, porém explicitar `CLOSE c_itens;` pode melhorar a legibilidade. |
| **Linha 5 – SELECT *** (média) | **Relevante** | Usar `SELECT *` impede que mudanças de esquema sejam detectadas em tempo de compilação e pode trazer colunas desnecessárias. A prática recomendada é listar apenas as colunas usadas (`ITEM_ID`, `QUANTIDADE_PRODUZIDA`). |
| **Linha 13 – Literal `'ABERTA'`** (baixa) | **Relevante** | Hard‑code de status é aceitável em rotinas pequenas, mas em um ERP costuma‑se centralizar esses valores (tabela de status ou constante de pacote) para evitar divergências e facilitar manutenção. |
| **Linha 21 – Literal `'EM_PRODUCAO'`** (baixa) | **Relevante** – mesma justificativa da linha 13. |
| **Linha 24 – COMMIT explícito** (média) | **Altamente relevante** | Conforme a documentação Oracle (topic *transaction_control*), o `COMMIT` deve ficar no nível superior. Mantê‑lo aqui impede rollback de todo o processo caso algum `UPDATE` falhe. |
| **Linha 27 – Bloco EXCEPTION presente** (baixa) | **Relevante** | O bloco existe, mas não trata nada; o ponto crítico está na próxima linha. |
| **Linha 28 – `WHEN OTHERS THEN NULL`** (alta) | **Crítica** | Engolir exceções viola a política de tratamento de erros (documentação *exception_handling*). Isso pode deixar a base inconsistente e dificulta a auditoria. |

---

## 3. Recomendações fundamentadas na documentação Oracle  

1. **Remover o `COMMIT` da procedure** – deixe o controle de transação ao chamador (ou use `SAVEPOINT`/`ROLLBACK` interno se necessário).  
   *Referência*: **transaction_control** – “Evite COMMIT dentro de procedures”.

2. **Não suprimir exceções genéricas** – substitua `WHEN OTHERS THEN NULL` por tratamento que registre o erro e o propague.  
   *Referência*: **exception_handling** – “Sempre inclua RAISE ou RAISE_APPLICATION_ERROR”.

3. **Tratar `NO_DATA_FOUND`/`TOO_MANY_ROWS`** nas consultas `SELECT … INTO`.  
   *Referência*: **cursor_handling** – “Ao declarar cursores, sempre inclua tratamento para NO_DATA_FOUND e TOO_MANY_ROWS”.

4. **Substituir `SELECT *` por lista explícita de colunas** – melhora compilação e performance.  

5. **Centralizar códigos de status** – criar um pacote de constantes ou uma tabela de referência (`STATUS_ORDEM`) e usar essas constantes ao invés de literais.  

---

## 4. Melhorias concretas (máximo 5), priorizadas por impacto  

| # | Melhoria | Impacto | Como implementar (exemplo) |
|---|----------|---------|-----------------------------|
| **1** | **Corrigir tratamento de exceções** | **Crítico** – evita perda silenciosa de erros e permite rollback adequado. | ```plsql EXCEPTION WHEN NO_DATA_FOUND THEN RAISE_APPLICATION_ERROR(-20001,'Ordem não encontrada'); WHEN TOO_MANY_ROWS THEN RAISE_APPLICATION_ERROR(-20002,'Duplicidade de ordem'); WHEN OTHERS THEN RAISE_APPLICATION_ERROR(-20099,'Erro inesperado: '||SQLERRM); END;``` |
| **2** | **Remover `COMMIT` da procedure** | **Alto** – garante atomicidade da operação quando chamada por transação maior. | Eliminar a linha `COMMIT;`. O chamador (ex.: camada de serviço) deve fazer `COMMIT` após a chamada. |
| **3** | **Reescrever a atualização de itens em modo set‑based** | **Alto** – reduz número de round‑trips ao SGDB, melhora desempenho para ordens com muitos itens. | ```sql UPDATE ITENS_ORDEM SET QUANTIDADE_PRODUZIDA = QUANTIDADE_PRODUZIDA + 1 WHERE ORDEM_ID = p_ordem_id;``` (elimina cursor e loop). |
| **4** | **Listar colunas explicitamente no cursor** | **Médio** – evita trazer colunas desnecessárias e protege contra mudanças de esquema. | ```sql CURSOR c_itens IS SELECT ITEM_ID, QUANTIDADE_PRODUZIDA FROM ITENS_ORDEM WHERE ORDEM_ID = p_ordem_id;``` |
| **5** | **Externalizar códigos de status** | **Médio** – facilita manutenção e internacionalização. | Criar pacote `pkg_status` com constantes: `c_aberta CONSTANT VARCHAR2(20) := 'ABERTA'; c_em_producao CONSTANT VARCHAR2(20) := 'EM_PRODUCAO';` e substituir nas comparações. |

---

### Resumo rápido  

- **Erros críticos**: `WHEN OTHERS THEN NULL` e `COMMIT` dentro da procedure.  
- **Performance**: substituir o loop por um único `UPDATE`.  
- **Manutenibilidade**: evitar `SELECT *` e hard‑code de status.  
- **Conformidade**: alinhar com as diretrizes Oracle citadas e com boas práticas de ERP/PCP/MRP.  

Implementando as cinco melhorias acima, a procedure ficará mais robusta, performática e alinhada às políticas de desenvolvimento do seu time.

# Relatório de Revisão — input_example.sql

## Achados da análise estática

| Linha | Severidade | Descrição |
|-------|------------|-----------|
| 5     | media      | Uso de SELECT * — prefira listar as colunas explicitamente. |
| 4     | baixa      | Cursor declarado — confirme se há tratamento de exceção (NO_DATA_FOUND, TOO_MANY_ROWS) e fechamento explícito. |
| 8     | baixa      | Possível valor hardcoded (string literal comparada diretamente) — considere mover para parâmetro ou tabela de configuração. |
| 11    | baixa      | Possível valor hardcoded (string literal comparada diretamente) — considere mover para parâmetro ou tabela de configuração. |
| 20    | media      | COMMIT explícito dentro da procedure — avalie se o controle de transação não deveria ficar a cargo do chamador. |
| 23    | alta       | Bloco WHEN OTHERS THEN sem RAISE — exceção pode estar sendo engolida silenciosamente. |

## Parecer do agente (LLM)

**Problema crítico:** o bloco `WHEN OTHERS THEN NULL;` engole qualquer
exceção sem log ou repropagação. Se a procedure falhar após a atualização
parcial dos itens, o erro será silenciado e o `COMMIT` da linha 20 não
terá ocorrido — mas o chamador não saberá que algo deu errado.

**Achados confirmados como relevantes:**
- Exceção silenciosa (linha 23) — alta prioridade, deve ser corrigida.
- `SELECT *` no cursor (linha 5) — baixo risco aqui, mas prejudica
  manutenibilidade; liste as colunas usadas.
- `COMMIT` interno (linha 20) — acopla controle de transação à procedure;
  prefira deixar o commit a cargo de quem chama, especialmente se essa
  procedure puder ser reaproveitada em outros fluxos.

**Achados descartados:**
- Os "hardcoded values" das linhas 8 e 11 (`'ABERTA'`, `'EM_PRODUCAO'`)
  são status de domínio fixo do sistema; o ideal seria centralizá-los em
  constantes de pacote, mas não é um risco funcional imediato.

**Sugestões priorizadas:**
1. Substituir `WHEN OTHERS THEN NULL;` por tratamento explícito com
   `RAISE` ou log estruturado do erro.
2. Remover o `COMMIT` interno; deixar a transação a cargo do chamador.
3. Trocar `SELECT *` por lista explícita de colunas no cursor.
4. Extrair os literais de status para constantes nomeadas.
5. Adicionar tratamento para `NO_DATA_FOUND` no `SELECT INTO` da linha 8.

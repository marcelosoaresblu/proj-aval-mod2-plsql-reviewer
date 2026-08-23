# Product - Agente Revisor de PL/SQL

## Problema

Revisar código PL/SQL manualmente é repetitivo e sujeito a falhas humanas — especialmente em sistemas legados de ERP/PCP/MRP, onde procedures grandes acumulam anos de manutenção. Problemas comuns como exceções silenciosas (`WHEN OTHERS THEN NULL`), `SELECT *`, commits mal posicionados e valores hardcoded passam despercebidos numa revisão rápida, mas custam caro quando geram bugs em produção.

Além disso, desenvolvedores frequentemente não têm acesso imediato à documentação Oracle PL/SQL ou esquecem boas práticas específicas do domínio. Uma revisão manual também não consegue calcular complexidade ciclomática ou recuperar recomendações baseadas no contexto do código.

## Quem usa

Desenvolvedores e mantenedores de sistemas PL/SQL (o público principal imaginado é alguém no papel do próprio autor: desenvolvedor com background em ERP/PCP/MRP) que querem:

- Uma primeira passada automatizada de revisão antes de um code review humano
- Apoio em revisões de código legado
- Recomendações baseadas em documentação Oracle PL/SQL
- Métricas de qualidade como complexidade ciclomática
- Histórico de interações para aprendizado contínuo

## Proposta de valor

Um agente que combina três camadas de análise:

1. **Análise estática determinística** (rápida, sem custo de API) — pega padrões de risco conhecidos via heurísticas (WHEN OTHERS, SELECT *, COMMIT, etc.)

2. **RAG (Retrieval-Augmented Generation)** — recupera documentação Oracle PL/SQL e boas práticas baseadas no código e achados, considerando contexto extra e histórico de interações

3. **Revisão qualitativa por LLM** — interpreta o código no contexto dos achados estáticos, RAG e histórico, confirma ou descarta falsos positivos, e sugere melhorias priorizadas

O resultado é um relatório único, estruturado, com:
- Tabela de achados estáticos (linha, severidade, descrição)
- Complexidade ciclomática estimada
- Recomendações de boas práticas Oracle PL/SQL
- Parecer qualitativo do LLM com sugestões concretas

## Fora do escopo do produto

- Não é um linter de produção nem substitui um parser PL/SQL real.
- Não se conecta a um banco de dados Oracle — trabalha apenas com o texto do código.
- Não pretende cobrir 100% das más práticas possíveis em PL/SQL — as regras estáticas são um subconjunto ilustrativo.
- Não possui checkpointer persistente em banco de dados (apenas memória/volátil no estado atual).

## Recursos de segurança

- **Validação de permissões**: verifica que o caminho não é protegido antes de ler
- **Validação de API Key**: verifica formato antes de usar serviço externo
- **Sanitização de saída**: remove segredos de logs e outputs
- **Autonomia**: cada ação tem nível definido (AUTO, MONITORED, APPROVED, BLOCKED)

## Critério de sucesso

O agente é considerado bem-sucedido se:

- Recebe um arquivo PL/SQL real (ou próximo de real) e produz um relatório coerente e útil.
- O relatório aponta pelo menos os problemas mais óbvios do arquivo de exemplo (exceção silenciosa, `SELECT *`, commit interno).
- O fluxo LangGraph com paralelização, RAG e validação de permissões ficam claros para quem avalia o repositório.
- O relatório inclui recomendações de boas práticas Oracle PL/SQL e complexidade ciclomática.
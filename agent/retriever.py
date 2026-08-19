"""
Módulo de recuperação de contexto (RAG) para o agente revisor de PL/SQL.

Este módulo recupera documentação Oracle PL/SQL baseada no código sendo revisado,
usando uma combinação de busca por keywords e heurísticas de domínio.

O RAG enriquece o contexto do LLM com:
- Documentação oficial Oracle (tratamento de exceções, cursores, transações)
- Boas práticas específicas do domínio ERP/PCP/MRP
- Exemplos de código corrigido para problemas comuns
"""

from typing import List, Dict, Any, Optional
import re


class PLSQLRetriever:
    """Recupera documentação Oracle PL/SQL baseada no código e achados.
    
    O RAG também considera:
    - Histórico de execuções anteriores (padrões de erros, perguntas frequentes)
    - Contexto extra (configurações, preferências do usuário)
    - Documentação Oracle PL/SQL e boas práticas
    """
    
    def __init__(self, historico: Optional[List[Dict[str, Any]]] = None):
        # Simulação de banco de dados de documentação
        # Em produção, isso usaria um vector store (ex: Chroma, FAISS)
        self._docs_db = [
            {
                "id": "doc_exception_001",
                "titulo": "Tratamento de Exceções WHEN OTHERS",
                "topico": "exception_handling",
                "conteudo": """Evite usar WHEN OTHERS THEN NULL pois isso ignora todos os erros.
Sempre inclua RAISE ou RAISE_APPLICATION_ERROR para propagar erros ou logging adequado.

Exemplo de código problemático:
    WHEN OTHERS THEN NULL;

Exemplo corrigido:
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20001, 'Erro inesperado: ' || SQLERRM);
""",
                "keywords": ["WHEN OTHERS", "exception", "raise", "null", "error"],
                "relevancia_base": 0.9,
            },
            {
                "id": "doc_cursor_001",
                "titulo": "Tratamento de Cursor e NO_DATA_FOUND",
                "topico": "cursor_handling",
                "conteudo": """Ao declarar cursores, sempre inclua tratamento para NO_DATA_FOUND e TOO_MANY_ROWS.
O uso de SELECT INTO sem tratamento adequado pode causar erros em runtime.

Exemplo de código problemático:
    SELECT coluna INTO variavel FROM tabela WHERE condicao;

Exemplo corrigido:
    BEGIN
        SELECT coluna INTO variavel FROM tabela WHERE condicao;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            variavel := valor_padrao;
        WHEN TOO_MANY_ROWS THEN
            RAISE_APPLICATION_ERROR(-20002, 'Múltiplos registros encontrados');
    END;
""",
                "keywords": ["CURSOR", "NO_DATA_FOUND", "TOO_MANY_ROWS", "SELECT INTO"],
                "relevancia_base": 0.85,
            },
            {
                "id": "doc_transaction_001",
                "titulo": "Controle de Transações e COMMIT",
                "topico": "transaction_control",
                "conteudo": """Evite COMMIT dentro de procedures. O controle de transação deve ficar no nível superior
(camada de serviço ou chamador) para permitir rollback em caso de erros.

Exemplo de código problemático:
    COMMIT;

Exemplo corrigido:
    -- Deixar o controle para o chamador, usando SAVEPOINT se necessário
    SAVEPOINT inicio_operacao;
    -- ... operações ...
    -- COMMIT deve vir no nível superior
""",
                "keywords": ["COMMIT", "ROLLBACK", "SAVEPOINT", "transaction"],
                "relevancia_base": 0.88,
            },
            {
                "id": "doc_select_001",
                "titulo": "Evitar SELECT * em PL/SQL",
                "topico": "performance",
                "conteudo": """SELECT * deve ser evitado em PL/SQL pois:
1. Quebra quando o schema muda (colunas adicionadas/removidas)
2. Afeta performance (leitura de colunas desnecessárias)
3. Dificulta manutenção

Exemplo de código problemático:
    SELECT * FROM tabela INTO registro;

Exemplo corrigido:
    SELECT col1, col2, col3 INTO variavel1, variavel2, variavel3 FROM tabela;
""",
                "keywords": ["SELECT *", "SELECT ALL", "performance", "schema"],
                "relevancia_base": 0.82,
            },
            {
                "id": "doc_hardcoded_001",
                "titulo": "Valores Hardcoded em PL/SQL",
                "topico": "configuracao",
                "conteudo": """Valores hardcoded (strings literais, números mágicos) dificultam manutenção.
Use parâmetros, variáveis ou tabelas de configuração para valores que podem mudar.

Exemplo de código problemático:
    IF status = 'APROVADO' THEN ...

Exemplo corrigido:
    c_status_aprovado CONSTANT VARCHAR2(20) := 'APROVADO';
    IF status = c_status_aprovado THEN ...
    
    -- Ou melhor: usar tabela de configuração
    SELECT valor INTO v_parametro FROM tabela_config WHERE chave = 'STATUS_APROVADO';
""",
                "keywords": ["hardcoded", "literal", "configuração", "constante"],
                "relevancia_base": 0.75,
            },
            {
                "id": "doc_debug_001",
                "titulo": "Debugging e Logging em PL/SQL",
                "topico": "debugging",
                "conteudo": """Use DBMS_OUTPUT apenas para desenvolvimento. Em produção, use logging estruturado
com DBMS_LOB ou tabelas de log.

Exemplo:
    -- Desenvolvimento
    DBMS_OUTPUT.PUT_LINE('Valor: ' || valor);
    
    -- Produção (recomendado)
    INSERT INTO log_operacoes (data, mensagem, detalhes)
    VALUES (SYSDATE, 'Processando registro', 'ID=' || id_registro);
""",
                "keywords": ["debug", "log", "DBMS_OUTPUT", "logging"],
                "relevancia_base": 0.7,
            },
        ]

    def retrieve(self, codigo: str, issues: List[Dict[str, Any]], 
                 contexto_extra: Optional[Dict[str, Any]] = None,
                 historico: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Recupera documentos relevantes baseados no código, achados, contexto extra e histórico.
        
        Args:
            codigo: Código PL/SQL completo sendo revisado
            issues: Lista de achados da análise estática
            contexto_extra: Dicionário com configurações ou preferências do usuário
            historico: Histórico de execuções anteriores (para aprendizado)
            
        Returns:
            Dict com:
            - documentos: Lista de documentos relevantes
            - queries: Queries usadas na busca
            - score: Score médio de relevância (0-1)
            
        Validações:
        - `codigo` deve ser string não vazia
        - `issues` deve ser lista
        - `contexto_extra` deve ser dict ou None
        - `historico` deve ser lista ou None
        """
        # Validação de entrada
        if not isinstance(codigo, str) or not codigo.strip():
            raise ValueError("Parâmetro 'codigo' deve ser uma string não vazia")
        
        if not isinstance(issues, list):
            raise ValueError("Parâmetro 'issues' deve ser uma lista")
        
        if contexto_extra is not None and not isinstance(contexto_extra, dict):
            raise ValueError("Parâmetro 'contexto_extra' deve ser um dicionário ou None")
        
        if historico is not None and not isinstance(historico, list):
            raise ValueError("Parâmetro 'historico' deve ser uma lista ou None")
        
        documentos_relevantes = []
        queries = []
        
        # Extrai keywords do código
        keywords_codigo = self._extrair_keywords(codigo)
        
        # Extrai keywords dos achados
        for issue in issues:
            keywords_achado = self._extrair_keywords_da_regra(issue.get("regra", ""))
            keywords_codigo.extend(keywords_achado)
        
        # Adiciona keywords do contexto extra (ex: preferências, configurações)
        if contexto_extra and "keywords" in contexto_extra:
            keywords_codigo.extend(contexto_extra["keywords"])
        
        # Adiciona keywords do histórico (ex: erros frequentes, perguntas anteriores)
        if historico:
            for msg in historico:
                if msg.get("role") == "user":
                    keywords_historico = self._extrair_keywords(msg.get("content", ""))
                    keywords_codigo.extend(keywords_historico)
        
        # Remove duplicatas mantendo ordem
        keywords_unicas = list(dict.fromkeys(keywords_codigo))
        
        # Busca em cada documento
        for doc in self._docs_db:
            # Score base + bonus por match de keywords
            score_base = doc["relevancia_base"]
            keywords_doc = doc["keywords"]
            
            matches = sum(1 for kw in keywords_unicas if any(kw.lower() in k.lower() for k in keywords_doc))
            score_final = min(1.0, score_base + (matches * 0.05))
            
            if score_final > 0.3:  # Threshold de relevância
                documentos_relevantes.append({
                    "id": doc["id"],
                    "titulo": doc["titulo"],
                    "topico": doc["topico"],
                    "conteudo": doc["conteudo"],
                    "score": round(score_final, 2),
                })
        
        # Ordena por score decrescente
        documentos_relevantes.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "documentos": documentos_relevantes,
            "queries": keywords_unicas[:5],  # Top 5 queries
            "score": round(sum(d["score"] for d in documentos_relevantes) / max(1, len(documentos_relevantes)), 2) if documentos_relevantes else 0,
        }

    def _extrair_keywords(self, texto: str) -> List[str]:
        """Extrai keywords relevantes do texto."""
        keywords = []
        
        # Padrões PL/SQL específicos
        padroes = [
            r"\bWHEN\s+OTHERS\b",
            r"\bSELECT\s+\*",
            r"\bCOMMIT\b",
            r"\bROLLBACK\b",
            r"\bSAVEPOINT\b",
            r"\bCURSOR\b",
            r"\bNO_DATA_FOUND\b",
            r"\bTOO_MANY_ROWS\b",
            r"\bRAISE\b",
            r"\bRAISE_APPLICATION_ERROR\b",
            r"=\s*'[A-Z0-9_]{2,}'",
        ]
        
        for padrao in padroes:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                # Mapeia para keyword legível
                if "WHEN OTHERS" in padrao:
                    keywords.append("WHEN OTHERS")
                elif "SELECT *" in padrao:
                    keywords.append("SELECT *")
                elif "COMMIT" in padrao:
                    keywords.append("COMMIT")
                elif "ROLLBACK" in padrao:
                    keywords.append("ROLLBACK")
                elif "SAVEPOINT" in padrao:
                    keywords.append("SAVEPOINT")
                elif "CURSOR" in padrao:
                    keywords.append("CURSOR")
                elif "NO_DATA_FOUND" in padrao:
                    keywords.append("NO_DATA_FOUND")
                elif "TOO_MANY_ROWS" in padrao:
                    keywords.append("TOO_MANY_ROWS")
                elif "RAISE" in padrao:
                    keywords.append("RAISE")
                elif "RAISE_APPLICATION_ERROR" in padrao:
                    keywords.append("RAISE_APPLICATION_ERROR")
                elif "hardcoded" in padrao:
                    keywords.append("HARDCODED")
        
        return keywords

    def _extrair_keywords_da_regra(self, regra: str) -> List[str]:
        """Extrai keywords da descrição de uma regra."""
        keywords = []
        
        if "WHEN OTHERS" in regra:
            keywords.append("WHEN OTHERS")
        if "SELECT *" in regra:
            keywords.append("SELECT *")
        if "COMMIT" in regra:
            keywords.append("COMMIT")
        if "CURSOR" in regra:
            keywords.append("CURSOR")
        if "hardcoded" in regra.lower():
            keywords.append("HARDCODED")
        if "exception" in regra.lower() or "EXCEPTION" in regra:
            keywords.append("EXCEPTION")
            
        return keywords

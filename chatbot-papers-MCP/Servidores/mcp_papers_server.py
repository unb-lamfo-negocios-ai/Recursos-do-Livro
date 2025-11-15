#!/usr/bin/env python3
"""
=== SERVIDOR MCP PARA PAPERS ACADÊMICOS ===

O QUE É ESTE CÓDIGO?
Este é um MCP SERVER que fornece ferramentas (tools) para:
- Buscar papers acadêmicos no ArXiv
- Analisar papers com IA (Google Gemini)
- Responder perguntas sobre papers

CONCEITOS MCP APLICADOS:
- MCP Server: Esta aplicação (fornece recursos)
- MCP Tools: Funções que o servidor disponibiliza
- Conexão: Aguarda conexão de MCP Clients (hosts)
"""

import os
import sys
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# === IMPORTAÇÃO DO FASTMCP ===
# FastMCP é uma biblioteca que facilita criar servidores MCP
# Ela implementa o protocolo MCP automaticamente
from fastmcp import FastMCP, Context

# === IMPORTAÇÕES DE SERVIÇOS EXTERNOS ===
import arxiv  # Para buscar papers acadêmicos
import google.generativeai as genai  # IA do Google (Gemini)
from dotenv import load_dotenv  # Para carregar variáveis de ambiente
import re

# Configurar logging (registro de eventos)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis secretas (API keys)
load_dotenv()

# === CRIAR SERVIDOR MCP ===
# FastMCP cria automaticamente um servidor que implementa o protocolo MCP
mcp = FastMCP(
    name="papers-academic-server",  # Nome do servidor
    version="1.0.0",  # Versão
    instructions="Servidor MCP para busca e análise de papers acadêmicos usando ArXiv e Google Gemini"
)

class PapersService:
    """
    === CLASSE DE SERVIÇOS ===
    
    Esta classe contém a lógica de negócio do servidor.
    Ela não é MCP - é apenas código Python normal que:
    - Busca papers no ArXiv
    - Analisa papers com IA
    - Gerencia cache de papers
    
    As MCP Tools (abaixo) usam esta classe para fazer o trabalho pesado.
    """
    
    def __init__(self):
        """
        === INICIALIZAÇÃO DO SERVIÇO ===
        
        Prepara o servidor para funcionar:
        1. Carrega a chave de API do Google
        2. Inicializa o modelo de IA (Gemini)
        3. Cria cache vazio para armazenar papers
        """
        # Buscar chave de API das variáveis de ambiente
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            logger.error("GOOGLE_API_KEY não encontrada no ambiente")
            raise ValueError("GOOGLE_API_KEY não encontrada no arquivo .env")
        
        # Configurar Google Gemini (IA)
        genai.configure(api_key=api_key) #type: ignore
        self.model = genai.GenerativeModel('gemini-2.5-pro') #type: ignore
         
        # Cache para armazenar papers em memória
        # É como uma gaveta temporária onde guardamos os papers encontrados
        self.papers_cache: List[Dict[str, Any]] = []
        
        logger.info("PapersService inicializado com sucesso")

    async def search_papers_async(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        === BUSCAR PAPERS NO ARXIV ===
        
        Esta função busca papers acadêmicos na base de dados ArXiv.
        
        PROCESSO:
        1. Valida os parâmetros de busca
        2. Executa busca no ArXiv em thread separada (não trava o servidor)
        3. Armazena resultados no cache
        4. Retorna lista de papers
        
        É como procurar livros em uma biblioteca:
        - query = palavras-chave que você busca
        - max_results = quantos livros você quer encontrar
        """
        try:
            # === VALIDAÇÃO ===
            # Verificar se os parâmetros fazem sentido
            if not query or not isinstance(query, str):
                return []
            
            # Limitar resultados entre 1 e 10
            max_results = min(max(1, max_results), 10)
            
            logger.info(f"Buscando papers sobre: '{query}'")
            
            # === EXECUTAR BUSCA ASSÍNCRONA ===
            # run_in_executor permite executar código síncrono sem travar
            # É como delegar uma tarefa para outra pessoa enquanto você continua trabalhando
            loop = asyncio.get_event_loop()
            papers = await loop.run_in_executor(
                None,  # Usar executor padrão
                self._search_papers_sync,  # Função a executar
                query,  # Parâmetros
                max_results
            )
            
            # === ARMAZENAR NO CACHE ===
            # Guardar papers encontrados para uso posterior
            self.papers_cache = papers
            logger.info(f"Encontrados {len(papers)} papers relevantes")
            return papers
            
        except Exception as e:
            logger.error(f"Erro ao buscar papers: {str(e)}")
            return []

    def _search_papers_sync(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        === BUSCA SÍNCRONA NO ARXIV ===
        
        Esta é a função que realmente faz a busca.
        Ela é "síncrona" = bloqueia enquanto executa.
        Por isso é executada em thread separada pela função acima.
        
        PROCESSO:
        1. Conecta ao ArXiv
        2. Busca papers pela query
        3. Processa cada resultado
        4. Retorna lista formatada
        """
        # Criar cliente ArXiv
        client = arxiv.Client()
        
        # Configurar busca
        search = arxiv.Search(
            query=query.strip(),  # Remover espaços extras
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance  # Mais relevantes primeiro
        )
        
        papers = []
        for result in client.results(search):
            if len(papers) >= max_results:
                break
                
            try:
                # === EXTRAIR INFORMAÇÕES DO PAPER ===
                # Criar dicionário com dados estruturados
                paper = {
                    "title": result.title.strip(),
                    "summary": result.summary.strip()[:1000],  # Limitar tamanho
                    "authors": [author.name for author in result.authors][:5],  # Primeiros 5 autores
                    "published": result.published.strftime("%Y-%m-%d") if result.published else "N/A",
                    "url": result.entry_id,  # Link do paper
                    "pdf_url": result.pdf_url,  # Link do PDF
                    "categories": result.categories[:3] if hasattr(result, 'categories') else []
                }
                papers.append(paper)
            except Exception as e:
                logger.warning(f"Erro ao processar paper: {e}")
                continue
        
        return papers

    async def analyze_papers_async(self, papers: List[Dict[str, Any]], analysis_type: str = "summary") -> str:
        """
        === ANALISAR PAPERS COM IA ===
        
        Usa o Google Gemini (IA) para analisar papers.
        
        TIPOS DE ANÁLISE:
        - summary: Resumo executivo dos papers
        - trends: Identifica tendências de pesquisa
        - comparison: Compara metodologias e resultados
        
        É como pedir para um especialista ler vários artigos
        e te dar um resumo inteligente sobre eles.
        """
        if not papers:
            return "Nenhum paper disponível para análise."
        
        try:
            # Executar análise em thread separada (não trava o servidor)
            loop = asyncio.get_event_loop()
            analysis = await loop.run_in_executor(
                None,
                self._analyze_papers_sync,
                papers,
                analysis_type
            )
            return analysis
        except Exception as e:
            logger.error(f"Erro ao analisar papers: {str(e)}")
            return f"Erro na análise: {str(e)}"

    def _analyze_papers_sync(self, papers: List[Dict[str, Any]], analysis_type: str) -> str:
        """
        === ANÁLISE SÍNCRONA COM GEMINI ===
        
        Função que realmente faz a análise usando IA.
        
        PROCESSO:
        1. Formata papers para contexto
        2. Escolhe prompt adequado ao tipo de análise
        3. Envia para o Gemini
        4. Retorna resposta da IA
        """
        # Formatar papers em texto legível
        papers_context = self._format_papers_context(papers)
        
        # === PROMPTS PARA CADA TIPO DE ANÁLISE ===
        # Cada tipo de análise tem um prompt (instrução) específico para a IA
        prompts = {
            "summary": f"""
                Analise os seguintes papers acadêmicos e forneça um resumo executivo destacando:
                1. Principais temas e tendências
                2. Metodologias mais utilizadas
                3. Descobertas significativas
                4. Lacunas de pesquisa identificadas
                
                Papers:
                {papers_context}
            """,
            "trends": f"""
                Identifique as principais tendências de pesquisa nos papers abaixo:
                - Tecnologias emergentes
                - Mudanças de paradigma
                - Áreas de crescimento
                
                Papers:
                {papers_context}
            """,
            "comparison": f"""
                Compare e contraste os papers abaixo considerando:
                - Abordagens metodológicas
                - Resultados obtidos
                - Contribuições únicas
                
                Papers:
                {papers_context}
            """
        }
        
        # Escolher prompt apropriado
        prompt = prompts.get(analysis_type, prompts["summary"])
        
        # === ENVIAR PARA IA E OBTER RESPOSTA ===
        response = self.model.generate_content(prompt)
        
        return response.text.strip() if response and response.text else "Análise não disponível."

    def _format_papers_context(self, papers: List[Dict[str, Any]]) -> str:
        """
        === FORMATAR PAPERS PARA IA ===
        
        Transforma lista de papers em texto formatado
        que a IA consegue entender e analisar.
        
        É como preparar um documento resumido dos papers
        para enviar à IA.
        """
        context = ""
        for i, paper in enumerate(papers[:5], 1):  # Limitar a 5 papers
            authors = ", ".join(paper["authors"][:2]) + (" et al." if len(paper["authors"]) > 2 else "")
            context += f"""
Paper {i}:
Título: {paper["title"]}
Autores: {authors}
Data: {paper["published"]}
Resumo: {paper["summary"][:500]}...
URL: {paper["url"]}

"""
        return context

# === INSTÂNCIA GLOBAL DO SERVIÇO ===
# Criar uma instância única do serviço que será usada por todas as tools
papers_service = PapersService()

# ==========================================
# === FERRAMENTAS MCP (TOOLS) ===
# ==========================================
# 
# As funções abaixo são MCP TOOLS.
# Elas são expostas pelo servidor e podem ser chamadas pelos clients.
# 
# DECORADOR @mcp.tool():
# - Registra a função como ferramenta MCP
# - FastMCP cuida de toda a comunicação
# - Client pode descobrir e chamar estas ferramentas
#
# É como um cardápio: cada função é um prato que o cliente pode pedir.

@mcp.tool()
async def search_papers(
    ctx: Context,  # Contexto MCP (informações da requisição)
    query: str,
    max_results: int = 5
) -> Dict[str, Any]:
    """
    === MCP TOOL: BUSCAR PAPERS ===
    
    Esta é uma FERRAMENTA MCP que o servidor disponibiliza.
    Quando um client chama esta tool, o servidor busca papers no ArXiv.
    
    FLUXO MCP:
    1. Client chama: call_tool("search_papers", {"query": "AI", "max_results": 5})
    2. MCP envia requisição para este servidor
    3. Esta função é executada
    4. Resultado é enviado de volta ao client
    
    Args:
        ctx: Contexto MCP (automaticamente fornecido)
        query: O que buscar
        max_results: Quantos resultados retornar
    
    Returns:
        Dicionário com papers encontrados
    """
    logger.info(f"Tool 'search_papers' chamada com query='{query}', max_results={max_results}")
    
    # Usar o serviço para fazer a busca
    papers = await papers_service.search_papers_async(query, max_results)
    
    # === RETORNO PADRONIZADO ===
    # Retornar sempre em formato consistente para o client
    return {
        "success": len(papers) > 0,
        "count": len(papers),
        "papers": papers,
        "message": f"Encontrados {len(papers)} papers sobre '{query}'"
    }

@mcp.tool()
async def get_paper_details(
    ctx: Context,
    paper_index: int = 0
) -> Dict[str, Any]:
    """
    === MCP TOOL: DETALHES DE UM PAPER ===
    
    Retorna informações completas de um paper específico do cache.
    
    CONCEITO DE CACHE:
    O servidor mantém papers em memória (cache) após uma busca.
    Esta tool acessa um paper específico pelo índice.
    
    É como uma estante temporária onde guardamos os últimos
    papers encontrados para consulta rápida.
    """
    # Verificar se há papers no cache
    if not papers_service.papers_cache:
        return {
            "success": False,
            "message": "Nenhum paper no cache. Execute uma busca primeiro."
        }
    
    # Validar índice
    if paper_index < 0 or paper_index >= len(papers_service.papers_cache):
        return {
            "success": False,
            "message": f"Índice inválido. Cache contém {len(papers_service.papers_cache)} papers."
        }
    
    # Retornar paper solicitado
    paper = papers_service.papers_cache[paper_index]
    return {
        "success": True,
        "paper": paper,
        "index": paper_index,
        "total_cached": len(papers_service.papers_cache)
    }

@mcp.tool()
async def analyze_papers(
    ctx: Context,
    analysis_type: str = "summary"
) -> Dict[str, Any]:
    """
    === MCP TOOL: ANALISAR PAPERS COM IA ===
    
    Analisa papers no cache usando inteligência artificial.
    
    TIPOS DE ANÁLISE:
    - "summary": Resumo executivo
    - "trends": Tendências de pesquisa
    - "comparison": Comparação entre papers
    
    Esta tool demonstra como o servidor pode fazer processamento
    complexo (usar IA) e retornar resultados para o client.
    """
    # Verificar se há papers para analisar
    if not papers_service.papers_cache:
        return {
            "success": False,
            "message": "Nenhum paper no cache. Execute uma busca primeiro."
        }
    
    # Validar tipo de análise
    valid_types = ["summary", "trends", "comparison"]
    if analysis_type not in valid_types:
        return {
            "success": False,
            "message": f"Tipo de análise inválido. Use: {', '.join(valid_types)}"
        }
    
    logger.info(f"Analisando {len(papers_service.papers_cache)} papers - tipo: {analysis_type}")
    
    # Executar análise
    analysis = await papers_service.analyze_papers_async(
        papers_service.papers_cache, 
        analysis_type
    )
    
    return {
        "success": True,
        "analysis_type": analysis_type,
        "papers_analyzed": len(papers_service.papers_cache),
        "analysis": analysis
    }

@mcp.tool()
async def clear_cache(ctx: Context) -> Dict[str, Any]:
    """
    === MCP TOOL: LIMPAR CACHE ===
    
    Remove todos os papers da memória.
    
    É útil para:
    - Liberar memória
    - Começar uma nova sessão de busca
    - Limpar dados antigos
    """
    previous_count = len(papers_service.papers_cache)
    papers_service.papers_cache = []
    
    return {
        "success": True,
        "message": f"Cache limpo. {previous_count} papers removidos."
    }

@mcp.tool()
async def get_cache_info(ctx: Context) -> Dict[str, Any]:
    """
    === MCP TOOL: INFORMAÇÕES DO CACHE ===
    
    Retorna estatísticas sobre papers armazenados.
    
    INFORMAÇÕES FORNECIDAS:
    - Número de papers no cache
    - Títulos dos papers
    - Categorias encontradas
    - Anos de publicação
    - Total de autores
    
    É como pedir um relatório do que está armazenado na memória.
    """
    cache = papers_service.papers_cache
    
    if not cache:
        return {
            "success": True,
            "cached_papers": 0,
            "message": "Cache vazio"
        }
    
    # === CALCULAR ESTATÍSTICAS ===
    
    # Coletar todas as categorias
    categories = []
    for paper in cache:
        if "categories" in paper:
            categories.extend(paper.get("categories", []))
    
    unique_categories = list(set(categories))
    
    # Extrair anos de publicação
    years = []
    for paper in cache:
        if paper.get("published") and paper["published"] != "N/A":
            try:
                year = paper["published"].split("-")[0]
                years.append(year)
            except:
                pass
    
    # Retornar estatísticas completas
    return {
        "success": True,
        "cached_papers": len(cache),
        "paper_titles": [p["title"][:100] for p in cache],
        "categories": unique_categories[:10],
        "publication_years": list(set(years)),
        "total_authors": sum(len(p.get("authors", [])) for p in cache),
        "message": f"Cache contém {len(cache)} papers"
    }

@mcp.tool()
async def chat_about_papers(
    ctx: Context,
    message: str
) -> Dict[str, Any]:
    """
    === MCP TOOL: CHAT INTERATIVO ===
    
    Permite conversar com a IA sobre papers.
    
    FUNCIONALIDADES:
    1. Se a mensagem contém palavras de busca ("busque", "procure"):
       - Faz busca automática
       - Retorna resposta sobre papers encontrados
    
    2. Se não é busca:
       - Usa papers do cache como contexto
       - Responde perguntas sobre os papers
    
    Esta tool demonstra IA conversacional contextualizada.
    É como ter um assistente que conhece os papers e pode
    responder perguntas sobre eles.
    """
    try:
        # === DETECTAR SE PRECISA FAZER BUSCA ===
        search_keywords = ['busque', 'procure', 'encontre', 'pesquise']
        needs_search = any(keyword in message.lower() for keyword in search_keywords)
        
        if needs_search:
            # === CASO 1: BUSCA AUTOMÁTICA ===
            
            # Extrair termos de busca da mensagem
            query = message.lower()
            for keyword in search_keywords:
                query = query.replace(keyword, "").strip()
            
            # Buscar papers
            papers = await papers_service.search_papers_async(query, 5)
            
            if papers:
                # Gerar resposta com contexto dos papers encontrados
                context = papers_service._format_papers_context(papers)
                prompt = f"""
                Pergunta do usuário: {message}
                
                Papers encontrados:
                {context}
                
                Responda de forma clara e informativa sobre os papers encontrados.
                """
            else:
                prompt = f"""
                Pergunta do usuário: {message}
                
                Não foram encontrados papers sobre este tema.
                Sugira alternativas ou forneça informações gerais sobre o tópico.
                """
        else:
            # === CASO 2: USAR CACHE ===
            
            # Usar papers já armazenados no cache
            if papers_service.papers_cache:
                context = papers_service._format_papers_context(papers_service.papers_cache)
                prompt = f"""
                Pergunta do usuário: {message}
                
                Papers disponíveis no contexto:
                {context}
                
                Responda baseando-se nos papers disponíveis.
                """
            else:
                # Sem papers no cache - resposta genérica
                prompt = f"""
                Pergunta do usuário: {message}
                
                Responda como um assistente especializado em papers acadêmicos.
                Sugira fazer buscas se necessário.
                """
        
        # === GERAR RESPOSTA COM IA ===
        response = papers_service.model.generate_content(prompt)
        answer = response.text.strip() if response and response.text else "Não foi possível gerar uma resposta."
        
        return {
            "success": True,
            "message": message,
            "response": answer,
            "papers_in_context": len(papers_service.papers_cache)
        }
        
    except Exception as e:
        logger.error(f"Erro no chat: {str(e)}")
        return {
            "success": False,
            "message": f"Erro ao processar mensagem: {str(e)}"
        }

# ==========================================
# === FUNÇÃO PRINCIPAL ===
# ==========================================

def main():
    """
    === INICIAR SERVIDOR MCP ===
    
    Esta função inicia o servidor e o mantém rodando.
    
    PROCESSO:
    1. Verificar se API key do Google está configurada
    2. Iniciar servidor MCP
    3. Aguardar conexões de clients
    4. Processar requisições
    
    O servidor fica em loop infinito aguardando requisições MCP.
    Quando um client se conecta e chama uma tool, o servidor
    executa e retorna o resultado.
    """
    try:
        # Verificar configuração obrigatória
        if not os.getenv('GOOGLE_API_KEY'):
            logger.error("GOOGLE_API_KEY não configurada!")
            sys.exit(1)
        
        logger.info("Iniciando servidor MCP de Papers Acadêmicos...")
        
        # === EXECUTAR SERVIDOR MCP ===
        # mcp.run() inicia o servidor e fica aguardando conexões
        # FastMCP cuida de toda a comunicação do protocolo MCP
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("Servidor interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
=== RESUMO DA ARQUITETURA DO SERVIDOR MCP ===

┌─────────────────────────────────────────────┐
│  MCP SERVER (esta aplicação)                │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  FastMCP                            │   │
│  │  (gerencia protocolo MCP)           │   │
│  └─────────────┬───────────────────────┘   │
│                │                            │
│  ┌─────────────▼───────────────────────┐   │
│  │  MCP Tools (6 ferramentas):        │   │
│  │  • search_papers                   │   │
│  │  • get_paper_details               │   │
│  │  • analyze_papers                  │   │
│  │  • chat_about_papers               │   │
│  │  • get_cache_info                  │   │
│  │  • clear_cache                     │   │
│  └─────────────┬───────────────────────┘   │
│                │                            │
│  ┌─────────────▼───────────────────────┐   │
│  │  PapersService                     │   │
│  │  (lógica de negócio)               │   │
│  │  • Busca no ArXiv                  │   │
│  │  • Análise com Gemini              │   │
│  │  • Gerenciamento de cache          │   │
│  └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
         ▲                    ▲
         │                    │
         │                    │
    ┌────┴────┐          ┌────┴────┐
    │ ArXiv   │          │ Gemini  │
    │ API     │          │ AI      │
    └─────────┘          └─────────┘

FLUXO DE UMA REQUISIÇÃO:
1. Client envia requisição MCP para chamar uma tool
2. FastMCP recebe e roteia para a função correta
3. Função (tool) executa lógica usando PapersService
4. PapersService acessa APIs externas (ArXiv, Gemini)
5. Resultado é processado e formatado
6. FastMCP envia resposta MCP de volta ao client

VANTAGENS DESTA ARQUITETURA:
• Separação clara: MCP Tools vs Lógica de Negócio
• Reutilizável: Outros hosts podem usar este servidor
• Escalável: Fácil adicionar novas tools
• Manutenível: Cada componente tem responsabilidade clara
• Testável: Pode testar PapersService independentemente

EXEMPLO DE USO:
Client: call_tool("search_papers", {"query": "AI", "max_results": 5})
Server: Busca no ArXiv → Retorna papers → Client recebe

Client: call_tool("analyze_papers", {"analysis_type": "trends"})
Server: Usa Gemini → Analisa papers → Client recebe análise
"""
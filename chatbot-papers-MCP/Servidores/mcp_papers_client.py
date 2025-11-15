#!/usr/bin/env python3
"""
=== CLIENTE MCP PARA PAPERS ACADÊMICOS ===

O QUE É ESTE CÓDIGO?
Este é um MCP HOST (aplicação AI) que se conecta a MCP SERVERS
para buscar e analisar papers acadêmicos.

CONCEITOS MCP APLICADOS:
- MCP Host: Esta aplicação (orquestra tudo)
- MCP Client: Componente interno que se conecta ao servidor
- MCP Server: Servidor de papers (fornece os dados)
- Conexão: One-to-one entre client e server
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import sys
import os

# === IMPORTAÇÕES MCP ===
# Estas são as bibliotecas que implementam o protocolo MCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Para deixar o terminal colorido 
try:
    from colorama import init, Fore, Style #type: ignore
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = YELLOW = RED = CYAN = BLUE = MAGENTA = WHITE = ""
        RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

# Configurações básicas
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/mcp_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PapersClient:
    """
    === CLASSE PRINCIPAL: MCP HOST ===
    
    Esta classe representa o MCP HOST (aplicação AI).
    Ela orquestra a comunicação com o MCP SERVER de papers.
    
    RESPONSABILIDADES:
    1. Conectar-se ao MCP Server
    2. Gerenciar o MCP Client interno
    3. Chamar ferramentas (tools) do servidor
    4. Processar e exibir resultados
    """
    
    def __init__(self):
        """
        === INICIALIZAÇÃO DO HOST ===
        Prepara o host MCP para funcionar
        """
        # Variáveis do MCP
        self.session: Optional[ClientSession] = None  # Sessão MCP (gerencia a comunicação)
        self.tools: Dict[str, Any] = {}  # Ferramentas disponíveis no servidor
        
        # Variáveis de dados
        self.last_search_query: str = ""
        self.last_results: List[Dict[str, Any]] = []
        
        # Componentes de comunicação
        self.stdio_context = None  # Contexto de entrada/saída
        self.read = None   # Canal de leitura
        self.write = None  # Canal de escrita
        
        print(f"{Fore.CYAN}{Style.BRIGHT}📚 Cliente MCP de Papers Acadêmicos")
        print(f"{Fore.CYAN}================================={Style.RESET_ALL}\n")

    async def connect(self, server_path: str = "Servidores/mcp_papers_server.py") -> bool:
        """
        === ETAPA 1: CONEXÃO MCP ===
        
        Esta função estabelece a conexão one-to-one entre:
        - MCP Client (interno desta aplicação)
        - MCP Server (servidor de papers)
        
        PROTOCOLO MCP:
        1. Configurar parâmetros de conexão
        2. Estabelecer canais de comunicação (stdio)
        3. Criar sessão MCP
        4. Inicializar protocolo
        5. Descobrir ferramentas disponíveis
        
        É como fazer uma ligação telefônica:
        - Discar o número (configurar parâmetros)
        - Estabelecer a linha (criar canais)
        - Dizer "alô" (inicializar protocolo)
        - Descobrir o que o outro lado pode fazer (listar ferramentas)
        """
        try:
            print(f"{Fore.YELLOW}🔌 Conectando ao servidor MCP...{Style.RESET_ALL}")
        
            # === PASSO 1: CONFIGURAR PARÂMETROS DO SERVIDOR ===
            # Define como executar o servidor MCP (Python script)
            server_params = StdioServerParameters(
                command="python",  # Comando para executar
                args=[server_path],  # Caminho do servidor
                env=dict(os.environ)  # Variáveis de ambiente
            )
        
            # === PASSO 2: CRIAR CANAIS DE COMUNICAÇÃO ===
            # stdio = Standard Input/Output (entrada/saída padrão)
            # É como criar dois tubos: um para enviar, outro para receber mensagens
            self.stdio_context = stdio_client(server_params)
            self.read, self.write = await self.stdio_context.__aenter__()
        
            # === PASSO 3: CRIAR SESSÃO MCP ===
            # A sessão gerencia toda a comunicação usando o protocolo MCP
            self.session = ClientSession(self.read, self.write)
            await self.session.__aenter__()

            # === PASSO 4: INICIALIZAR PROTOCOLO MCP ===
            # Faz o "handshake" inicial - apresentação entre client e server
            await self.session.initialize()
        
            # === PASSO 5: DESCOBRIR FERRAMENTAS (TOOLS) ===
            # O servidor informa quais ferramentas ele oferece
            # É como perguntar: "O que você sabe fazer?"
            tools_response = await self.session.list_tools()
            self.tools = {tool.name: tool for tool in tools_response.tools}
        
            print(f"{Fore.GREEN}✅ Conectado com sucesso!")
            print(f"{Fore.GREEN}📦 {len(self.tools)} ferramentas disponíveis:{Style.RESET_ALL}")
        
            for tool_name in self.tools:
                print(f"   • {Fore.CYAN}{tool_name}{Style.RESET_ALL}")
        
            print()
            return True
        
        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao conectar: {str(e)}{Style.RESET_ALL}")
            logger.error(f"Erro de conexão: {str(e)}")
            return False

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        === ETAPA 2: CHAMAR FERRAMENTAS (TOOLS) ===
        
        CONCEITO MCP TOOLS:
        Tools são funções que o MCP Server disponibiliza.
        É como um cardápio de restaurante - você escolhe o que quer
        e o servidor prepara para você.
        
        PROCESSO:
        1. Verificar se a ferramenta existe
        2. Enviar requisição ao servidor via protocolo MCP
        3. Aguardar resposta
        4. Processar e retornar resultado
        
        EXEMPLO:
        call_tool("search_papers", {"query": "AI", "max_results": 5})
        - Ferramenta: search_papers
        - Argumentos: query e max_results
        - Servidor processa e retorna papers
        """
        if not self.session:
            raise RuntimeError("Cliente não conectado ao servidor")
        
        if tool_name not in self.tools:
            raise ValueError(f"Ferramenta '{tool_name}' não encontrada")
        
        try:
            logger.info(f"Chamando ferramenta: {tool_name} com args: {arguments}")
            
            # === CHAMADA MCP ===
            # Envia requisição ao servidor usando o protocolo MCP
            result = await self.session.call_tool(
                name=tool_name,
                arguments=arguments
            )
            
            # === PROCESSAR RESPOSTA ===
            # O servidor responde em formato MCP padrão
            # Precisamos extrair o conteúdo útil
            if hasattr(result, 'content'):
                if isinstance(result.content, list) and result.content:
                    content = result.content[0]
                    text = getattr(content, 'text', None)
                    if text:
                        return json.loads(text)
                    
            return {"error": "Formato de resposta inesperado"}
            
        except Exception as e:
            logger.error(f"Erro ao chamar ferramenta {tool_name}: {str(e)}")
            return {"error": str(e)}

    async def search_papers(self, query: str, max_results: int = 5):
        """
        === FUNÇÃO DE NEGÓCIO: BUSCAR PAPERS ===
        
        Usa a ferramenta MCP "search_papers" do servidor.
        
        FLUXO MCP:
        1. Host chama call_tool()
        2. Client envia requisição ao Server
        3. Server busca papers no ArXiv
        4. Server retorna resultados
        5. Host processa e exibe
        """
        print(f"\n{Fore.YELLOW}🔍 Buscando papers sobre: '{query}'...{Style.RESET_ALL}")
        
        # Chama a ferramenta MCP no servidor
        result = await self.call_tool("search_papers", {
            "query": query,
            "max_results": max_results
        })
        
        if result.get("success"):
            self.last_search_query = query
            self.last_results = result.get("papers", [])
            
            print(f"{Fore.GREEN}✅ {result.get('message')}{Style.RESET_ALL}\n")
            
            # Exibir papers encontrados
            for i, paper in enumerate(self.last_results, 1):
                self._display_paper_summary(i, paper)
        else:
            print(f"{Fore.RED}❌ Nenhum paper encontrado{Style.RESET_ALL}")

    def _display_paper_summary(self, index: int, paper: Dict[str, Any]):
        """Formata e exibe resumo de um paper na tela"""
        print(f"{Fore.CYAN}{Style.BRIGHT}📄 [{index}] {paper['title'][:80]}...{Style.RESET_ALL}")
        
        authors = paper.get('authors', [])
        if authors:
            authors_str = ", ".join(authors[:2])
            if len(authors) > 2:
                authors_str += " et al."
            print(f"   {Fore.BLUE}👥 {authors_str}{Style.RESET_ALL}")
        
        print(f"   {Fore.MAGENTA}📅 {paper.get('published', 'N/A')}{Style.RESET_ALL}")
        
        summary = paper.get('summary', '')[:150]
        if summary:
            print(f"   {Fore.WHITE}{Style.DIM}{summary}...{Style.RESET_ALL}")
        
        print(f"   {Fore.YELLOW}🔗 {paper.get('url', 'N/A')}{Style.RESET_ALL}")
        print()

    async def get_paper_details(self, index: int):
        """
        === FERRAMENTA MCP: DETALHES DO PAPER ===
        Chama "get_paper_details" no servidor
        """
        result = await self.call_tool("get_paper_details", {
            "paper_index": index
        })
        
        if result.get("success"):
            paper = result.get("paper", {})
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📚 Detalhes Completos do Paper{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
            
            print(f"{Fore.GREEN}Título:{Style.RESET_ALL} {paper.get('title', 'N/A')}\n")
            
            authors = paper.get('authors', [])
            if authors:
                print(f"{Fore.GREEN}Autores:{Style.RESET_ALL}")
                for author in authors:
                    print(f"  • {author}")
                print()
            
            print(f"{Fore.GREEN}Data de Publicação:{Style.RESET_ALL} {paper.get('published', 'N/A')}\n")
            
            categories = paper.get('categories', [])
            if categories:
                print(f"{Fore.GREEN}Categorias:{Style.RESET_ALL} {', '.join(categories)}\n")
            
            print(f"{Fore.GREEN}Resumo:{Style.RESET_ALL}")
            summary = paper.get('summary', 'N/A')
            words = summary.split()
            line = ""
            for word in words:
                if len(line) + len(word) > 80:
                    print(f"  {line}")
                    line = word
                else:
                    line += (" " if line else "") + word
            if line:
                print(f"  {line}")
            print()
            
            print(f"{Fore.GREEN}Links:{Style.RESET_ALL}")
            print(f"  • ArXiv: {paper.get('url', 'N/A')}")
            print(f"  • PDF: {paper.get('pdf_url', 'N/A')}")
        else:
            print(f"{Fore.RED}❌ {result.get('message')}{Style.RESET_ALL}")

    async def analyze_papers(self, analysis_type: str = "summary"):
        """
        === FERRAMENTA MCP: ANÁLISE COM IA ===
        Usa IA (Gemini) para analisar papers via MCP Server
        """
        print(f"\n{Fore.YELLOW}🤖 Analisando papers ({analysis_type})...{Style.RESET_ALL}\n")
        
        result = await self.call_tool("analyze_papers", {
            "analysis_type": analysis_type
        })
        
        if result.get("success"):
            print(f"{Fore.GREEN}✅ Análise Completa:{Style.RESET_ALL}\n")
            print(f"{Fore.CYAN}Tipo: {result.get('analysis_type')}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Papers analisados: {result.get('papers_analyzed')}{Style.RESET_ALL}\n")
            
            analysis = result.get('analysis', '')
            lines = analysis.split('\n')
            for line in lines:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"{Fore.RED}❌ {result.get('message')}{Style.RESET_ALL}")

    async def chat_about_papers(self, message: str):
        """
        === FERRAMENTA MCP: CHAT INTERATIVO ===
        Conversa sobre papers usando IA via MCP
        """
        print(f"\n{Fore.YELLOW}💬 Processando pergunta...{Style.RESET_ALL}\n")
        
        result = await self.call_tool("chat_about_papers", {
            "message": message
        })
        
        if result.get("success"):
            print(f"{Fore.GREEN}🤖 Resposta:{Style.RESET_ALL}\n")
            response = result.get('response', '')
            
            lines = response.split('\n')
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            
            if result.get('papers_in_context'):
                print(f"\n  {Fore.CYAN}(Papers no contexto: {result.get('papers_in_context')}){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ {result.get('message')}{Style.RESET_ALL}")

    async def get_cache_info(self):
        """
        === FERRAMENTA MCP: INFORMAÇÕES DO CACHE ===
        Obtém estatísticas dos papers armazenados no servidor
        """
        result = await self.call_tool("get_cache_info", {})
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 Informações do Cache{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*40}{Style.RESET_ALL}\n")
        
        if result.get("success"):
            cached = result.get('cached_papers', 0)
            
            if cached > 0:
                print(f"{Fore.GREEN}Papers em cache: {cached}{Style.RESET_ALL}\n")
                
                titles = result.get('paper_titles', [])
                if titles:
                    print(f"{Fore.YELLOW}Títulos:{Style.RESET_ALL}")
                    for i, title in enumerate(titles[:5], 1):
                        print(f"  {i}. {title[:60]}...")
                    if len(titles) > 5:
                        print(f"  ... e mais {len(titles)-5} papers")
                    print()
                
                categories = result.get('categories', [])
                if categories:
                    print(f"{Fore.YELLOW}Categorias:{Style.RESET_ALL} {', '.join(categories[:5])}")
                
                years = result.get('publication_years', [])
                if years:
                    print(f"{Fore.YELLOW}Anos de publicação:{Style.RESET_ALL} {', '.join(sorted(years))}")
                
                total_authors = result.get('total_authors', 0)
                if total_authors:
                    print(f"{Fore.YELLOW}Total de autores:{Style.RESET_ALL} {total_authors}")
            else:
                print(f"{Fore.YELLOW}Cache vazio{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Erro ao obter informações do cache{Style.RESET_ALL}")

    async def clear_cache(self):
        """
        === FERRAMENTA MCP: LIMPAR CACHE ===
        Remove todos os papers da memória do servidor
        """
        result = await self.call_tool("clear_cache", {})
        
        if result.get("success"):
            print(f"{Fore.GREEN}✅ {result.get('message')}{Style.RESET_ALL}")
            self.last_results = []
        else:
            print(f"{Fore.RED}❌ Erro ao limpar cache{Style.RESET_ALL}")

    def show_menu(self):
        """Exibe menu de opções para o usuário"""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📋 Menu de Opções{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*40}{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}1{Style.RESET_ALL} - Buscar papers")
        print(f"  {Fore.GREEN}2{Style.RESET_ALL} - Ver detalhes de um paper")
        print(f"  {Fore.GREEN}3{Style.RESET_ALL} - Analisar papers (resumo)")
        print(f"  {Fore.GREEN}4{Style.RESET_ALL} - Analisar papers (tendências)")
        print(f"  {Fore.GREEN}5{Style.RESET_ALL} - Analisar papers (comparação)")
        print(f"  {Fore.GREEN}6{Style.RESET_ALL} - Chat sobre papers")
        print(f"  {Fore.GREEN}7{Style.RESET_ALL} - Informações do cache")
        print(f"  {Fore.GREEN}8{Style.RESET_ALL} - Limpar cache")
        print(f"  {Fore.GREEN}9{Style.RESET_ALL} - Ajuda")
        print(f"  {Fore.RED}0{Style.RESET_ALL} - Sair")
        print(f"{Fore.CYAN}{'='*40}{Style.RESET_ALL}")

    async def run_interactive(self):
        """
        === LOOP PRINCIPAL DO HOST MCP ===
        
        Esta função mantém o host ativo e processando comandos do usuário.
        
        FLUXO:
        1. Conectar ao MCP Server
        2. Loop infinito aguardando comandos
        3. Para cada comando, chamar a ferramenta apropriada
        4. Ao sair, desconectar corretamente
        """
        try:
            # === CONECTAR AO SERVIDOR MCP ===
            if not await self.connect():
                return
            
            print(f"\n{Fore.GREEN}✨ Cliente pronto! Use o menu para interagir.{Style.RESET_ALL}")
            
            # === LOOP DE INTERAÇÃO ===
            while True:
                self.show_menu()
                
                try:
                    choice = input(f"\n{Fore.YELLOW}Escolha uma opção: {Style.RESET_ALL}").strip()
                    
                    if choice == "0":
                        print(f"\n{Fore.CYAN}👋 Encerrando cliente...{Style.RESET_ALL}")
                        break
                    
                    elif choice == "1":
                        query = input(f"{Fore.YELLOW}Digite os termos de busca: {Style.RESET_ALL}").strip()
                        if query:
                            max_results = input(f"{Fore.YELLOW}Número de resultados (1-10, padrão 5): {Style.RESET_ALL}").strip()
                            max_results = int(max_results) if max_results.isdigit() else 5
                            await self.search_papers(query, max_results)
                    
                    elif choice == "2":
                        if self.last_results:
                            index = input(f"{Fore.YELLOW}Digite o número do paper (1-{len(self.last_results)}): {Style.RESET_ALL}").strip()
                            if index.isdigit():
                                index = int(index) - 1
                                if 0 <= index < len(self.last_results):
                                    await self.get_paper_details(index)
                                else:
                                    print(f"{Fore.RED}Índice inválido{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.YELLOW}Faça uma busca primeiro{Style.RESET_ALL}")
                    
                    elif choice == "3":
                        await self.analyze_papers("summary")
                    
                    elif choice == "4":
                        await self.analyze_papers("trends")
                    
                    elif choice == "5":
                        await self.analyze_papers("comparison")
                    
                    elif choice == "6":
                        message = input(f"{Fore.YELLOW}Digite sua pergunta: {Style.RESET_ALL}").strip()
                        if message:
                            await self.chat_about_papers(message)
                    
                    elif choice == "7":
                        await self.get_cache_info()
                    
                    elif choice == "8":
                        confirm = input(f"{Fore.YELLOW}Confirma limpar cache? (s/n): {Style.RESET_ALL}").strip().lower()
                        if confirm == 's':
                            await self.clear_cache()
                    
                    elif choice == "9":
                        self.show_help()
                    
                    else:
                        print(f"{Fore.RED}Opção inválida{Style.RESET_ALL}")
                    
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}Operação cancelada{Style.RESET_ALL}")
                    continue
                except Exception as e:
                    print(f"{Fore.RED}Erro: {str(e)}{Style.RESET_ALL}")
                    logger.error(f"Erro no menu: {str(e)}")
            
        except Exception as e:
            print(f"{Fore.RED}Erro fatal: {str(e)}{Style.RESET_ALL}")
            logger.error(f"Erro fatal: {str(e)}")
        finally:
            # === DESCONECTAR DO SERVIDOR MCP ===
            # É importante fechar a conexão corretamente
            if self.session:
                try:
                    await self.session.__aexit__(None, None, None)
                    print(f"{Fore.GREEN}Desconectado do servidor{Style.RESET_ALL}")
                except:
                    pass

            if self.stdio_context:
                try:
                    await self.stdio_context.__aexit__(None, None, None)
                except:
                    pass

    def show_help(self):
        """Exibe ajuda detalhada sobre o sistema"""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}❓ Ajuda - Cliente MCP Papers{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
        
        help_text = """
Este cliente permite interagir com o servidor MCP de papers acadêmicos.

FUNCIONALIDADES:
• Buscar papers: Pesquisa papers no ArXiv por palavras-chave
• Ver detalhes: Mostra informações completas de um paper
• Análise com IA: Usa Gemini para analisar papers
  - Resumo: Visão geral dos papers
  - Tendências: Identifica padrões emergentes
  - Comparação: Compara metodologias e resultados
• Chat: Faça perguntas sobre os papers
• Cache: Mantém papers em memória para análise

DICAS:
• Faça buscas específicas para melhores resultados
• Use análise de tendências para identificar áreas promissoras
• O chat entende contexto - faça perguntas detalhadas
• O cache persiste entre operações até ser limpo

EXEMPLOS DE BUSCA:
• "machine learning"
• "neural networks attention"
• "quantum computing applications"
• "climate change modeling"
        """
        
        for line in help_text.split('\n'):
            if line.strip():
                if line.startswith('•'):
                    print(f"  {Fore.GREEN}{line}{Style.RESET_ALL}")
                elif line.isupper() and ':' in line:
                    print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
                else:
                    print(f"  {line}")

async def main():
    """
    === PONTO DE ENTRADA DO PROGRAMA ===
    
    Cria e inicia o MCP Host (cliente de papers).
    
    RESUMO DO FLUXO COMPLETO:
    1. main() cria PapersClient (MCP Host)
    2. Host se conecta ao MCP Server
    3. Host descobre ferramentas disponíveis
    4. Usuário interage via menu
    5. Cada ação chama uma ferramenta MCP
    6. Server processa e retorna resultado
    7. Host exibe para o usuário
    """
    print(f"{Fore.CYAN}{Style.BRIGHT}")
    print("╔═══════════════════════════════════════╗")
    print("║   Cliente MCP - Papers Acadêmicos     ║")
    print("║         Versão 1.0.0                  ║")
    print("╚═══════════════════════════════════════╝")
    print(f"{Style.RESET_ALL}")
    
    client = PapersClient()
    await client.run_interactive()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}👋 Programa encerrado{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Erro: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

"""
=== RESUMO DA ARQUITETURA MCP ===

┌─────────────────────────────────────┐
│  MCP HOST (esta aplicação)          │
│  ┌─────────────────────────────┐    │
│  │ MCP Client 1                │    │
│  │ (interno)                   │    │
│  └──────────┬──────────────────┘    │
│             │ One-to-one             │
└─────────────┼────────────────────────┘
              │
              ▼
    ┌─────────────────────┐
    │  MCP Server         │
    │  (Papers Server)    │
    │                     │
    │  Tools:             │
    │  • search_papers    │
    │  • get_details      │
    │  • analyze_papers   │
    │  • chat             │
    │  • cache_info       │
    │  • clear_cache      │
    └─────────────────────┘

FLUXO DE UMA REQUISIÇÃO:
1. Usuário escolhe opção no menu
2. Host chama call_tool()
3. Client envia requisição MCP ao Server
4. Server processa (busca ArXiv, usa IA, etc)
5. Server retorna resposta em formato MCP
6. Client recebe e decodifica
7. Host processa e exibe para usuário

VANTAGENS DO MCP:
• Separação clara de responsabilidades
• Protocolo padrão de comunicação
• Fácil adicionar novos servers
• Servidor pode ser reutilizado por outros hosts
• Modular e escalável
"""
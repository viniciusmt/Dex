from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
import os
import uvicorn
import sys
import json
import anthropic
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
from dotenv import load_dotenv
from fastapi.openapi.utils import get_openapi

load_dotenv()

# Configuração de caminho
current_dir = os.path.dirname(os.path.abspath(__file__))
agents_dir = os.path.join(current_dir, "agents")
if agents_dir not in sys.path:
    sys.path.append(agents_dir)
print(f"Adicionado ao sys.path: {agents_dir}", file=sys.stderr)

# Importação dos módulos
try:
    from agents import analytics
    from agents import search_console
    from agents import youtube
    from agents import drive
    from agents import trello
except ImportError as e:
    print(f"Erro ao importar módulos: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("AVISO: Chave API do Claude não encontrada!", file=sys.stderr)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI(title="Analytics Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp = FastMCP("analytics-agent")

@app.get("/")
async def root():
    return {"message": "API de Analytics com Claude e MCP está funcionando!"}

class NaturalLanguageQuery(BaseModel):
    pergunta: str
    contexto: Optional[str] = None

class ListarContasGA4Request(BaseModel):
    """Classe para requisição de listagem de contas GA4"""
    pass
    
class GA4Query(BaseModel):
    dimensao: str = "country"
    metrica: str = "sessions"
    periodo: str = "7daysAgo"
    data_fim: str = "today"  # Nova variável para data final
    filtro_campo: str = ""
    filtro_valor: str = ""
    filtro_condicao: str = Field(
        default="igual",
        description="Condição do filtro: igual, contem, começa com, termina com, regex, regex completa"
    )
    property_id: str = Field(
        default="properties/254018746",
        description="ID da propriedade GA4 no formato 'properties/XXXXXX'"
    )

class GA4PivotQuery(BaseModel):
    dimensao: str = "country"
    dimensao_pivot: str = "deviceCategory"
    metrica: str = "sessions"
    periodo: str = "7daysAgo"
    data_fim: str = "today"  # Nova variável para data final
    filtro_campo: str = ""
    filtro_valor: str = ""
    filtro_condicao: str = Field(
        default="igual",
        description="Condição do filtro: igual, contem, começa com, termina com, regex, regex completa"
    )
    limite_linhas: int = 100
    property_id: str = Field(
        default="properties/254018746",
        description="ID da propriedade GA4 no formato 'properties/XXXXXX'"
    )

# Novas classes para Search Console
class SearchConsoleListarSitesRequest(BaseModel):
    """Classe para requisição de listagem de sites Search Console"""
    pass

class SearchConsoleQuery(BaseModel):
    site_url: str = Field(description="URL do site a ser analisado (obrigatório)")
    data_inicio: str = "30daysAgo"
    data_fim: str = "today"
    dimensoes: List[str] = ["query"]
    metrica_extra: bool = True
    filtros: Optional[List[Dict[str, Any]]] = None
    limite: int = 100
    query_filtro: str = Field(default="", description="Filtro específico para queries - usa condição 'contém' automaticamente")
    pagina_filtro: str = Field(default="", description="Filtro específico para páginas - usa condição 'contém' automaticamente")

class SearchConsoleVerificarSiteRequest(BaseModel):
    site_url: str = Field(description="URL do site para verificar")

class YouTubeQuery(BaseModel):
    pergunta: str

# 1. CORRIGIR MODELOS PYDANTIC

class CriarPlanilhaRequest(BaseModel):
    nome_planilha: str  # MUDANÇA: titulo → nome_planilha
    # REMOVER: dados_iniciais não é usado pela função criar_planilha

class ListarPlanilhasRequest(BaseModel):
    limite: int = 20  # ADICIONAR: parâmetro que a função aceita

class CriarAbaRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    linhas: int = 100      # ADICIONAR: parâmetros opcionais da função
    colunas: int = 20      # ADICIONAR: parâmetros opcionais da função

class SobrescreverSheetRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    dados: List[List[Any]]
    # Esta está correta

class AdicionarCelulasRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    dados: List[List[Any]]
    # REMOVER: inicio - a função não aceita este parâmetro

# Classes para operações do Trello
class TrelloListarQuadrosRequest(BaseModel):
    pass

class TrelloListarListasRequest(BaseModel):
    board_id: str

class TrelloListarCartoesRequest(BaseModel):
    list_id: str

class TrelloCriarCartaoRequest(BaseModel):
    list_id: str
    nome: str
    descricao: str = ""

class TrelloMoverCartaoRequest(BaseModel):
    card_id: str
    list_id: str

class TrelloListarTarefasQuadroRequest(BaseModel):
    board_id: str

# Registrar ferramentas MCP
@mcp.tool()
def listar_sites_search_console() -> dict:
    """
    Lista todos os sites disponíveis no Search Console para a conta de serviço.
    
    Returns:
        dict: Lista de sites disponíveis no Search Console
    """
    try:
        return search_console.listar_sites_search_console()
    except Exception as e:
        return {"erro": f"Erro ao listar sites do Search Console: {str(e)}"}

@mcp.tool()
def consulta_search_console_custom(
    site_url: str,
    data_inicio: str = "30daysAgo",
    data_fim: str = "today",
    dimensoes: list[str] = ["query"],
    metrica_extra: bool = True,
    filtros: list[dict] = None,
    limite: int = 100,
    query_filtro: str = "",
    pagina_filtro: str = ""
) -> dict:
    """
    Consulta customizada ao Search Console com suporte a múltiplas dimensões e filtros.
    
    Args:
        site_url: URL do site a ser analisado (obrigatório)
        data_inicio: Data de início (padrão: "30daysAgo")
        data_fim: Data de fim (padrão: "today") 
        dimensoes: Lista de dimensões para análise (padrão: ["query"])
        metrica_extra: Se deve incluir métricas extras como CTR e posição (padrão: True)
        filtros: Lista de filtros customizados no formato [{"dimension": "query", "operator": "contains", "expression": "termo"}]
        limite: Número máximo de resultados (padrão: 100)
        query_filtro: Filtro específico para queries - usa condição 'contém' automaticamente (opcional)
        pagina_filtro: Filtro específico para páginas - usa condição 'contém' automaticamente (opcional)
        
    Returns:
        dict: Dados da consulta Search Console
    """
    try:
        return search_console.consulta_search_console_custom(
            site_url=site_url,
            data_inicio=data_inicio,
            data_fim=data_fim,
            dimensoes=dimensoes,
            metrica_extra=metrica_extra,
            filtros=filtros,
            limite=limite,
            query_filtro=query_filtro,
            pagina_filtro=pagina_filtro
        )
    except Exception as e:
        return {"erro": f"Erro na consulta_search_console_custom: {str(e)}"}

@mcp.tool()
def verificar_propriedade_site_search_console(site_url: str) -> dict:
    """
    Verifica se um site específico está disponível no Search Console.
    
    Args:
        site_url: URL do site para verificar
        
    Returns:
        dict: Informações sobre a disponibilidade do site no Search Console
    """
    try:
        return search_console.verificar_propriedade_site_search_console(site_url)
    except Exception as e:
        return {"erro": f"Erro ao verificar propriedade do site: {str(e)}"}

@mcp.tool()
def listar_contas_ga4() -> dict:
    """
    Lista todas as contas do Google Analytics 4 e suas propriedades associadas.
    
    Returns:
        dict: Informações sobre contas e propriedades
    """
    try:
        return analytics.listar_contas_ga4()
    except Exception as e:
        return {"erro": f"Erro ao listar contas GA4: {str(e)}"}

@mcp.tool()
def consulta_ga4(
    dimensao: str = "country",
    metrica: str = "sessions",
    periodo: str = "7daysAgo",
    data_fim: str = "today",
    filtro_campo: str = "",
    filtro_valor: str = "",
    filtro_condicao: str = "igual",
    property_id: str = "properties/254018746"
) -> dict:
    """
    Consulta dados do Google Analytics 4.
    
    Args:
        dimensao: Dimensões para análise (ex: 'country', 'city')
        metrica: Métricas para análise (ex: 'sessions', 'users')
        periodo: Data de início (ex: '7daysAgo', '2024-01-01')
        data_fim: Data de fim (ex: 'today', '2024-12-31')
        filtro_campo: Campo para filtro
        filtro_valor: Valor do filtro
        filtro_condicao: Condição do filtro
        property_id: ID da propriedade GA4
        
    Returns:
        dict: Resultado da consulta GA4
    """
    try:
        return analytics.consulta_ga4(
            dimensao=dimensao,
            metrica=metrica,
            periodo=periodo,
            data_fim=data_fim,
            filtro_campo=filtro_campo,
            filtro_valor=filtro_valor,
            filtro_condicao=filtro_condicao,
            property_id=property_id
        )
    except Exception as e:
        return {"erro": f"Erro na consulta GA4: {str(e)}"}

@mcp.tool()
def consulta_ga4_pivot(
    dimensao: str = "country",
    dimensao_pivot: str = "deviceCategory",
    metrica: str = "sessions",
    periodo: str = "7daysAgo",
    data_fim: str = "today",
    filtro_campo: str = "",
    filtro_valor: str = "",
    filtro_condicao: str = "igual",
    limite_linhas: int = 100,
    property_id: str = "properties/254018746"
) -> dict:
    """
    Consulta GA4 com tabela pivot para análise cruzada de dimensões.
    
    Args:
        dimensao: Dimensão principal
        dimensao_pivot: Dimensão para cruzamento (pivot)
        metrica: Métrica para análise
        periodo: Data de início (ex: '7daysAgo', '2024-01-01')
        data_fim: Data de fim (ex: 'today', '2024-12-31')
        filtro_campo: Campo para filtro
        filtro_valor: Valor do filtro
        filtro_condicao: Condição do filtro
        limite_linhas: Limite de linhas no resultado
        property_id: ID da propriedade GA4
        
    Returns:
        dict: Resultado da consulta GA4 Pivot
    """
    try:
        return analytics.consulta_ga4_pivot(
            dimensao=dimensao,
            dimensao_pivot=dimensao_pivot,
            metrica=metrica,
            periodo=periodo,
            data_fim=data_fim,
            filtro_campo=filtro_campo,
            filtro_valor=filtro_valor,
            filtro_condicao=filtro_condicao,
            limite_linhas=limite_linhas,
            property_id=property_id
        )
    except Exception as e:
        return {"erro": f"Erro na consulta GA4 Pivot: {str(e)}"}

@mcp.tool()
def analise_youtube(pergunta: str) -> dict:
    """
    Analisa comentários do YouTube sobre um tópico específico.
    
    Args:
        pergunta: Pergunta ou tópico a ser analisado
        
    Returns:
        dict: Análise dos comentários do YouTube
    """
    try:
        return youtube.youtube_analyzer(pergunta)
    except Exception as e:
        return {"erro": f"Erro na analise_youtube: {str(e)}"}

@mcp.tool()
def criar_planilha(nome_planilha: str) -> dict:  # MUDANÇA: titulo → nome_planilha, remover dados_iniciais
    """
    Cria uma nova planilha no Google Drive e a compartilha com vinicius.matsumoto@fgv.br
    
    Args:
        nome_planilha: Nome da planilha a ser criada
    """
    try:
        return drive.criar_planilha(nome_planilha)  # MUDANÇA: passar apenas nome_planilha
    except Exception as e:
        return {"erro": f"Erro ao criar planilha: {str(e)}"}

@mcp.tool()
def listar_planilhas(limite: int = 20) -> dict:  # ADICIONAR: parâmetro limite
    """
    Lista todas as planilhas que a conta de serviço tem acesso.
    
    Args:
        limite: Número máximo de planilhas a listar (padrão: 20)
    """
    try:
        return drive.listar_planilhas(limite)  # MUDANÇA: passar parâmetro limite
    except Exception as e:
        return {"erro": f"Erro ao listar planilhas: {str(e)}"}

@mcp.tool()
def criar_aba(planilha_id: str, nome_aba: str, linhas: int = 100, colunas: int = 20) -> dict:  # ADICIONAR: parâmetros opcionais
    """
    Cria uma nova aba em uma planilha existente.
    
    Args:
        planilha_id: ID da planilha
        nome_aba: Nome da nova aba
        linhas: Número de linhas na nova aba (padrão: 100)
        colunas: Número de colunas na nova aba (padrão: 20)
    """
    try:
        return drive.criar_nova_aba(planilha_id, nome_aba, linhas, colunas)  # MUDANÇA: passar todos os parâmetros
    except Exception as e:
        return {"erro": f"Erro ao criar aba: {str(e)}"}

@mcp.tool()
def sobrescrever_sheet(planilha_id: str, nome_aba: str, dados: list) -> dict:
    """
    Sobrescreve os dados de uma aba específica.
    
    Args:
        planilha_id: ID da planilha
        nome_aba: Nome da aba a ser sobrescrita
        dados: Lista de dados (lista de listas)
    """
    try:
        return drive.sobrescrever_aba(planilha_id, nome_aba, dados)
    except Exception as e:
        return {"erro": f"Erro ao sobrescrever sheet: {str(e)}"}

@mcp.tool()
def adicionar_celulas(planilha_id: str, nome_aba: str, dados: list) -> dict:  # REMOVER: parâmetro inicio
    """
    Adiciona dados em células específicas sem sobrescrever outras áreas.
    
    Args:
        planilha_id: ID da planilha
        nome_aba: Nome da aba
        dados: Lista de dados (lista de listas)
    """
    try:
        return drive.adicionar_celulas(planilha_id, nome_aba, dados)  # REMOVER: parâmetro inicio
    except Exception as e:
        return {"erro": f"Erro ao adicionar células: {str(e)}"}

# 3. CORRIGIR ENDPOINTS DA API

@app.post("/api/drive/criar_planilha")
async def api_criar_planilha(query: CriarPlanilhaRequest):
    try:
        result = drive.criar_planilha(query.nome_planilha)  # MUDANÇA: passar apenas nome_planilha
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drive/listar_planilhas")
async def api_listar_planilhas(limite: int = 20):  # ADICIONAR: parâmetro limite
    try:
        result = drive.listar_planilhas(limite)  # MUDANÇA: passar parâmetro limite
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/criar_aba")
async def api_criar_aba(query: CriarAbaRequest):
    try:
        result = drive.criar_nova_aba(query.planilha_id, query.nome_aba, query.linhas, query.colunas)  # MUDANÇA: passar todos os parâmetros
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/sobrescrever_sheet")
async def api_sobrescrever_sheet(query: SobrescreverSheetRequest):
    try:
        result = drive.sobrescrever_aba(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/adicionar_celulas")
async def api_adicionar_celulas(query: AdicionarCelulasRequest):
    try:
        result = drive.adicionar_celulas(query.planilha_id, query.nome_aba, query.dados)  # REMOVER: parâmetro inicio
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Ferramentas para Trello
@mcp.tool()
def trello_listar_quadros() -> dict:
    """
    Lista todos os quadros do Trello do usuário.
    
    Returns:
        dict: Informações sobre quadros disponíveis
    """
    try:
        return trello.listar_quadros()
    except Exception as e:
        return {"erro": f"Erro ao listar quadros do Trello: {str(e)}"}

@mcp.tool()
def trello_listar_listas(board_id: str) -> dict:
    """
    Lista todas as listas (colunas) de um quadro do Trello.
    
    Args:
        board_id: ID do quadro do Trello
        
    Returns:
        dict: Informações sobre as listas do quadro
    """
    try:
        return trello.listar_listas(board_id)
    except Exception as e:
        return {"erro": f"Erro ao listar listas do Trello: {str(e)}"}

@mcp.tool()
def trello_listar_cartoes(list_id: str) -> dict:
    """
    Lista todos os cartões (tarefas) de uma lista do Trello.
    
    Args:
        list_id: ID da lista do Trello
        
    Returns:
        dict: Informações sobre os cartões da lista
    """
    try:
        return trello.listar_cartoes(list_id)
    except Exception as e:
        return {"erro": f"Erro ao listar cartões do Trello: {str(e)}"}

@mcp.tool()
def trello_criar_cartao(list_id: str, nome: str, descricao: str = "") -> dict:
    """
    Cria um novo cartão (tarefa) em uma lista do Trello.
    
    Args:
        list_id: ID da lista onde o cartão será criado
        nome: Nome do cartão/tarefa
        descricao: Descrição do cartão (opcional)
        
    Returns:
        dict: Informações sobre o cartão criado
    """
    try:
        return trello.criar_cartao(list_id, nome, descricao)
    except Exception as e:
        return {"erro": f"Erro ao criar cartão do Trello: {str(e)}"}

@mcp.tool()
def trello_mover_cartao(card_id: str, list_id: str) -> dict:
    """
    Move um cartão (tarefa) para outra lista no Trello.
    
    Args:
        card_id: ID do cartão a ser movido
        list_id: ID da lista de destino
        
    Returns:
        dict: Informações sobre o resultado da operação
    """
    try:
        return trello.mover_cartao(card_id, list_id)
    except Exception as e:
        return {"erro": f"Erro ao mover cartão do Trello: {str(e)}"}

@mcp.tool()
def trello_listar_tarefas_quadro(board_id: str) -> dict:
    """
    Lista todas as tarefas de um quadro do Trello organizadas por lista.
    
    Args:
        board_id: ID do quadro do Trello
        
    Returns:
        dict: Todas as tarefas organizadas por lista
    """
    try:
        return trello.listar_tarefas_quadro(board_id)
    except Exception as e:
        return {"erro": f"Erro ao listar tarefas do quadro Trello: {str(e)}"}

@app.post("/perguntar")
async def perguntar(query: NaturalLanguageQuery):
    try:
        if not ANTHROPIC_API_KEY:
            raise HTTPException(status_code=500, detail="Chave API do Claude não configurada")

        system_prompt = (
            "Você é um assistente de analytics. Seu trabalho é transformar perguntas em linguagem natural "
            "em objetos JSON válidos com o formato especificado. Responda SOMENTE com JSON puro. "
            "Sem explicações. Sem formatação Markdown. Sem prefixos ou sufixos. Apenas JSON."
        )

        user_prompt = f"""
Pergunta: {query.pergunta}

Retorne um JSON neste formato:

{{
  "tipo_consulta": "ga4" ou "ga4_pivot" ou "search_console" ou "search_console_listar_sites" ou "search_console_verificar_site" ou "youtube" ou "drive_criar_planilha" ou "drive_listar_planilhas" ou "drive_criar_aba" ou "drive_sobrescrever_aba" ou "drive_adicionar_celulas" ou "listar_contas_ga4" ou "trello_listar_quadros" ou "trello_listar_listas" ou "trello_listar_cartoes" ou "trello_criar_cartao" ou "trello_mover_cartao" ou "trello_listar_tarefas_quadro",
  "parametros": {{}}
}}

Para filtros GA4, use a condição "contem" (sem acento) para buscas parciais.
Para Search Console, o site_url é obrigatório nas consultas.

Apenas o JSON. Nenhuma explicação.
"""

        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}]
        )

        content = response.content[0].text.strip()
        if "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed_response = json.loads(content)
        tipo_consulta = parsed_response.get("tipo_consulta")
        parametros = parsed_response.get("parametros", {})
        
        # Correção para garantir que "contem" esteja no formato correto
        if "filtro_condicao" in parametros and parametros["filtro_condicao"] in ["contém", "contains", "contém"]:
            parametros["filtro_condicao"] = "contem"
            print(f"DIAGNÓSTICO: Convertendo condição de filtro para 'contem'", file=sys.stderr)

        # Determina qual função chamar com base no tipo de consulta
        if tipo_consulta == "ga4":
            resultado = analytics.consulta_ga4(**parametros)
        elif tipo_consulta == "ga4_pivot":
            resultado = analytics.consulta_ga4_pivot(**parametros)
        elif tipo_consulta == "search_console":
            resultado = search_console.consulta_search_console_custom(**parametros)
        elif tipo_consulta == "search_console_listar_sites":
            resultado = search_console.listar_sites_search_console()
        elif tipo_consulta == "search_console_verificar_site":
            resultado = search_console.verificar_propriedade_site_search_console(**parametros)
        elif tipo_consulta == "youtube":
            resultado = youtube.youtube_analyzer(parametros.get("pergunta", query.pergunta))
        elif tipo_consulta == "listar_contas_ga4":
            resultado = analytics.listar_contas_ga4()
        # Operações de Drive
        elif tipo_consulta == "drive_criar_planilha":
            resultado = drive.criar_planilha(**parametros)
        elif tipo_consulta == "drive_listar_planilhas":
            resultado = drive.listar_planilhas()
        elif tipo_consulta == "drive_criar_aba":
            resultado = drive.criar_nova_aba(**parametros)
        elif tipo_consulta == "drive_sobrescrever_aba":
            resultado = drive.sobrescrever_aba(**parametros)
        elif tipo_consulta == "drive_adicionar_celulas":
            resultado = drive.adicionar_celulas(**parametros)
        # Operações do Trello
        elif tipo_consulta == "trello_listar_quadros":
            resultado = trello.listar_quadros()
        elif tipo_consulta == "trello_listar_listas":
            resultado = trello.listar_listas(**parametros)
        elif tipo_consulta == "trello_listar_cartoes":
            resultado = trello.listar_cartoes(**parametros)
        elif tipo_consulta == "trello_criar_cartao":
            resultado = trello.criar_cartao(**parametros)
        elif tipo_consulta == "trello_mover_cartao":
            resultado = trello.mover_cartao(**parametros)
        elif tipo_consulta == "trello_listar_tarefas_quadro":
            resultado = trello.listar_tarefas_quadro(**parametros)
        else:
            raise HTTPException(status_code=400, detail="Tipo de consulta não reconhecido")

        interpretacao_response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1500,
            temperature=0.2,
            system="Você é um assistente de analytics. Interprete resultados com base na pergunta original e forneça uma explicação clara.",
            messages=[{"role": "user", "content": [{"type": "text", "text": f"Pergunta: {query.pergunta}\n\nResultados:\n{json.dumps(resultado, ensure_ascii=False, indent=2)}"}]}]
        )

        return {
            "pergunta": query.pergunta,
            "tipo_consulta": tipo_consulta,
            "parametros": parametros,
            "resultado_bruto": resultado,
            "interpretacao": interpretacao_response.content[0].text.strip()
        }

    except Exception as e:
        print(f"[Erro geral] {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {str(e)}")

@app.get("/api/listar_contas_ga4")
async def api_listar_contas_ga4():
    """
    Lista todas as contas do Google Analytics 4 e suas propriedades associadas.
    
    Returns:
        dict: Informações sobre contas e propriedades GA4
    """
    try:
        result = analytics.listar_contas_ga4()
        return {"result": result}
    except Exception as e:
        print(f"Erro ao listar contas GA4: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Erro ao listar contas GA4: {str(e)}")

@app.post("/api/consulta_ga4")
async def api_consulta_ga4(query: GA4Query):
    """
    Consulta dados do Google Analytics 4.
    
    Returns:
        dict: Resultado da consulta GA4
    """
    try:
        # Garantir que "contem" esteja no formato correto
        if query.filtro_condicao in ["contém", "contains", "contém"]:
            query.filtro_condicao = "contem"
            print(f"DIAGNÓSTICO API GA4: Convertendo condição de filtro para 'contem'", file=sys.stderr)
        
        result = analytics.consulta_ga4(**query.dict())
        return {"result": result}
    except Exception as e:
        print(f"Erro na consulta GA4: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Erro na consulta GA4: {str(e)}")

@app.post("/api/consulta_ga4_pivot")
async def api_consulta_ga4_pivot(query: GA4PivotQuery):
    try:
        # Garantir que "contem" esteja no formato correto
        if query.filtro_condicao in ["contém", "contains", "contém"]:
            query.filtro_condicao = "contem"
            print(f"DIAGNÓSTICO API PIVOT: Convertendo condição de filtro para 'contem'", file=sys.stderr)
        
        result = analytics.consulta_ga4_pivot(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Novos endpoints para Search Console
@app.get("/api/search_console/listar_sites")
async def api_listar_sites_search_console():
    """
    Lista todos os sites disponíveis no Search Console para a conta de serviço.
    
    Returns:
        dict: Lista de sites disponíveis no Search Console
    """
    try:
        result = search_console.listar_sites_search_console()
        return {"result": result}
    except Exception as e:
        print(f"Erro ao listar sites Search Console: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Erro ao listar sites Search Console: {str(e)}")

@app.post("/api/search_console/consulta_custom")
async def api_consulta_search_console_custom(query: SearchConsoleQuery):
    """
    Consulta customizada ao Search Console com suporte a múltiplas dimensões e filtros.
    
    Returns:
        dict: Dados da consulta Search Console
    """
    try:
        result = search_console.consulta_search_console_custom(**query.dict())
        return {"result": result}
    except Exception as e:
        print(f"Erro na consulta Search Console: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Erro na consulta Search Console: {str(e)}")

@app.post("/api/search_console/verificar_site")
async def api_verificar_propriedade_site_search_console(query: SearchConsoleVerificarSiteRequest):
    """
    Verifica se um site específico está disponível no Search Console.
    
    Returns:
        dict: Informações sobre a disponibilidade do site no Search Console
    """
    try:
        result = search_console.verificar_propriedade_site_search_console(**query.dict())
        return {"result": result}
    except Exception as e:
        print(f"Erro ao verificar propriedade do site: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Erro ao verificar propriedade do site: {str(e)}")

@app.post("/api/consulta_search_console")
async def api_consulta_search_console(query: SearchConsoleQuery):
    """
    Endpoint mantido para compatibilidade - redireciona para consulta_custom
    """
    try:
        result = search_console.consulta_search_console_custom(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analise_youtube")
async def api_analise_youtube(query: YouTubeQuery):
    try:
        result = youtube.youtube_analyzer(query.pergunta)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints para as operações de Drive/Sheets
@app.post("/api/drive/criar_planilha")
async def api_criar_planilha(query: CriarPlanilhaRequest):
    try:
        result = drive.criar_planilha(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drive/listar_planilhas")
async def api_listar_planilhas():
    try:
        result = drive.listar_planilhas()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/criar_aba")
async def api_criar_aba(query: CriarAbaRequest):
    try:
        result = drive.criar_nova_aba(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/sobrescrever_sheet")
async def api_sobrescrever_sheet(query: SobrescreverSheetRequest):
    try:
        result = drive.sobrescrever_aba(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/adicionar_celulas")
async def api_adicionar_celulas(query: AdicionarCelulasRequest):
    try:
        result = drive.adicionar_celulas(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints para operações do Trello
@app.get("/api/trello/listar_quadros")
async def api_trello_listar_quadros():
    try:
        result = trello.listar_quadros()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trello/listar_listas")
async def api_trello_listar_listas(query: TrelloListarListasRequest):
    try:
        result = trello.listar_listas(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trello/listar_cartoes")
async def api_trello_listar_cartoes(query: TrelloListarCartoesRequest):
    try:
        result = trello.listar_cartoes(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trello/criar_cartao")
async def api_trello_criar_cartao(query: TrelloCriarCartaoRequest):
    try:
        result = trello.criar_cartao(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trello/mover_cartao")
async def api_trello_mover_cartao(query: TrelloMoverCartaoRequest):
    try:
        result = trello.mover_cartao(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trello/listar_tarefas_quadro")
async def api_trello_listar_tarefas_quadro(query: TrelloListarTarefasQuadroRequest):
    try:
        result = trello.listar_tarefas_quadro(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/routes")
async def list_routes():
    return {"routes": [{"path": r.path, "methods": list(r.methods)} for r in app.routes]}

@app.get("/debug/filter_test")
async def test_filter_conditions():
    """Endpoint para testar as condições de filtro do GA4"""
    condicoes = [
        "igual", "contem", "contém", "contains", 
        "começa com", "comeca com", "begins_with",
        "termina com", "ends_with", "regex"
    ]
    
    return {
        "condicoes_suportadas": condicoes,
        "nota": "Use 'contem' (sem acento) para consultas que contêm um valor parcial."
    }

@app.get("/debug/credentials")
async def debug_credentials():
    """
    Endpoint para depurar problemas de credenciais.
    Não mostra as credenciais completas, apenas informações de diagnóstico.
    """
    try:
        # Verifica se GOOGLE_CREDENTIALS existe
        google_creds = os.getenv("GOOGLE_CREDENTIALS")
        has_google_creds = google_creds is not None

        # Tenta analisar o JSON
        json_valid = False
        creds_info = {}
        if has_google_creds:
            try:
                creds_dict = json.loads(google_creds)
                json_valid = True
                
                # Extrai informações de diagnóstico (sem revelar dados sensíveis)
                if "type" in creds_dict:
                    creds_info["type"] = creds_dict["type"]
                if "project_id" in creds_dict:
                    creds_info["project_id"] = creds_dict["project_id"]
                if "client_email" in creds_dict:
                    creds_info["client_email"] = creds_dict["client_email"]
                if "private_key_id" in creds_dict:
                    creds_info["has_private_key_id"] = True
                if "private_key" in creds_dict:
                    creds_info["has_private_key"] = len(creds_dict["private_key"]) > 100
            except json.JSONDecodeError:
                json_valid = False
        
        # Verifica se YOUTUBE_API_KEY existe
        youtube_key = os.getenv("YOUTUBE_API_KEY")
        has_youtube_key = youtube_key is not None
        
        # Verifica se ANTHROPIC_API_KEY existe
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        has_claude_key = claude_key is not None

        # Verifica se TRELLO_API_KEY existe
        trello_key = os.getenv("TRELLO_API_KEY")
        has_trello_key = trello_key is not None

        # Verifica se TRELLO_TOKEN existe
        trello_token = os.getenv("TRELLO_TOKEN")
        has_trello_token = trello_token is not None

        # Retorna as informações de diagnóstico
        return {
            "environment": {
                "has_google_credentials": has_google_creds,
                "google_credentials_valid_json": json_valid,
                "google_credentials_info": creds_info,
                "has_youtube_api_key": has_youtube_key,
                "has_anthropic_api_key": has_claude_key,
                "has_trello_api_key": has_trello_key,
                "has_trello_token": has_trello_token
            }
        }
    except Exception as e:
        return {"error": str(e)}

def get_custom_openapi():
    """Personaliza a descrição OpenAPI."""
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title="Analytics Agent API",
        version="1.0.0",
        description="API para consultas em Analytics (GA4), Search Console, YouTube, Drive e Trello",
        routes=app.routes,
    )
    
    # Adiciona informações sobre o servidor
    openapi_schema["servers"] = [
        {"url": "https://dex-mcp-server-1212.onrender.com", "description": "Servidor Render"}
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

@app.get("/openapi.json")
def custom_openapi_route():
    """Rota para a especificação OpenAPI personalizada."""
    return get_custom_openapi()

# Rota adicional para compatibilidade com MCP
@app.get("/.well-known/openapi.json")
def mcp_openapi():
    """Rota para a especificação OpenAPI no formato exigido pelo MCP."""
    return get_custom_openapi()

# Sobrescreve a função openapi padrão do FastAPI
app.openapi = get_custom_openapi

# Tenta integrar o router do MCP, se disponível
try:
    if hasattr(mcp, 'router'):
        app.include_router(mcp.router, prefix="/mcp")
except Exception as e:
    print(f"Erro ao registrar router MCP: {e}", file=sys.stderr)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"Iniciando servidor na porta {port}", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=port)

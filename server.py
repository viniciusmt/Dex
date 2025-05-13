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

class GA4Query(BaseModel):
    dimensao: str = "country"
    metrica: str = "sessions"
    periodo: str = "7daysAgo"
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

class SearchConsoleQuery(BaseModel):
    data_inicio: str = "30daysAgo"
    data_fim: str = "today"
    dimensoes: List[str] = ["query"]
    metrica_extra: bool = True
    filtros: Optional[List[Dict[str, Any]]] = None
    limite: int = 60

class YouTubeQuery(BaseModel):
    pergunta: str

# Classes para as operações de Drive/Sheets
class CriarPlanilhaRequest(BaseModel):
    titulo: str
    dados_iniciais: Optional[List[List[Any]]] = None

class ListarPlanilhasRequest(BaseModel):
    pass

class CriarAbaRequest(BaseModel):
    planilha_id: str
    nome_aba: str

class SobrescreverSheetRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    dados: List[List[Any]]

class AdicionarCelulasRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    dados: List[List[Any]]
    inicio: str = "A1"

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
  "tipo_consulta": "ga4" ou "ga4_pivot" ou "search_console" ou "youtube" ou "drive_criar_planilha" ou "drive_listar_planilhas" ou "drive_criar_aba" ou "drive_sobrescrever_aba" ou "drive_adicionar_celulas" ou "listar_contas_ga4" ou "trello_listar_quadros" ou "trello_listar_listas" ou "trello_listar_cartoes" ou "trello_criar_cartao" ou "trello_mover_cartao" ou "trello_listar_tarefas_quadro",
  "parametros": {{}}
}}

Para filtros GA4, use a condição "contem" (sem acento) para buscas parciais.

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

@app.get("/listar-contas-ga4")
async def api_listar_contas_ga4():
    try:
        result = analytics.listar_contas_ga4()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/consulta_ga4")
async def api_consulta_ga4(query: GA4Query):
    try:
        # Garantir que "contem" esteja no formato correto
        if query.filtro_condicao in ["contém", "contains", "contém"]:
            query.filtro_condicao = "contem"
            print(f"DIAGNÓSTICO API: Convertendo condição de filtro para 'contem'", file=sys.stderr)
        
        result = analytics.consulta_ga4(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.post("/api/consulta_search_console")
async def api_consulta_search_console(query: SearchConsoleQuery):
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

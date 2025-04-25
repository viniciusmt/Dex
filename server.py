from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from agents import analytics
import agents.search_console as search_console
import agents.youtube as youtube
import agents.drive as drive  # Importa o novo módulo de drive
import os
import uvicorn
import sys
import json
import anthropic
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
from dotenv import load_dotenv

load_dotenv()

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

class SearchConsoleQuery(BaseModel):
    data_inicio: str = "30daysAgo"
    data_fim: str = "today"
    dimensoes: List[str] = ["query"]
    metrica_extra: bool = True
    filtros: Optional[List[Dict[str, Any]]] = None
    limite: int = 20

class YouTubeQuery(BaseModel):
    pergunta: str

# Novas classes para as operações de Drive/Sheets
class CriarPlanilhaRequest(BaseModel):
    nome_planilha: str
    email_compartilhamento: str = "vinicius.matsumoto@fgv.br"

class ListarPlanilhasRequest(BaseModel):
    limite: int = 20

class CriarAbaRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    linhas: int = 100
    colunas: int = 20

class SobrescreverAbaRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    dados: str
    formato: str = "auto"  # "json", "csv" ou "auto"

class AdicionarCelulasRequest(BaseModel):
    planilha_id: str
    nome_aba: str
    dados: str
    formato: str = "auto"  # "json", "csv" ou "auto"

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
  "tipo_consulta": "ga4" ou "ga4_pivot" ou "search_console" ou "youtube" ou "drive_criar_planilha" ou "drive_listar_planilhas" ou "drive_criar_aba" ou "drive_sobrescrever_aba" ou "drive_adicionar_celulas",
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
        # Novas operações de Drive
        elif tipo_consulta == "drive_criar_planilha":
            resultado = drive.criar_planilha(**parametros)
        elif tipo_consulta == "drive_listar_planilhas":
            resultado = drive.listar_planilhas(**parametros)
        elif tipo_consulta == "drive_criar_aba":
            resultado = drive.criar_nova_aba(**parametros)
        elif tipo_consulta == "drive_sobrescrever_aba":
            # Converter os dados para o formato esperado pelo Google Sheets
            if "dados" in parametros and "formato" in parametros:
                dados_convertidos = drive.dados_para_lista(
                    parametros["dados"],
                    parametros["formato"]
                )
                parametros["dados"] = dados_convertidos
                # Remove o parâmetro formato que não é usado pela função sobrescrever_aba
                parametros.pop("formato", None)
            resultado = drive.sobrescrever_aba(**parametros)
        elif tipo_consulta == "drive_adicionar_celulas":
            # Converter os dados para o formato esperado pelo Google Sheets
            if "dados" in parametros and "formato" in parametros:
                dados_convertidos = drive.dados_para_lista(
                    parametros["dados"],
                    parametros["formato"]
                )
                parametros["dados"] = dados_convertidos
                # Remove o parâmetro formato que não é usado pela função adicionar_celulas
                parametros.pop("formato", None)
            resultado = drive.adicionar_celulas(**parametros)
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

# Novos endpoints para as operações de Drive/Sheets
@app.post("/api/drive/criar_planilha")
async def api_criar_planilha(query: CriarPlanilhaRequest):
    try:
        result = drive.criar_planilha(**query.dict())
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/listar_planilhas")
async def api_listar_planilhas(query: ListarPlanilhasRequest):
    try:
        result = drive.listar_planilhas(**query.dict())
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

@app.post("/api/drive/sobrescrever_aba")
async def api_sobrescrever_aba(query: SobrescreverAbaRequest):
    try:
        # Converte os dados para o formato esperado pelo Google Sheets
        dados_convertidos = drive.dados_para_lista(query.dados, query.formato)
        # Atualiza o objeto de consulta
        query_dict = query.dict()
        query_dict["dados"] = dados_convertidos
        query_dict.pop("formato")  # Remove o campo formato que não é usado pela função
        
        result = drive.sobrescrever_aba(**query_dict)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/drive/adicionar_celulas")
async def api_adicionar_celulas(query: AdicionarCelulasRequest):
    try:
        # Converte os dados para o formato esperado pelo Google Sheets
        dados_convertidos = drive.dados_para_lista(query.dados, query.formato)
        # Atualiza o objeto de consulta
        query_dict = query.dict()
        query_dict["dados"] = dados_convertidos
        query_dict.pop("formato")  # Remove o campo formato que não é usado pela função
        
        result = drive.adicionar_celulas(**query_dict)
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

@mcp.tool()
def consulta_ga4(**kwargs) -> str:
    # Garantir que "contem" esteja no formato correto
    if "filtro_condicao" in kwargs and kwargs["filtro_condicao"] in ["contém", "contains", "contém"]:
        kwargs["filtro_condicao"] = "contem"
        print(f"DIAGNÓSTICO MCP: Convertendo condição de filtro para 'contem'", file=sys.stderr)
    
    return analytics.consulta_ga4(**kwargs)

@mcp.tool()
def consulta_ga4_pivot(**kwargs) -> str:
    # Garantir que "contem" esteja no formato correto
    if "filtro_condicao" in kwargs and kwargs["filtro_condicao"] in ["contém", "contains", "contém"]:
        kwargs["filtro_condicao"] = "contem"
        print(f"DIAGNÓSTICO MCP PIVOT: Convertendo condição de filtro para 'contem'", file=sys.stderr)
    
    return analytics.consulta_ga4_pivot(**kwargs)

@mcp.tool()
def consulta_search_console_custom(**kwargs) -> dict:
    return search_console.consulta_search_console_custom(**kwargs)

@mcp.tool()
def analise_youtube(pergunta: str) -> dict:
    return youtube.youtube_analyzer(pergunta)

# Registrando as novas ferramentas MCP para o Google Drive/Sheets
@mcp.tool()
def drive_criar_planilha(nome_planilha: str, email_compartilhamento: str = "vinicius.matsumoto@fgv.br") -> dict:
    """
    Cria uma nova planilha no Google Drive e a compartilha com o email especificado.
    
    Args:
        nome_planilha: Nome da nova planilha
        email_compartilhamento: Email com quem compartilhar (padrão: vinicius.matsumoto@fgv.br)
    """
    return drive.criar_planilha(nome_planilha, email_compartilhamento)

@mcp.tool()
def drive_listar_planilhas(limite: int = 20) -> dict:
    """
    Lista todas as planilhas às quais a conta de serviço tem acesso.
    
    Args:
        limite: Número máximo de planilhas a listar
    """
    return drive.listar_planilhas(limite)

@mcp.tool()
def drive_criar_aba(planilha_id: str, nome_aba: str, linhas: int = 100, colunas: int = 20) -> dict:
    """
    Cria uma nova aba em uma planilha existente.
    
    Args:
        planilha_id: ID da planilha no Google Drive
        nome_aba: Nome da nova aba
        linhas: Número de linhas na nova aba
        colunas: Número de colunas na nova aba
    """
    return drive.criar_nova_aba(planilha_id, nome_aba, linhas, colunas)

@mcp.tool()
def drive_sobrescrever_aba(planilha_id: str, nome_aba: str, dados: str, formato: str = "auto") -> dict:
    """
    Sobrescreve completamente o conteúdo de uma aba existente.
    
    Args:
        planilha_id: ID da planilha no Google Drive
        nome_aba: Nome da aba a ser sobrescrita
        dados: String JSON ou CSV com os dados a serem escritos
        formato: "json", "csv" ou "auto" para detecção automática
    """
    dados_convertidos = drive.dados_para_lista(dados, formato)
    return drive.sobrescrever_aba(planilha_id, nome_aba, dados_convertidos)

@mcp.tool()
def drive_adicionar_celulas(planilha_id: str, nome_aba: str, dados: str, formato: str = "auto") -> dict:
    """
    Adiciona dados a uma aba existente, sem sobrescrever dados existentes.
    
    Args:
        planilha_id: ID da planilha no Google Drive
        nome_aba: Nome da aba onde adicionar dados
        dados: String JSON ou CSV com os dados a serem adicionados
        formato: "json", "csv" ou "auto" para detecção automática
    """
    dados_convertidos = drive.dados_para_lista(dados, formato)
    return drive.adicionar_celulas(planilha_id, nome_aba, dados_convertidos)

from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Analytics Agent API",
        version="1.0.0",
        description="API que interpreta perguntas em linguagem natural para gerar análises com GA4, Search Console, YouTube e Google Drive/Sheets",
        routes=app.routes,
    )
    openapi_schema["servers"] = [
        {"url": "https://dex-mcp-server-1212.onrender.com"}
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/.well-known/openapi.json")
def openapi_schema():
    return app.openapi()

try:
    if hasattr(mcp, 'router'):
        app.include_router(mcp.router, prefix="/mcp")
except Exception as e:
    print(f"Erro ao registrar router MCP: {e}", file=sys.stderr)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"Iniciando servidor na porta {port}", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=port)

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from agents import analytics
import agents.search_console as search_console
import agents.youtube as youtube
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
    limite_linhas: int = 30

class SearchConsoleQuery(BaseModel):
    data_inicio: str = "30daysAgo"
    data_fim: str = "today"
    dimensoes: List[str] = ["query"]
    metrica_extra: bool = True
    filtros: Optional[List[Dict[str, Any]]] = None
    limite: int = 20

class YouTubeQuery(BaseModel):
    pergunta: str

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
  "tipo_consulta": "ga4" ou "ga4_pivot" ou "search_console" ou "youtube",
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

        if tipo_consulta == "ga4":
            resultado = analytics.consulta_ga4(**parametros)
        elif tipo_consulta == "ga4_pivot":
            resultado = analytics.consulta_ga4_pivot(**parametros)
        elif tipo_consulta == "search_console":
            resultado = search_console.consulta_search_console_custom(**parametros)
        elif tipo_consulta == "youtube":
            resultado = youtube.youtube_analyzer(parametros.get("pergunta", query.pergunta))
        else:
            raise HTTPException(status_code=400, detail="Tipo de consulta não reconhecido")

        interpretacao_response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1500,
            temperature=0.2,
            system="Você é um assistente de analytics. Interprete resultados com base na pergunta original e forneça uma explicação clara.",
            messages=[{"role": "user", "content": [{"type": "text", "text": f"Pergunta: {query.pergunta}\n\nResultados:\n{resultado}"}]}]
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

from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Analytics Agent API",
        version="1.0.0",
        description="API que interpreta perguntas em linguagem natural para gerar análises com GA4, Search Console e YouTube",
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

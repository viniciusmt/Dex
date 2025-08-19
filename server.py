from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
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
from openapi_to_swagger import convert_openapi_to_swagger

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
except ImportError as e:
    print(f"Erro ao importar módulos: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("AVISO: Chave API do Claude não encontrada!", file=sys.stderr)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI(
    title="Dex Analytics MCP Server",
    description="Servidor MCP para Google Analytics e Search Console compatível com Copilot Studio",
    version="1.0.0"
)

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

@app.get("/swagger.yaml")
async def get_swagger():
    """Serve o arquivo swagger.yaml para Copilot Studio"""
    swagger_path = os.path.join(os.path.dirname(__file__), "swagger.yaml")
    return FileResponse(swagger_path, media_type="text/yaml")

# MCP Endpoint para Copilot Studio
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    return await mcp_handler(request)

@app.post("/api/mcp")  
async def mcp_api_endpoint(request: Request):
    return await mcp_handler(request)

async def mcp_handler(request: Request):
    """
    Endpoint MCP compatível com Copilot Studio seguindo protocolo streamable.
    """
    try:
        # Tenta ler como JSON primeiro
        try:
            body = await request.json()
        except Exception as json_error:
            # Se falhar, tenta ler como texto e fazer parse manual
            text_body = await request.body()
            text_content = text_body.decode('utf-8').strip()
            
            # Remove possíveis múltiplos JSONs, pega apenas o primeiro
            lines = text_content.split('\n')
            json_lines = []
            brace_count = 0
            
            for line in lines:
                if line.strip():
                    json_lines.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0 and json_lines:
                        break
            
            first_json = '\n'.join(json_lines)
            print(f"Extracted JSON: {first_json}", file=sys.stderr)
            body = json.loads(first_json)
        
        # Log da requisição para debug
        print(f"MCP Request: {json.dumps(body, indent=2)}", file=sys.stderr)
        
        # Resposta padrão MCP
        response = {
            "jsonrpc": "2.0",
            "id": body.get("id", "1"),
        }
        
        method = body.get("method")
        params = body.get("params", {})
        
        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "dex-analytics-server",
                    "version": "1.0.0"
                }
            }
            
        elif method == "tools/list":
            response["result"] = {
                "tools": [
                    {
                        "name": "listar_contas_ga4",
                        "description": "Lista todas as contas do Google Analytics 4 e suas propriedades associadas",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "consulta_ga4",
                        "description": "Consulta dados do Google Analytics 4",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "dimensao": {
                                    "type": "string",
                                    "description": "Dimensões para análise (ex: 'country', 'city')",
                                    "default": "country"
                                },
                                "metrica": {
                                    "type": "string", 
                                    "description": "Métricas para análise (ex: 'sessions', 'users')",
                                    "default": "sessions"
                                },
                                "periodo": {
                                    "type": "string",
                                    "description": "Data de início (ex: '7daysAgo', '2024-01-01')", 
                                    "default": "7daysAgo"
                                },
                                "data_fim": {
                                    "type": "string",
                                    "description": "Data de fim (ex: 'today', '2024-12-31')",
                                    "default": "today"
                                },
                                "property_id": {
                                    "type": "string",
                                    "description": "ID da propriedade GA4",
                                    "default": "properties/254018746"
                                },
                                "filtro_campo": {
                                    "type": "string",
                                    "description": "Campo para filtro"
                                },
                                "filtro_valor": {
                                    "type": "string", 
                                    "description": "Valor do filtro"
                                },
                                "filtro_condicao": {
                                    "type": "string",
                                    "description": "Condição do filtro",
                                    "default": "igual"
                                }
                            },
                            "required": []
                        }
                    },
                    {
                        "name": "consulta_ga4_pivot", 
                        "description": "Consulta GA4 com tabela pivot para análise cruzada de dimensões",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "dimensao": {
                                    "type": "string",
                                    "description": "Dimensão principal",
                                    "default": "country"
                                },
                                "dimensao_pivot": {
                                    "type": "string",
                                    "description": "Dimensão para cruzamento (pivot)", 
                                    "default": "deviceCategory"
                                },
                                "metrica": {
                                    "type": "string",
                                    "description": "Métrica para análise",
                                    "default": "sessions"
                                },
                                "periodo": {
                                    "type": "string",
                                    "description": "Data de início",
                                    "default": "7daysAgo"
                                },
                                "data_fim": {
                                    "type": "string",
                                    "description": "Data de fim", 
                                    "default": "today"
                                },
                                "property_id": {
                                    "type": "string",
                                    "description": "ID da propriedade GA4",
                                    "default": "properties/254018746"
                                },
                                "limite_linhas": {
                                    "type": "integer",
                                    "description": "Limite de linhas no resultado",
                                    "default": 100
                                }
                            },
                            "required": []
                        }
                    },
                    {
                        "name": "listar_sites_search_console",
                        "description": "Lista todos os sites disponíveis no Search Console",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "consulta_search_console_custom",
                        "description": "Consulta customizada ao Search Console com suporte a múltiplas dimensões e filtros",
                        "inputSchema": {
                            "type": "object", 
                            "properties": {
                                "site_url": {
                                    "type": "string",
                                    "description": "URL do site a ser analisado (obrigatório)"
                                },
                                "data_inicio": {
                                    "type": "string",
                                    "description": "Data de início",
                                    "default": "30daysAgo"
                                },
                                "data_fim": {
                                    "type": "string",
                                    "description": "Data de fim",
                                    "default": "today"
                                },
                                "dimensoes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Lista de dimensões para análise",
                                    "default": ["query"]
                                },
                                "metrica_extra": {
                                    "type": "boolean",
                                    "description": "Se deve incluir métricas extras como CTR e posição",
                                    "default": True
                                },
                                "limite": {
                                    "type": "integer",
                                    "description": "Número máximo de resultados",
                                    "default": 100
                                },
                                "query_filtro": {
                                    "type": "string",
                                    "description": "Filtro específico para queries"
                                },
                                "pagina_filtro": {
                                    "type": "string",
                                    "description": "Filtro específico para páginas"
                                }
                            },
                            "required": ["site_url"]
                        }
                    },
                    {
                        "name": "verificar_propriedade_site_search_console",
                        "description": "Verifica se um site específico está disponível no Search Console",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "site_url": {
                                    "type": "string",
                                    "description": "URL do site para verificar"
                                }
                            },
                            "required": ["site_url"]
                        }
                    }
                ]
            }
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_arguments = params.get("arguments", {})
            
            try:
                if tool_name == "listar_contas_ga4":
                    result = analytics.listar_contas_ga4()
                elif tool_name == "consulta_ga4":
                    result = analytics.consulta_ga4(**tool_arguments)
                elif tool_name == "consulta_ga4_pivot":
                    result = analytics.consulta_ga4_pivot(**tool_arguments) 
                elif tool_name == "listar_sites_search_console":
                    result = search_console.listar_sites_search_console()
                elif tool_name == "consulta_search_console_custom":
                    result = search_console.consulta_search_console_custom(**tool_arguments)
                elif tool_name == "verificar_propriedade_site_search_console":
                    result = search_console.verificar_propriedade_site_search_console(**tool_arguments)
                else:
                    raise ValueError(f"Ferramenta não encontrada: {tool_name}")
                
                response["result"] = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
                
            except Exception as e:
                response["error"] = {
                    "code": -32000,
                    "message": f"Erro ao executar ferramenta {tool_name}: {str(e)}"
                }
                
        else:
            response["error"] = {
                "code": -32601, 
                "message": f"Método não encontrado: {method}"
            }
            
        print(f"MCP Response: {json.dumps(response, indent=2)}", file=sys.stderr)
        return response
        
    except Exception as e:
        print(f"Erro no endpoint MCP: {str(e)}", file=sys.stderr)
        return {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {
                "code": -32000,
                "message": f"Erro interno: {str(e)}"
            }
        }

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
  "tipo_consulta": "ga4" ou "ga4_pivot" ou "search_console" ou "search_console_listar_sites" ou "search_console_verificar_site" ou "listar_contas_ga4",
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
        elif tipo_consulta == "listar_contas_ga4":
            resultado = analytics.listar_contas_ga4()
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
        
        # Verifica se ANTHROPIC_API_KEY existe
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        has_claude_key = claude_key is not None

        # Retorna as informações de diagnóstico
        return {
            "environment": {
                "has_google_credentials": has_google_creds,
                "google_credentials_valid_json": json_valid,
                "google_credentials_info": creds_info,
                "has_anthropic_api_key": has_claude_key
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

# Convert OpenAPI 3 schema to Swagger 2.0 for compatibility
_original_get_custom_openapi = get_custom_openapi

def get_custom_openapi() -> dict:
    openapi_schema = _original_get_custom_openapi()
    swagger_schema = convert_openapi_to_swagger(openapi_schema)
    app.openapi_schema = swagger_schema
    return app.openapi_schema

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

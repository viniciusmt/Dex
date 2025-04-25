from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from agents import analytics  # módulo GA4
import agents.search_console as search_console
import agents.youtube as youtube
import os
import uvicorn
import sys
import json
import anthropic
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

# Carrega a chave API do Claude do ambiente
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
print("AVISO: Chave API do Claude não encontrada!", file=sys.stderr)

# Cria cliente do Anthropic
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Cria a instância FastAPI
app = FastAPI(title="Analytics Agent API")

# Adiciona CORS para permitir acesso de diferentes origens
app.add_middleware(
CORSMiddleware,
allow_origins=["*"],  # Permite todas as origens
allow_credentials=True,
allow_methods=["*"],  # Permite todos os métodos
allow_headers=["*"],  # Permite todos os cabeçalhos
)

# Cria a instância FastMCP
mcp = FastMCP("analytics-agent")

# Endpoint raiz para teste básico
@app.get("/")
async def root():
return {"message": "API de Analytics com Claude e MCP está funcionando!"}

# Modelo para requisição de pergunta em linguagem natural
class NaturalLanguageQuery(BaseModel):
pergunta: str
contexto: Optional[str] = None

# Modelo para requisição de consulta GA4
class GA4Query(BaseModel):
dimensao: str = "country"
metrica: str = "sessions"
periodo: str = "7daysAgo"
filtro_campo: str = ""
filtro_valor: str = ""
filtro_condicao: str = "igual"

# Modelo para requisição de consulta GA4 Pivot
class GA4PivotQuery(BaseModel):
dimensao: str = "country"
dimensao_pivot: str = "deviceCategory"
metrica: str = "sessions"
periodo: str = "7daysAgo"
filtro_campo: str = ""
filtro_valor: str = ""
filtro_condicao: str = "igual"
limite_linhas: int = 30

# Modelo para requisição Search Console
class SearchConsoleQuery(BaseModel):
data_inicio: str = "30daysAgo"
data_fim: str = "today"
dimensoes: List[str] = ["query"]
metrica_extra: bool = True
filtros: Optional[List[Dict[str, Any]]] = None
limite: int = 20

# Modelo para requisição YouTube
class YouTubeQuery(BaseModel):
pergunta: str

# Endpoint para perguntas em linguagem natural
@app.post("/perguntar")
async def perguntar(query: NaturalLanguageQuery):
"""
   Endpoint para processar perguntas em linguagem natural.
   Usa o Claude para interpretar a pergunta e determinar qual API chamar.
   """
try:
if not ANTHROPIC_API_KEY:
raise HTTPException(status_code=500, detail="Chave API do Claude não configurada")

# Prompt de sistema
system_prompt = (
"Você é um assistente de analytics. Seu trabalho é transformar perguntas em linguagem natural "
"em objetos JSON válidos com o formato especificado. Responda SOMENTE com JSON puro. "
"Sem explicações. Sem formatação Markdown. Sem prefixos ou sufixos. Apenas JSON."
)

# Prompt do usuário com instruções
user_prompt = f"""
Pergunta: {query.pergunta}

Retorne um JSON neste formato:

{{
 "tipo_consulta": "ga4" ou "ga4_pivot" ou "search_console" ou "youtube",
 "parametros": {{
   // parâmetros relevantes conforme o tipo
 }}
}}

Apenas o JSON. Nenhuma explicação.
"""

response = client.messages.create(
model="claude-3-5-sonnet-20240620",
max_tokens=1000,
temperature=0,
system=system_prompt,
messages=[
{
"role": "user",
"content": [{"type": "text", "text": user_prompt}]
}
]
)

content = response.content[0].text.strip()
print(f"[Claude output bruto]\n{content}\n", file=sys.stderr)

# Remove marcações de código caso existam
if "```json" in content:
content = content.split("```json")[1].split("```")[0].strip()
elif "```" in content:
content = content.split("```")[1].split("```")[0].strip()

try:
parsed_response = json.loads(content)
except Exception as e:
raise HTTPException(status_code=400, detail=f"Erro ao interpretar JSON do Claude: {e}\nConteúdo: {content}")

tipo_consulta = parsed_response.get("tipo_consulta")
parametros = parsed_response.get("parametros", {})

# Executa a consulta apropriada
if tipo_consulta == "ga4":
resultado = analytics.consulta_ga4(
dimensao=parametros.get("dimensao", "country"),
metrica=parametros.get("metrica", "sessions"),
periodo=parametros.get("periodo", "7daysAgo"),
filtro_campo=parametros.get("filtro_campo", ""),
filtro_valor=parametros.get("filtro_valor", ""),
filtro_condicao=parametros.get("filtro_condicao", "igual")
)
elif tipo_consulta == "ga4_pivot":
resultado = analytics.consulta_ga4_pivot(
dimensao=parametros.get("dimensao", "country"),
dimensao_pivot=parametros.get("dimensao_pivot", "deviceCategory"),
metrica=parametros.get("metrica", "sessions"),
periodo=parametros.get("periodo", "7daysAgo"),
filtro_campo=parametros.get("filtro_campo", ""),
filtro_valor=parametros.get("filtro_valor", ""),
filtro_condicao=parametros.get("filtro_condicao", "igual"),
limite_linhas=parametros.get("limite_linhas", 30)
)
elif tipo_consulta == "search_console":
resultado = search_console.consulta_search_console_custom(
data_inicio=parametros.get("data_inicio", "30daysAgo"),
data_fim=parametros.get("data_fim", "today"),
dimensoes=parametros.get("dimensoes", ["query"]),
metrica_extra=parametros.get("metrica_extra", True),
filtros=parametros.get("filtros"),
limite=parametros.get("limite", 20)
)
elif tipo_consulta == "youtube":
resultado = youtube.youtube_analyzer(parametros.get("pergunta", query.pergunta))
else:
raise HTTPException(status_code=400, detail=f"Tipo de consulta não reconhecido: {tipo_consulta}")

# Interpretação com Claude (em linguagem natural)
interpretacao_response = client.messages.create(
model="claude-3-5-sonnet-20240620",
max_tokens=1500,
temperature=0.2,
system="Você é um assistente de analytics. Interprete resultados com base na pergunta original e forneça uma explicação clara.",
messages=[
{
"role": "user",
"content": [{"type": "text", "text": f"Pergunta: {query.pergunta}\n\nResultados:\n{resultado}"}]
}
]
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



# Endpoint direto para consulta GA4
@app.post("/api/consulta_ga4")
async def api_consulta_ga4(query: GA4Query):
try:
result = analytics.consulta_ga4(
query.dimensao, query.metrica, query.periodo,
query.filtro_campo, query.filtro_valor, query.filtro_condicao
)
return {"result": result}
except Exception as e:
raise HTTPException(status_code=500, detail=str(e))

# Endpoint direto para consulta GA4 Pivot
@app.post("/api/consulta_ga4_pivot")
async def api_consulta_ga4_pivot(query: GA4PivotQuery):
try:
result = analytics.consulta_ga4_pivot(
query.dimensao, query.dimensao_pivot, query.metrica, query.periodo,
query.filtro_campo, query.filtro_valor, query.filtro_condicao, query.limite_linhas
)
return {"result": result}
except Exception as e:
raise HTTPException(status_code=500, detail=str(e))

# Endpoint direto para consulta Search Console
@app.post("/api/consulta_search_console")
async def api_consulta_search_console(query: SearchConsoleQuery):
try:
result = search_console.consulta_search_console_custom(
query.data_inicio, query.data_fim, query.dimensoes,
query.metrica_extra, query.filtros, query.limite
)
return {"result": result}
except Exception as e:
raise HTTPException(status_code=500, detail=str(e))

# Endpoint direto para análise de YouTube
@app.post("/api/analise_youtube")
async def api_analise_youtube(query: YouTubeQuery):
try:
result = youtube.youtube_analyzer(query.pergunta)
return {"result": result}
except Exception as e:
raise HTTPException(status_code=500, detail=str(e))

# Endpoint para debug que lista todas as rotas
@app.get("/debug/routes")
async def list_routes():
routes = []
for route in app.routes:
routes.append({
"path": route.path,
"name": route.name,
"methods": route.methods,
})
return {"routes": routes}

# Registra as ferramentas no MCP (opcional, para compatibilidade)
@mcp.tool()
def consulta_ga4(
dimensao: str = "country",
metrica: str = "sessions",
periodo: str = "7daysAgo",
filtro_campo: str = "",
filtro_valor: str = "",
filtro_condicao: str = "igual"
) -> str:
return analytics.consulta_ga4(
dimensao, metrica, periodo,
filtro_campo, filtro_valor, filtro_condicao
)

@mcp.tool()
def consulta_ga4_pivot(
dimensao: str = "country",
dimensao_pivot: str = "deviceCategory",
metrica: str = "sessions",
periodo: str = "7daysAgo",
filtro_campo: str = "",
filtro_valor: str = "",
filtro_condicao: str = "igual",
limite_linhas: int = 30
) -> str:
return analytics.consulta_ga4_pivot(
dimensao, dimensao_pivot, metrica, periodo,
filtro_campo, filtro_valor, filtro_condicao, limite_linhas
)

@mcp.tool()
def consulta_search_console_custom(
data_inicio: str = "30daysAgo",
data_fim: str = "today",
dimensoes: list[str] = ["query"],
metrica_extra: bool = True,
filtros: list[dict] = None,
limite: int = 20
) -> dict:
return search_console.consulta_search_console_custom(
data_inicio, data_fim, dimensoes, metrica_extra, filtros, limite
)

@mcp.tool()
def analise_youtube(pergunta: str) -> dict:
return youtube.youtube_analyzer(pergunta)

# Tenta registrar o router do MCP (opcional, para compatibilidade)
try:
if hasattr(mcp, 'router'):
app.include_router(mcp.router, prefix="/mcp")
except Exception as e:
print(f"Erro ao registrar router MCP: {e}", file=sys.stderr)


from fastapi.openapi.utils import get_openapi

# Customiza o schema OpenAPI com o campo 'servers' corretamente definido
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



# Endpoint necessário para validação da URL no ChatGPT (exige 'servers')
@app.get("/.well-known/openapi.json")
def openapi_schema():
return app.openapi()

if __name__ == "__main__":
port = int(os.getenv("PORT", 10000))
print(f"Iniciando servidor na porta {port}", file=sys.stderr)
uvicorn.run(app, host="0.0.0.0", port=port)

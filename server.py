from mcp.server.fastmcp import FastMCP
from agents import analytics  # módulo GA4
import agents.search_console as search_console
import agents.youtube as youtube
import os
import uvicorn
from fastapi import FastAPI

# Cria a instância FastMCP
mcp = FastMCP("analytics-agent")

# Cria uma instância FastAPI diretamente
app = FastAPI(title="Analytics Agent API")

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

# Registra o router do MCP no app FastAPI
# Esta é a parte que muda comparada à versão anterior
# Não tentamos mais acessar o fastapi_app diretamente
if hasattr(mcp, 'router'):
    app.include_router(mcp.router)

# Verificar se o MCP tem todos os caminhos registrados
@app.get("/")
async def root():
    return {"message": "API de Analytics com Claude e MCP está funcionando!"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"Iniciando servidor na porta {port}")
    # Agora usamos a instância 'app' que criamos diretamente
    uvicorn.run(app, host="0.0.0.0", port=port)

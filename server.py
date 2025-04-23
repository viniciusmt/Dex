from mcp.server.fastmcp import FastMCP
from agents import analytics  # módulo GA4
import agents.search_console as search_console
import agents.youtube as youtube

# Create the FastMCP app
mcp = FastMCP("analytics-agent")

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


# ✅ Compatível com Render usando Uvicorn e a porta do ambiente
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    
    # Fix: Access the FastAPI app properly based on the current FastMCP implementation
    # The app property may now be called 'app' instead of 'fastapi_app'
    app = mcp.app if hasattr(mcp, 'app') else mcp.fastapi_app
    
    # For newer versions, FastMCP may directly return a FastAPI app
    if app is None and callable(mcp):
        app = mcp()
    
    # As a fallback, create a FastAPI app directly using the MCP router
    if app is None and hasattr(mcp, 'router'):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(mcp.router)
    
    # Final fallback if none of the above works
    if app is None:
        raise AttributeError(
            "Unable to find FastAPI app in FastMCP object. "
            "Please check the FastMCP SDK documentation for the correct API."
        )
    
    uvicorn.run(app, host="0.0.0.0", port=port)

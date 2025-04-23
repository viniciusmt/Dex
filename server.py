from mcp.server.fastmcp import FastMCP
from agents import analytics  # módulo GA4
from agents import trends     # módulo Google Trends
import agents.search_console as search_console  # Corrigida a importação
import agents.search_terms as search_terms  # Novo módulo para buscar termos
import agents.youtube as youtube

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
    return search_console.consulta_search_console_custom(data_inicio, data_fim, dimensoes, metrica_extra, filtros, limite)


@mcp.tool()
def analise_youtube(pergunta: str) -> dict:
    return youtube.youtube_analyzer(pergunta)


if __name__ == "__main__":
    mcp.run()
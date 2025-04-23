import os
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Lê credenciais do JSON como string (vinda de variável de ambiente)
creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build("searchconsole", "v1", credentials=credentials)

SITE_URL = "https://educacao-executiva.fgv.br/"

def resolver_data(d: str):
    if "daysAgo" in d:
        dias = int(d.replace("daysAgo", "").strip())
        return (datetime.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    if d == "today":
        return datetime.today().strftime("%Y-%m-%d")
    return d

# Mantém a função consulta_search_console_custom exatamente como está


def resolver_data(d: str):
    if "daysAgo" in d:
        dias = int(d.replace("daysAgo", "").strip())
        return (datetime.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    if d == "today":
        return datetime.today().strftime("%Y-%m-%d")
    return d

def consulta_search_console_custom(
    data_inicio: str = "30daysAgo",
    data_fim: str = "today",
    dimensoes: list[str] = ["query"],
    metrica_extra: bool = False,
    filtros: list[dict] = None,
    limite: int = 20
) -> dict:
    """
    Consulta customizada ao Search Console com suporte a múltiplas dimensões e filtros.

    Parâmetros:
    - data_inicio: "30daysAgo", "today" ou "YYYY-MM-DD"
    - data_fim: "today" ou "YYYY-MM-DD"
    - dimensoes: lista de dimensões como "query", "date", "page", "country"
    - metrica_extra: inclui todas as métricas padrão (clicks, impressions, ctr, position)
    - filtros: lista de filtros no formato {"dimension": "query", "operator": "contains", "expression": "mba"}
    - limite: número máximo de linhas
    """
    try:
        data_inicio = resolver_data(data_inicio)
        data_fim = resolver_data(data_fim)

        body = {
            "startDate": data_inicio,
            "endDate": data_fim,
            "dimensions": dimensoes,
            "rowLimit": limite
        }

        if filtros:
            body["dimensionFilterGroups"] = [{"filters": filtros}]

        response = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()

        resultados = []
        for row in response.get("rows", []):
            registro = {f"Dimensão {i+1}": v for i, v in enumerate(row.get("keys", []))}
            if metrica_extra:
                registro.update({
                    "Cliques": row.get("clicks"),
                    "Impressões": row.get("impressions"),
                    "CTR": f"{row['ctr']:.2%}",
                    "Posição Média": f"{row['position']:.2f}"
                })
            resultados.append(registro)

        return {
            "site": SITE_URL,
            "periodo": f"{data_inicio} a {data_fim}",
            "dimensoes": dimensoes,
            "dados": resultados
        }

    except Exception as e:
        return {"erro": str(e)}

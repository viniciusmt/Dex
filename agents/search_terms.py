from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# Caminho para o arquivo JSON da conta de serviço
SERVICE_ACCOUNT_FILE = r"C:\Users\Vinicius\Projetos\agent_mcp\agents\projeto-apis-408113-b4cfe422134b.json"

# Escopo necessário para acessar os dados do Search Console
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# Autenticação com a conta de serviço
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# Construindo o serviço da API Search Console
service = build("searchconsole", "v1", credentials=credentials)

# Site configurado para análise
SITE_URL = "https://educacao-executiva.fgv.br/"

def resolver_data(d: str):
    try:
        if "daysAgo" in d:
            dias = int(d.replace("daysAgo", "").strip())
            return (datetime.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
        if d == "today":
            return datetime.today().strftime("%Y-%m-%d")
        return d
    except Exception:
        return d

def consulta_termos_search_console(
    termos: list[str] = None,
    padrao: str = "",
    data_inicio: str = "7daysAgo",
    data_fim: str = "today"
) -> dict:
    """
    Obtém dados do Search Console para termos de pesquisa específicos ou que contenham um padrão.
    """
    try:
        # Converte datas relativas
        data_inicio = resolver_data(data_inicio)
        data_fim = resolver_data(data_fim)

        filtros = []
        if termos:
            for termo in termos:
                filtros.append({"dimension": "query", "operator": "equals", "expression": termo})
        elif padrao:
            filtros.append({"dimension": "query", "operator": "contains", "expression": padrao})

        response = service.searchanalytics().query(
            siteUrl=SITE_URL,
            body={
                "startDate": data_inicio,
                "endDate": data_fim,
                "dimensions": ["query"],
                "dimensionFilterGroups": [{"filters": filtros}] if filtros else [],
                "rowLimit": 20
            }
        ).execute()

        resultados = []
        for row in response.get("rows", []):
            resultados.append({
                "Termo": row["keys"][0],
                "Cliques": row["clicks"],
                "Impressões": row["impressions"],
                "CTR": f"{row['ctr']:.2%}",
                "Posição Média": f"{row['position']:.2f}"
            })

        return {
            "site": SITE_URL,
            "periodo": f"{data_inicio} a {data_fim}",
            "termos": termos if termos else f"Contendo '{padrao}'",
            "dados": resultados
        }

    except Exception as e:
        return {"erro": str(e)}

import os
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import sys

def log_debug(message):
    """Função para log de depuração."""
    print(f"SEARCH_CONSOLE DEBUG: {message}", file=sys.stderr)

def init_search_console_service():
    """Inicializa o serviço do Search Console usando credenciais de variável de ambiente."""
    try:
        # Lê credenciais do JSON como string (vinda de variável de ambiente)
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            log_debug("ERRO: Variável GOOGLE_CREDENTIALS não encontrada")
            return None
            
        # Tenta analisar o JSON
        try:
            creds_dict = json.loads(creds_json)
            log_debug(f"JSON analisado com sucesso. Email da conta: {creds_dict.get('client_email')}")
        except json.JSONDecodeError as e:
            log_debug(f"Falha ao analisar JSON das credenciais: {e}")
            return None
            
        # Cria as credenciais
        try:
            SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            log_debug("Credenciais Search Console criadas com sucesso")
        except Exception as e:
            log_debug(f"Falha ao criar credenciais: {e}")
            return None
            
        # Cria o serviço
        try:
            service = build("searchconsole", "v1", credentials=credentials)
            log_debug("Serviço Search Console criado com sucesso")
            return service
        except Exception as e:
            log_debug(f"Falha ao criar serviço Search Console: {e}")
            return None
    except Exception as e:
        log_debug(f"ERRO GERAL: {e}")
        return None

# Inicializa o serviço uma vez
service = init_search_console_service()

def resolver_data(d: str):
    """Converte strings de data relativa para formato YYYY-MM-DD"""
    if "daysAgo" in d:
        dias = int(d.replace("daysAgo", "").strip())
        return (datetime.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    if d == "today":
        return datetime.today().strftime("%Y-%m-%d")
    return d

def listar_sites_search_console() -> dict:
    """
    Lista todos os sites disponíveis no Search Console para a conta de serviço.
    
    Returns:
        dict: Lista de sites disponíveis ou erro
    """
    if service is None:
        return {"erro": "Serviço Search Console não inicializado. Verifique as credenciais."}
    
    try:
        log_debug("Listando sites disponíveis no Search Console...")
        # Lista todos os sites disponíveis
        sites_list = service.sites().list().execute()
        
        sites = []
        for site in sites_list.get('siteEntry', []):
            sites.append({
                "url": site.get('siteUrl'),
                "nivel_permissao": site.get('permissionLevel')
            })
        
        log_debug(f"Encontrados {len(sites)} sites no Search Console")
        return {
            "sucesso": True,
            "mensagem": f"Encontrados {len(sites)} sites no Search Console",
            "sites": sites
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log_debug(f"Erro ao listar sites: {str(e)}\n{error_details}")
        return {"erro": f"Erro ao listar sites do Search Console: {str(e)}"}

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
        dimensoes: Lista de dimensões (padrão: ["query"])
        metrica_extra: Se deve incluir métricas extras (padrão: True)
        filtros: Lista de filtros customizados (opcional)
        limite: Número máximo de resultados (padrão: 100)
        query_filtro: Filtro específico para queries - usa condição 'contém' (opcional)
        pagina_filtro: Filtro específico para páginas - usa condição 'contém' (opcional)
    """
    # Verificar se o serviço foi inicializado corretamente
    if service is None:
        return {"erro": "Serviço Search Console não inicializado. Verifique as credenciais."}
    
    # Garantir que a URL do site tenha o formato correto
    if not site_url.startswith(('http://', 'https://')):
        site_url = f"https://{site_url}"
    
    if not site_url.endswith('/'):
        site_url = f"{site_url}/"
        
    try:
        log_debug(f"Iniciando consulta para site: {site_url}")
        log_debug(f"Período: {data_inicio} a {data_fim}")
        log_debug(f"Dimensões: {dimensoes}")
        
        data_inicio = resolver_data(data_inicio)
        data_fim = resolver_data(data_fim)

        body = {
            "startDate": data_inicio,
            "endDate": data_fim,
            "dimensions": dimensoes,
            "rowLimit": limite
        }

        # Construir filtros automáticos para query e página se fornecidos
        filtros_automaticos = []
        
        if query_filtro:
            filtros_automaticos.append({
                "dimension": "query",
                "operator": "contains",
                "expression": query_filtro
            })
            log_debug(f"Adicionado filtro de query: contém '{query_filtro}'")
        
        if pagina_filtro:
            filtros_automaticos.append({
                "dimension": "page",
                "operator": "contains", 
                "expression": pagina_filtro
            })
            log_debug(f"Adicionado filtro de página: contém '{pagina_filtro}'")
        
        # Combinar filtros automáticos com filtros customizados
        todos_filtros = filtros_automaticos[:]
        if filtros:
            todos_filtros.extend(filtros)
            log_debug(f"Adicionados {len(filtros)} filtros customizados")
        
        # Aplicar filtros se existirem
        if todos_filtros:
            body["dimensionFilterGroups"] = [{"filters": todos_filtros}]

        log_debug("Enviando requisição ao Search Console...")
        response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()

        resultados = []
        for row in response.get("rows", []):
            registro = {}
            
            # Mapear dimensões com nomes mais amigáveis
            for i, dimensao in enumerate(dimensoes):
                if i < len(row.get("keys", [])):
                    nome_dimensao = {
                        "query": "Consulta",
                        "page": "Página", 
                        "country": "País",
                        "device": "Dispositivo",
                        "date": "Data"
                    }.get(dimensao, f"Dimensão {dimensao}")
                    
                    registro[nome_dimensao] = row["keys"][i]
            
            # Adicionar métricas se solicitado
            if metrica_extra:
                registro.update({
                    "Cliques": row.get("clicks", 0),
                    "Impressões": row.get("impressions", 0),
                    "CTR": f"{row.get('ctr', 0):.2%}",
                    "Posição Média": f"{row.get('position', 0):.2f}"
                })
            else:
                # Apenas métricas básicas
                registro.update({
                    "Cliques": row.get("clicks", 0),
                    "Impressões": row.get("impressions", 0)
                })
                
            resultados.append(registro)

        # Informações sobre filtros aplicados
        filtros_info = []
        if query_filtro:
            filtros_info.append(f"Query contém: '{query_filtro}'")
        if pagina_filtro:
            filtros_info.append(f"Página contém: '{pagina_filtro}'")
        if filtros:
            for filtro in filtros:
                operador = filtro.get('operator', 'equals')
                filtros_info.append(f"{filtro.get('dimension')} {operador} '{filtro.get('expression')}'")

        log_debug(f"Consulta concluída: {len(resultados)} resultados encontrados")
        return {
            "sucesso": True,
            "site": site_url,
            "periodo": f"{data_inicio} a {data_fim}",
            "dimensoes": dimensoes,
            "filtros_aplicados": filtros_info,
            "total_resultados": len(resultados),
            "dados": resultados
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log_debug(f"Erro na consulta_search_console_custom: {str(e)}\n{error_details}")
        return {"erro": f"Erro na consulta Search Console: {str(e)}"}

def verificar_propriedade_site_search_console(site_url: str) -> dict:
    """
    Verifica se um site específico está disponível no Search Console.
    
    Args:
        site_url: URL do site para verificar
        
    Returns:
        dict: Informações sobre a disponibilidade do site
    """
    if service is None:
        return {"erro": "Serviço Search Console não inicializado. Verifique as credenciais."}
    
    # Garantir formato correto da URL
    if not site_url.startswith(('http://', 'https://')):
        site_url = f"https://{site_url}"
    
    if not site_url.endswith('/'):
        site_url = f"{site_url}/"
    
    try:
        log_debug(f"Verificando propriedade do site: {site_url}")
        # Obter informações do site específico
        site_info = service.sites().get(siteUrl=site_url).execute()
        
        return {
            "sucesso": True,
            "site_url": site_info.get('siteUrl'),
            "nivel_permissao": site_info.get('permissionLevel'),
            "mensagem": f"Site {site_url} está disponível no Search Console"
        }
        
    except Exception as e:
        log_debug(f"Erro ao verificar propriedade: {str(e)}")
        return {
            "sucesso": False,
            "site_url": site_url,
            "erro": f"Site não encontrado ou sem permissão: {str(e)}"
        }

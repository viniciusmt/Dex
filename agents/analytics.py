import os
import json
import sys
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, RunPivotReportRequest,
    DateRange, Dimension, Metric,
    FilterExpression, Filter, Pivot, OrderBy
)
from google.analytics.data_v1beta.types import Filter as GAFilter

# Funções de diagnóstico
def init_analytics_client():
    try:
        # Lê credenciais do JSON como string (vinda de variável de ambiente)
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            print("ERRO: Variável GOOGLE_CREDENTIALS não encontrada", file=sys.stderr)
            return None
            
        # Tenta analisar o JSON
        try:
            creds_dict = json.loads(creds_json)
            print(f"DIAGNÓSTICO: JSON analisado com sucesso. Tipo da conta: {creds_dict.get('type')}", file=sys.stderr)
            print(f"DIAGNÓSTICO: Email da conta: {creds_dict.get('client_email')}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"ERRO: Falha ao analisar JSON das credenciais: {e}", file=sys.stderr)
            print(f"DIAGNÓSTICO: Primeiros 100 caracteres da string: {creds_json[:100]}", file=sys.stderr)
            return None
            
        # Cria as credenciais
        try:
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            print("DIAGNÓSTICO: Credenciais criadas com sucesso", file=sys.stderr)
        except Exception as e:
            print(f"ERRO: Falha ao criar credenciais: {e}", file=sys.stderr)
            return None
            
        # Cria o cliente
        try:
            client = BetaAnalyticsDataClient(credentials=credentials)
            print("DIAGNÓSTICO: Cliente GA4 criado com sucesso", file=sys.stderr)
            return client
        except Exception as e:
            print(f"ERRO: Falha ao criar cliente GA4: {e}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"ERRO GERAL: {e}", file=sys.stderr)
        return None

# Inicializa o cliente GA4
client = init_analytics_client()

def listar_contas_ga4():
    """
    Lista todas as contas do Google Analytics 4 e suas propriedades associadas.
    
    Returns:
        dict: Dicionário com informações sobre contas e propriedades ou erro
    """
    try:
        from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient
        from google.analytics.admin_v1alpha.types import ListPropertiesRequest
        
        # Verifica se as credenciais existem (usa as mesmas credenciais do cliente de dados)
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            return {"erro": "Credenciais do Google não encontradas na variável GOOGLE_CREDENTIALS"}
        
        try:
            creds_dict = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            return {"erro": f"Erro ao processar credenciais: {str(e)}"}
        
        # Inicializa o cliente Admin
        admin_client = AnalyticsAdminServiceClient(credentials=credentials)
        
        print("DIAGNÓSTICO: Listando contas GA4...", file=sys.stderr)
        
        # Lista todas as contas
        accounts = admin_client.list_accounts()
        
        resultado = {
            "sucesso": True,
            "mensagem": "Contas e propriedades listadas com sucesso",
            "contas": []
        }
        
        conta_count = 0
        for account in accounts:
            conta_count += 1
            print(f"DIAGNÓSTICO: Processando conta {conta_count}: {account.display_name}", file=sys.stderr)
            
            conta_info = {
                "id_conta": account.name,
                "nome_conta": account.display_name,
                "propriedades": []
            }
            
            try:
                # Lista propriedades dessa conta  
                request = ListPropertiesRequest(filter=f"parent:{account.name}")
                properties = admin_client.list_properties(request=request)
                
                prop_count = 0
                for prop in properties:
                    prop_count += 1
                    print(f"DIAGNÓSTICO: Processando propriedade {prop_count}: {prop.display_name}", file=sys.stderr)
                    
                    conta_info["propriedades"].append({
                        "id_propriedade": prop.name,
                        "nome_propriedade": prop.display_name,
                        # O formato que as funções existentes esperam 
                        "property_id": prop.name,
                        "tipo": prop.property_type.name if hasattr(prop, 'property_type') else "GA4"
                    })
                    
                print(f"DIAGNÓSTICO: Encontradas {prop_count} propriedades na conta {account.display_name}", file=sys.stderr)
                
            except Exception as e:
                print(f"Erro ao listar propriedades da conta {account.name}: {str(e)}", file=sys.stderr)
                conta_info["erro_propriedades"] = str(e)
            
            resultado["contas"].append(conta_info)
        
        print(f"DIAGNÓSTICO: Total de {conta_count} contas processadas", file=sys.stderr)
        return resultado
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Erro ao listar contas GA4: {str(e)}\n{error_details}", file=sys.stderr)
        return {"erro": f"Erro ao listar contas GA4: {str(e)}"}

def responder(pergunta):
    """
    Função para compatibilidade com o sistema de agentes.
    Responde a perguntas sobre analytics.
    """
    pergunta_lower = pergunta.lower()
    
    if "contas" in pergunta_lower or "listar contas" in pergunta_lower:
        resultado = listar_contas_ga4()
        return {"response": f"Resultado da consulta: {json.dumps(resultado, ensure_ascii=False, indent=2)}"}
    
    # Outros tipos de consulta podem ser adicionados aqui
    return {"response": "Comando não reconhecido. Tente perguntar sobre 'listar contas ga4'."}


def consulta_ga4(
    dimensao: str = "country",
    metrica: str = "sessions",
    periodo: str = "7daysAgo",
    data_fim: str = "today",  # Nova variável para data final
    filtro_campo: str = "",
    filtro_valor: str = "",
    filtro_condicao: str = "igual",
    property_id: str = "properties/254018746"
) -> str:
    """
    Consulta sessões segmentadas por dimensões no GA4.
    
    Args:
        dimensao: Dimensões para análise (ex: 'country', 'city')
        metrica: Métricas para análise (ex: 'sessions', 'users')
        periodo: Data de início (ex: '7daysAgo', '2024-01-01')
        data_fim: Data de fim (ex: 'today', '2024-12-31')
        filtro_campo: Campo para filtro
        filtro_valor: Valor do filtro
        filtro_condicao: Condição do filtro
        property_id: ID da propriedade GA4
    """
    try:
        # Verifica se o cliente está inicializado
        if client is None:
            return "Erro: Cliente GA4 não inicializado corretamente. Verifique as credenciais."

        print(f"DIAGNÓSTICO: Iniciando consulta GA4 - dimensão: {dimensao}, métrica: {metrica}", file=sys.stderr)
        print(f"DIAGNÓSTICO: Período - início: {periodo}, fim: {data_fim}", file=sys.stderr)
        
        # Garante formato correto do property_id
        if not property_id.startswith("properties/"):
            property_id = f"properties/{property_id}"
            
        # Prepara dimensões e métricas
        lista_dimensoes = [Dimension(name=d.strip()) for d in dimensao.split(",")]
        lista_metricas = [Metric(name=m.strip()) for m in metrica.split(",")]

        # Mapeia condição textual para enums do GA4
        condicoes = {
            "igual": GAFilter.StringFilter.MatchType.EXACT,
            "contem": GAFilter.StringFilter.MatchType.CONTAINS,  # Corrigido de "contém" para "contem"
            "começa com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "termina com": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "regex": GAFilter.StringFilter.MatchType.PARTIAL_REGEXP,
            "regex completa": GAFilter.StringFilter.MatchType.FULL_REGEXP,
        }

        # Adiciona variantes sem acentos e em maiúsculas para melhorar a robustez
        condicoes_extras = {
            "contém": GAFilter.StringFilter.MatchType.CONTAINS,
            "comeca com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "comeca_com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "termina_com": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "contains": GAFilter.StringFilter.MatchType.CONTAINS,
            "begins_with": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "ends_with": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "exact": GAFilter.StringFilter.MatchType.EXACT,
            "regexp": GAFilter.StringFilter.MatchType.PARTIAL_REGEXP,
            "full_regexp": GAFilter.StringFilter.MatchType.FULL_REGEXP,
        }
        
        # Mescla os dicionários
        condicoes.update(condicoes_extras)

        print(f"DIAGNÓSTICO: Condição de filtro usada: '{filtro_condicao.lower()}'", file=sys.stderr)
        match_type = condicoes.get(filtro_condicao.lower(), GAFilter.StringFilter.MatchType.EXACT)
        print(f"DIAGNÓSTICO: Match type selecionado: {match_type}", file=sys.stderr)

        # Monta filtro se informado
        dimension_filter = None
        if filtro_campo and filtro_valor:
            dimension_filter = FilterExpression(
                filter=Filter(
                    field_name=filtro_campo.strip(),
                    string_filter=Filter.StringFilter(
                        value=filtro_valor.strip(),
                        match_type=match_type
                    )
                )
            )

        # Monta requisição com datas dinâmicas
        request = RunReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=periodo, end_date=data_fim)],  # Agora ambas são dinâmicas
            dimensions=lista_dimensoes,
            metrics=lista_metricas,
            dimension_filter=dimension_filter
        )

        print("DIAGNÓSTICO: Enviando requisição ao GA4", file=sys.stderr)
        response = client.run_report(request)
        print("DIAGNÓSTICO: Resposta recebida do GA4", file=sys.stderr)

        if not response.rows:
            return "Nenhum dado encontrado com esse filtro."

        # Cabeçalho
        headers = [d.name for d in request.dimensions] + [m.name for m in request.metrics]
        resultado = [" | ".join(headers)]

        # Limita a 30 linhas
        for row in response.rows[:100]:
            dim_vals = [d.value for d in row.dimension_values]
            met_vals = [m.value for m in row.metric_values]
            resultado.append(" | ".join(dim_vals + met_vals))

        return "\n".join(resultado)

    except Exception as e:
        print(f"ERRO na consulta GA4: {e}", file=sys.stderr)
        return f"[Erro] Consulta GA4 falhou: {e}"

def consulta_ga4_pivot(
    dimensao: str = "country",
    dimensao_pivot: str = "deviceCategory",
    metrica: str = "sessions",
    periodo: str = "7daysAgo",
    data_fim: str = "today",  # Nova variável para data final
    filtro_campo: str = "",
    filtro_valor: str = "",
    filtro_condicao: str = "igual",
    limite_linhas: int = 30,
    property_id: str = "properties/254018746"
) -> str:
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
    """
    try:
        # Verifica se o cliente está inicializado
        if client is None:
            return "Erro: Cliente GA4 não inicializado corretamente. Verifique as credenciais."
            
        print(f"DIAGNÓSTICO: Iniciando consulta GA4 Pivot - período: {periodo} a {data_fim}", file=sys.stderr)
            
        # Garante formato correto do property_id
        if not property_id.startswith("properties/"):
            property_id = f"properties/{property_id}"
            
        # Lista de todas as dimensões (tanto primária como de pivot)
        todas_dimensoes = [Dimension(name=d.strip()) for d in dimensao.split(",")]
        for d in dimensao_pivot.split(","):
            todas_dimensoes.append(Dimension(name=d.strip()))
            
        # Lista de métricas
        lista_metricas = [Metric(name=m.strip()) for m in metrica.split(",")]

        # Mapeia condição textual para enums do GA4
        condicoes = {
            "igual": GAFilter.StringFilter.MatchType.EXACT,
            "contem": GAFilter.StringFilter.MatchType.CONTAINS,  # Corrigido de "contém" para "contem"
            "começa com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "termina com": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "regex": GAFilter.StringFilter.MatchType.PARTIAL_REGEXP,
            "regex completa": GAFilter.StringFilter.MatchType.FULL_REGEXP,
        }

        # Adiciona variantes sem acentos e em maiúsculas para melhorar a robustez
        condicoes_extras = {
            "contém": GAFilter.StringFilter.MatchType.CONTAINS,
            "comeca com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "comeca_com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "termina_com": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "contains": GAFilter.StringFilter.MatchType.CONTAINS,
            "begins_with": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "ends_with": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "exact": GAFilter.StringFilter.MatchType.EXACT,
            "regexp": GAFilter.StringFilter.MatchType.PARTIAL_REGEXP,
            "full_regexp": GAFilter.StringFilter.MatchType.FULL_REGEXP,
        }
        
        # Mescla os dicionários
        condicoes.update(condicoes_extras)

        print(f"DIAGNÓSTICO: Condição de filtro usada (pivot): '{filtro_condicao.lower()}'", file=sys.stderr)
        match_type = condicoes.get(filtro_condicao.lower(), GAFilter.StringFilter.MatchType.EXACT)
        print(f"DIAGNÓSTICO: Match type selecionado (pivot): {match_type}", file=sys.stderr)

        # Monta filtro se informado
        dimension_filter = None
        if filtro_campo and filtro_valor:
            dimension_filter = FilterExpression(
                filter=Filter(
                    field_name=filtro_campo.strip(),
                    string_filter=Filter.StringFilter(
                        value=filtro_valor.strip(),
                        match_type=match_type
                    )
                )
            )

        # Cria objetos Pivot conforme exemplo da documentação
        # Primeiro pivot para dimensão principal
        pivot_principal = Pivot(
            field_names=[d.strip() for d in dimensao.split(",")],
            limit=limite_linhas
        )
        
        # Segundo pivot para a dimensão de cruzamento
        pivot_secundario = Pivot(
            field_names=[d.strip() for d in dimensao_pivot.split(",")],
            limit=limite_linhas,
            # Ordena o segundo pivot por valor de métrica descendente
            order_bys=[
                OrderBy(
                    metric=OrderBy.MetricOrderBy(
                        metric_name=lista_metricas[0].name
                    ),
                    desc=True
                )
            ]
        )

        # Monta a requisição de pivot seguindo o exemplo da documentação
        request = RunPivotReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=periodo, end_date=data_fim)],  # Agora ambas são dinâmicas
            dimensions=todas_dimensoes,  # Todas as dimensões (primária e pivot)
            metrics=lista_metricas,  # Métricas
            pivots=[pivot_principal, pivot_secundario],  # Pivots na ordem correta
            dimension_filter=dimension_filter  # Filtro opcional
        )

        # Executa a consulta de pivot
        response = client.run_pivot_report(request)
        
        # Processamento da resposta
        resultado = ["Resultados da consulta pivot:"]
        
        # Cabeçalhos das dimensões
        dimensoes = [header.name for header in response.dimension_headers]
        resultado.append(f"Dimensões: {', '.join(dimensoes)}")
        
        # Cabeçalhos das métricas
        metricas = [header.name for header in response.metric_headers]
        resultado.append(f"Métricas: {', '.join(metricas)}")
        
        # Processa cabeçalhos de pivot
        if response.pivot_headers:
            resultado.append("\nCabeçalhos de Pivot:")
            for i, pivot_header in enumerate(response.pivot_headers):
                resultado.append(f"Pivot {i+1}:")
                for j, dim_header in enumerate(pivot_header.pivot_dimension_headers):
                    valores = [dim_val.value for dim_val in dim_header.dimension_values]
                    resultado.append(f"  Cabeçalho {j+1}: {' | '.join(valores)}")
        
        # Processa linhas de dados
        if response.rows:
            resultado.append("\nDados:")
            for i, row in enumerate(response.rows[:50]):  # Limita a 50 linhas para exibição
                dim_values = [dim_val.value for dim_val in row.dimension_values]
                metric_values = [metric_val.value for metric_val in row.metric_values]
                resultado.append(f"Linha {i+1}: {' | '.join(dim_values)} => {' | '.join(metric_values)}")
        else:
            resultado.append("\nNenhum dado encontrado.")
            
        return "\n".join(resultado)

    except Exception as e:
        print(f"ERRO na consulta GA4 Pivot: {e}", file=sys.stderr)
        return f"[Erro] Consulta GA4 Pivot falhou: {str(e)}"

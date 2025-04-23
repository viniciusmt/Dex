from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    RunPivotReportRequest,
    DateRange,
    Dimension,
    Metric,
    FilterExpression,
    Filter,
    Pivot,
    OrderBy
)
from google.analytics.data_v1beta.types import Filter as GAFilter  # para acessar enums

import os
import json
from google.oauth2 import service_account

# Caminho da credencial
credentials_path = "C:/Users/Vinicius/Projetos/agent_mcp/agents/projeto-apis-408113-b4cfe422134b.json"
property_id = "properties/254018746"

credentials = service_account.Credentials.from_service_account_file(credentials_path)
client = BetaAnalyticsDataClient(credentials=credentials)




def consulta_ga4(
    dimensao: str = "country",
    metrica: str = "sessions",
    periodo: str = "7daysAgo",
    filtro_campo: str = "",
    filtro_valor: str = "",
    filtro_condicao: str = "igual"
) -> str:
    """
    Consulta sessões segmentadas por etapas do funil de cadastro para um curso ou categoria.

    Etapas:
    1. Sessões totais para o curso ou categoria
    2. Sessões com 'inscreva-se'
    3. Sessões com 'passo:1'
    4. Sessões com 'subscription cadastro'

    - curso: nome no formato 'exemplo:mba-em-gestao-empresarial'
    - categoria: ex: 'mba ou pós graduação ou curta e media duração'
    - dimensoes_extra: lista de dimensões como 'deviceCategory', 'pagePath', etc.
    """
    try:
        # Prepara dimensões e métricas
        lista_dimensoes = [Dimension(name=d.strip()) for d in dimensao.split(",")]
        lista_metricas = [Metric(name=m.strip()) for m in metrica.split(",")]

        # Mapeia condição textual para enums do GA4
        condicoes = {
            "igual": GAFilter.StringFilter.MatchType.EXACT,
            "contém": GAFilter.StringFilter.MatchType.CONTAINS,
            "começa com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "termina com": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "regex": GAFilter.StringFilter.MatchType.PARTIAL_REGEXP,
            "regex completa": GAFilter.StringFilter.MatchType.FULL_REGEXP,
        }

        match_type = condicoes.get(filtro_condicao.lower(), GAFilter.StringFilter.MatchType.EXACT)

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

        # Monta requisição
        request = RunReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=periodo, end_date="today")],
            dimensions=lista_dimensoes,
            metrics=lista_metricas,
            dimension_filter=dimension_filter
        )

        response = client.run_report(request)

        if not response.rows:
            return "Nenhum dado encontrado com esse filtro."

        # Cabeçalho
        headers = [d.name for d in request.dimensions] + [m.name for m in request.metrics]
        resultado = [" | ".join(headers)]

        # Limita a 30 linhas
        for row in response.rows[:30]:
            dim_vals = [d.value for d in row.dimension_values]
            met_vals = [m.value for m in row.metric_values]
            resultado.append(" | ".join(dim_vals + met_vals))

        return "\n".join(resultado)

    except Exception as e:
        return f"[Erro] Consulta GA4 falhou: {e}"

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
    try:
        # Lista de todas as dimensões (tanto primária como de pivot)
        todas_dimensoes = [Dimension(name=d.strip()) for d in dimensao.split(",")]
        for d in dimensao_pivot.split(","):
            todas_dimensoes.append(Dimension(name=d.strip()))
            
        # Lista de métricas
        lista_metricas = [Metric(name=m.strip()) for m in metrica.split(",")]

        # Mapeia condição textual para enums do GA4
        condicoes = {
            "igual": GAFilter.StringFilter.MatchType.EXACT,
            "contém": GAFilter.StringFilter.MatchType.CONTAINS,
            "começa com": GAFilter.StringFilter.MatchType.BEGINS_WITH,
            "termina com": GAFilter.StringFilter.MatchType.ENDS_WITH,
            "regex": GAFilter.StringFilter.MatchType.PARTIAL_REGEXP,
            "regex completa": GAFilter.StringFilter.MatchType.FULL_REGEXP,
        }

        match_type = condicoes.get(filtro_condicao.lower(), GAFilter.StringFilter.MatchType.EXACT)

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
            date_ranges=[DateRange(start_date=periodo, end_date="today")],
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
        import traceback
        return f"[Erro] Consulta GA4 Pivot falhou: {str(e)}\n{traceback.format_exc()}"
    

from pytrends.request import TrendReq

def termos_relacionados(
    termo: str,
    geo: str = "BR",
    timeframe: str = "today 12-m",
    usar_sugestao: bool = False
) -> list[str]:
    pytrends = TrendReq(hl='pt-BR', tz=360)

    try:
        termo_final = termo

        # Se ativado, tenta usar suggestions para pegar o mid
        if usar_sugestao:
            sugestoes = pytrends.suggestions(keyword=termo)
            if sugestoes:
                termo_codificado = sugestoes[0].get("mid", "")
                if termo_codificado:
                    termo_final = termo_codificado
                else:
                    return [f"Sugestão encontrada para '{termo}', mas sem 'mid' válido."]
            else:
                return [f"Nenhuma sugestão encontrada para '{termo}'."]
        
        # Build e consulta
        pytrends.build_payload([termo_final], cat=0, geo=geo, timeframe=timeframe)
        related = pytrends.related_queries()

        # Verifica as chaves retornadas, ignora diferenças de capitalização
        for chave in related:
            top = related[chave].get("top")
            if top is not None and not top.empty:
                return top["query"].tolist()

        return [f"Nenhum termo relacionado encontrado para '{termo}'."]
    
    except Exception as e:
        return [f"Erro ao buscar termos relacionados: {str(e)}"]

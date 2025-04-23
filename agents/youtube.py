from googleapiclient.discovery import build
import pandas as pd
from collections import Counter
import re
import nltk
from nltk.corpus import stopwords
from langdetect import detect, LangDetectException
import os

# Baixa apenas as stopwords
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords")

# Load the API key from environment variables instead of hardcoding
API_KEY = os.getenv("YOUTUBE_API_KEY")

def youtube_service():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY não encontrada nas variáveis de ambiente")
    return build("youtube", "v3", developerKey=API_KEY)

def extrair_termo(pergunta: str) -> str:
    # Extrai apenas o assunto da pergunta, mantendo simplicidade
    remover = [
        "o que estão falando sobre", "no youtube", "comentários sobre", "vídeos sobre",
        "me fale sobre", "quero saber sobre", "me diga sobre", "analise", "análise de"
    ]
    texto = pergunta.lower()
    for frase in remover:
        texto = texto.replace(frase, "")
    return texto.strip().capitalize()

def buscar_videos(termo, max_results=20):
    yt = youtube_service()
    res = yt.search().list(
        part="snippet",
        q=termo,
        type="video",
        maxResults=max_results,
        relevanceLanguage="pt"
    ).execute()

    videos = []
    for item in res.get("items", []):
        titulo = item["snippet"]["title"]
        try:
            if detect(titulo) == "pt":
                videos.append(item["id"]["videoId"])
        except LangDetectException:
            continue
    return videos

def buscar_comentarios(video_ids, max_por_video=5):
    yt = youtube_service()
    comentarios = []
    for vid in video_ids:
        try:
            res = yt.commentThreads().list(
                part="snippet", videoId=vid, maxResults=max_por_video
            ).execute()
            for item in res.get("items", []):
                texto = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                try:
                    if detect(texto) == "pt":
                        comentarios.append(texto)
                except:
                    continue
        except Exception:
            continue
    return comentarios

def tokenizar_texto(texto):
    return re.findall(r'\b\w{3,}\b', texto.lower(), flags=re.UNICODE)

def analisar_textos(textos):
    if not textos:
        return {
            "palavras_mais_comuns": [],
            "bigramas_mais_comuns": []
        }
    
    stop_pt = set(stopwords.words('portuguese'))
    palavras, bigramas = [], []

    for txt in textos:
        tokens = [w for w in tokenizar_texto(txt) if w not in stop_pt]
        palavras.extend(tokens)
        bigramas.extend([' '.join(tokens[i:i+2]) for i in range(len(tokens)-1)])

    return {
        "palavras_mais_comuns": Counter(palavras).most_common(10),
        "bigramas_mais_comuns": Counter(bigramas).most_common(5)
    }

def youtube_analyzer(pergunta):
    # Check if API key is available
    if not API_KEY:
        return {
            "erro": "API_KEY do YouTube não encontrada nas variáveis de ambiente",
            "termo_extraido": extrair_termo(pergunta),
            "videos_encontrados": 0,
            "comentarios_analisados": 0,
            "analise": {
                "palavras_mais_comuns": [],
                "bigramas_mais_comuns": []
            }
        }
    
    try:    
        termo = extrair_termo(pergunta)
        video_ids = buscar_videos(termo)
        
        if not video_ids:
            return {
                "termo_extraido": termo,
                "videos_encontrados": 0,
                "comentarios_analisados": 0,
                "analise": {
                    "palavras_mais_comuns": [],
                    "bigramas_mais_comuns": []
                }
            }
            
        comentarios = buscar_comentarios(video_ids)
        analise = analisar_textos(comentarios)
        return {
            "termo_extraido": termo,
            "videos_encontrados": len(video_ids),
            "comentarios_analisados": len(comentarios),
            "analise": analise
        }
    except Exception as e:
        return {
            "erro": str(e),
            "termo_extraido": extrair_termo(pergunta) if 'termo' not in locals() else termo,
            "videos_encontrados": len(video_ids) if 'video_ids' in locals() else 0,
            "comentarios_analisados": len(comentarios) if 'comentarios' in locals() else 0,
            "analise": {
                "palavras_mais_comuns": [],
                "bigramas_mais_comuns": []
            }
        }

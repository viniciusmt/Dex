from fastapi import FastAPI, APIRouter
import os
import json
import sys

# Adicione este endpoint ao seu servidor.py
@app.get("/debug/credentials")
async def debug_credentials():
    """
    Endpoint para depurar problemas de credenciais.
    Não mostra as credenciais completas, apenas informações de diagnóstico.
    """
    try:
        # Verifica se GOOGLE_CREDENTIALS existe
        google_creds = os.getenv("GOOGLE_CREDENTIALS")
        has_google_creds = google_creds is not None

        # Tenta analisar o JSON
        json_valid = False
        creds_info = {}
        if has_google_creds:
            try:
                creds_dict = json.loads(google_creds)
                json_valid = True
                
                # Extrai informações de diagnóstico (sem revelar dados sensíveis)
                if "type" in creds_dict:
                    creds_info["type"] = creds_dict["type"]
                if "project_id" in creds_dict:
                    creds_info["project_id"] = creds_dict["project_id"]
                if "client_email" in creds_dict:
                    creds_info["client_email"] = creds_dict["client_email"]
                if "private_key_id" in creds_dict:
                    creds_info["has_private_key_id"] = True
                if "private_key" in creds_dict:
                    creds_info["has_private_key"] = len(creds_dict["private_key"]) > 100
            except json.JSONDecodeError:
                json_valid = False
        
        # Verifica se YOUTUBE_API_KEY existe
        youtube_key = os.getenv("YOUTUBE_API_KEY")
        has_youtube_key = youtube_key is not None
        
        # Verifica se ANTHROPIC_API_KEY existe
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        has_claude_key = claude_key is not None

        # Retorna as informações de diagnóstico
        return {
            "environment": {
                "has_google_credentials": has_google_creds,
                "google_credentials_valid_json": json_valid,
                "google_credentials_info": creds_info,
                "has_youtube_api_key": has_youtube_key,
                "has_anthropic_api_key": has_claude_key
            }
        }
    except Exception as e:
        return {"error": str(e)}

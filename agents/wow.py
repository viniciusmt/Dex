import os
import re
import sys
import requests
import logging
from dotenv import load_dotenv
from unidecode import unidecode

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger(__name__)

load_dotenv()

def get_access_token(client_id, client_secret, region="us") -> str:
    auth_url = f"https://{region}.battle.net/oauth/token"
    data = {"grant_type": "client_credentials"}

    try:
        response = requests.post(auth_url, data=data, auth=(client_id, client_secret))
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise Exception("Token de acesso não encontrado.")
        return token
    except requests.exceptions.RequestException as e:
        raise Exception(f"[ERRO] Falha ao obter token: {e}")

def clean_guild_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unidecode(name).lower()).strip("-")

def get_guild_roster(region: str, realm_slug: str, guild_slug: str, token: str):
    url = f"https://{region}.api.blizzard.com/data/wow/guild/{realm_slug}/{guild_slug}/roster"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"namespace": f"profile-{region}", "locale": "en_US"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 401:
        raise Exception("Token inválido ou expirado (401).")
    elif response.status_code == 404:
        log.warning(f"Guilda '{guild_slug}' não encontrada no realm '{realm_slug}'.")
        return []
    response.raise_for_status()

    return response.json().get("members", [])

def get_character_profile_basic(region: str, realm_slug: str, character_name: str, token: str):
    url = f"https://{region}.api.blizzard.com/profile/wow/character/{realm_slug}/{character_name.lower()}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"namespace": f"profile-{region}", "locale": "en_US"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 404:
        safe_name = unidecode(character_name).encode("ascii", errors="ignore").decode()
        log.warning(f"Personagem '{safe_name}' não encontrado.")
        return None
    elif response.status_code == 401:
        raise Exception("Token inválido ou expirado (401).")
    response.raise_for_status()

    char = response.json()
    return {
        "name": char.get("name"),
        "level": char.get("level")
    }

def consulta_guilda_wow(guild_names: list[str], realm_slug: str = "azralon", region: str = "us", offset: int = 0, limit: int = 50, basic_only: bool = True) -> dict:
    client_id = os.getenv("WOW_CLIENT_ID")
    client_secret = os.getenv("WOW_CLIENT_SECRET")

    if not client_id or not client_secret:
        return {"erro": "Credenciais não encontradas no arquivo .env"}

    try:
        token = get_access_token(client_id, client_secret, region)
    except Exception as e:
        return {"erro": str(e)}

    results = []
    count = 0

    for guild_name in guild_names:
        guild_slug = clean_guild_name(guild_name)
        try:
            members = get_guild_roster(region, realm_slug.lower(), guild_slug, token)
        except Exception as e:
            log.error(f"[ERRO] {e}")
            continue

        for member in members:
            if count >= offset + limit:
                break
            character = member.get("character")
            if character:
                if count >= offset:
                    profile = get_character_profile_basic(region, realm_slug.lower(), character.get("name"), token)
                    if profile:
                        results.append(profile)
                count += 1

    return {
        "total": count,
        "offset": offset,
        "limit": limit,
        "results": results
    }

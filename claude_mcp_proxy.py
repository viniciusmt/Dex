import os
import json
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv()  # carrega a chave Claude do .env

CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MCP_URL = os.getenv("MCP_URL", "http://localhost:8000")

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

def claude_query_mcp(pergunta: str, tool: str):
    prompt = (
        f"Converta a seguinte pergunta para um JSON adequado para a ferramenta MCP '{tool}':\n"
        f"{pergunta}\n"
        "O JSON deve conter apenas os campos exigidos pela API (ex: dimensao, metrica, periodo, filtro_campo, filtro_valor, filtro_condicao)."
    )

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=400,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.content[0].text.strip("```json").strip("```").strip()
    try:
        payload = json.loads(content)
        res = requests.post(f"{MCP_URL}/tool/{tool}", json=payload)
        return res.json()
    except Exception as e:
        return {"erro": str(e), "json_raw": content}

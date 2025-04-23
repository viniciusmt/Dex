import json
import sys
from agents import analytics

def handle_message(message):
    method = message.get("method")

    # Responde apenas a mensagens do tipo "message"
    if method == "message":
        texto = message.get("params", {}).get("text", "").lower()
        print(f"[main.py] Mensagem recebida: {texto}", file=sys.stderr)

        if "analytics" in texto:
            resposta = analytics.responder(texto)
            return {"text": resposta.get("response", "Sem resposta.")}

        return {"text": "Nenhum comando reconhecido."}

    # Ignora o "initialize"
    return None

if __name__ == "__main__":
    while True:
        try:
            raw = input()
            message = json.loads(raw)
            response = handle_message(message)

            if response:
                print(json.dumps({
                    "jsonrpc": "2.0",
                    "id": message.get("id", 0),
                    "result": response
                }))
                sys.stdout.flush()

        except Exception as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": message.get("id", 0),
                "error": {
                    "code": -32000,
                    "message": f"Erro no MCP: {str(e)}"
                }
            }))
            print(f"[main.py ERRO] {e}", file=sys.stderr)
            sys.stdout.flush()

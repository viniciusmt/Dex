import requests
import json
import os
import sys

# Obter credenciais do Trello de variáveis de ambiente
API_KEY_TRELLO = os.getenv("TRELLO_API_KEY")
TOKEN_TRELLO = os.getenv("TRELLO_TOKEN")

def log_debug(message):
    """Função para log de depuração."""
    print(f"TRELLO DEBUG: {message}", file=sys.stderr)

def verificar_credenciais():
    """Verifica se as credenciais do Trello estão configuradas."""
    if not API_KEY_TRELLO or not TOKEN_TRELLO:
        log_debug("Credenciais do Trello não configuradas corretamente")
        return False
    return True

def listar_quadros():
    """
    Lista todos os quadros do Trello do usuário.
    
    Returns:
        dict: Informações sobre quadros disponíveis
    """
    if not verificar_credenciais():
        return {
            "sucesso": False,
            "mensagem": "Credenciais do Trello não configuradas corretamente"
        }
    
    try:
        url = "https://api.trello.com/1/members/me/boards"
        params = {
            'key': API_KEY_TRELLO,
            'token': TOKEN_TRELLO
        }
        
        log_debug(f"Enviando requisição para {url}")
        response = requests.get(url, params=params)
        response.raise_for_status()  # Lança exceção para erros HTTP
        
        boards = response.json()
        log_debug(f"Encontrados {len(boards)} quadros")
        
        result = {
            "sucesso": True,
            "mensagem": f"Encontrados {len(boards)} quadros",
            "quadros": []
        }
        
        for board in boards:
            result["quadros"].append({
                "id": board.get('id'),
                "nome": board.get('name'),
                "url": board.get('url')
            })
        
        return result
    
    except Exception as e:
        log_debug(f"Erro ao listar quadros: {str(e)}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao listar quadros: {str(e)}"
        }

def listar_listas(board_id):
    """
    Lista todas as listas (colunas) de um quadro do Trello.
    
    Args:
        board_id: ID do quadro do Trello
        
    Returns:
        dict: Informações sobre as listas do quadro
    """
    if not verificar_credenciais():
        return {
            "sucesso": False,
            "mensagem": "Credenciais do Trello não configuradas corretamente"
        }
    
    try:
        url = f"https://api.trello.com/1/boards/{board_id}/lists"
        params = {
            'key': API_KEY_TRELLO,
            'token': TOKEN_TRELLO
        }
        
        log_debug(f"Enviando requisição para {url}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        lists = response.json()
        log_debug(f"Encontradas {len(lists)} listas no quadro {board_id}")
        
        result = {
            "sucesso": True,
            "mensagem": f"Encontradas {len(lists)} listas",
            "listas": []
        }
        
        for lst in lists:
            result["listas"].append({
                "id": lst.get('id'),
                "nome": lst.get('name'),
                "posicao": lst.get('pos')
            })
        
        return result
    
    except Exception as e:
        log_debug(f"Erro ao listar listas do quadro {board_id}: {str(e)}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao listar listas: {str(e)}"
        }

def listar_cartoes(list_id):
    """
    Lista todos os cartões (tarefas) de uma lista do Trello.
    
    Args:
        list_id: ID da lista do Trello
        
    Returns:
        dict: Informações sobre os cartões da lista
    """
    if not verificar_credenciais():
        return {
            "sucesso": False,
            "mensagem": "Credenciais do Trello não configuradas corretamente"
        }
    
    try:
        url = f"https://api.trello.com/1/lists/{list_id}/cards"
        params = {
            'key': API_KEY_TRELLO,
            'token': TOKEN_TRELLO
        }
        
        log_debug(f"Enviando requisição para {url}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        cards = response.json()
        log_debug(f"Encontrados {len(cards)} cartões na lista {list_id}")
        
        result = {
            "sucesso": True,
            "mensagem": f"Encontrados {len(cards)} cartões",
            "cartoes": []
        }
        
        for card in cards:
            labels = []
            for label in card.get('labels', []):
                if label.get('name'):
                    labels.append({
                        "id": label.get('id'),
                        "nome": label.get('name'),
                        "cor": label.get('color')
                    })
            
            result["cartoes"].append({
                "id": card.get('id'),
                "nome": card.get('name'),
                "descricao": card.get('desc'),
                "url": card.get('url'),
                "data_vencimento": card.get('due'),
                "etiquetas": labels
            })
        
        return result
    
    except Exception as e:
        log_debug(f"Erro ao listar cartões da lista {list_id}: {str(e)}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao listar cartões: {str(e)}"
        }

def criar_cartao(list_id, nome, descricao=""):
    """
    Cria um novo cartão (tarefa) em uma lista do Trello.
    
    Args:
        list_id: ID da lista onde o cartão será criado
        nome: Nome do cartão/tarefa
        descricao: Descrição do cartão (opcional)
        
    Returns:
        dict: Informações sobre o cartão criado
    """
    if not verificar_credenciais():
        return {
            "sucesso": False,
            "mensagem": "Credenciais do Trello não configuradas corretamente"
        }
    
    try:
        url = "https://api.trello.com/1/cards"
        params = {
            'key': API_KEY_TRELLO,
            'token': TOKEN_TRELLO,
            'idList': list_id,
            'name': nome,
            'desc': descricao
        }
        
        log_debug(f"Criando cartão '{nome}' na lista {list_id}")
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        card = response.json()
        log_debug(f"Cartão criado com ID: {card.get('id')}")
        
        return {
            "sucesso": True,
            "mensagem": f"Cartão '{nome}' criado com sucesso",
            "cartao": {
                "id": card.get('id'),
                "nome": card.get('name'),
                "url": card.get('url')
            }
        }
    
    except Exception as e:
        log_debug(f"Erro ao criar cartão na lista {list_id}: {str(e)}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao criar cartão: {str(e)}"
        }

def mover_cartao(card_id, list_id):
    """
    Move um cartão (tarefa) para outra lista no Trello.
    
    Args:
        card_id: ID do cartão a ser movido
        list_id: ID da lista de destino
        
    Returns:
        dict: Informações sobre o resultado da operação
    """
    if not verificar_credenciais():
        return {
            "sucesso": False,
            "mensagem": "Credenciais do Trello não configuradas corretamente"
        }
    
    try:
        url = f"https://api.trello.com/1/cards/{card_id}"
        params = {
            'key': API_KEY_TRELLO,
            'token': TOKEN_TRELLO,
            'idList': list_id
        }
        
        log_debug(f"Movendo cartão {card_id} para lista {list_id}")
        response = requests.put(url, params=params)
        response.raise_for_status()
        
        card = response.json()
        log_debug(f"Cartão {card.get('id')} movido com sucesso")
        
        return {
            "sucesso": True,
            "mensagem": f"Cartão movido com sucesso",
            "cartao": {
                "id": card.get('id'),
                "nome": card.get('name'),
                "nova_lista_id": list_id
            }
        }
    
    except Exception as e:
        log_debug(f"Erro ao mover cartão {card_id} para lista {list_id}: {str(e)}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao mover cartão: {str(e)}"
        }

def listar_tarefas_quadro(board_id):
    """
    Lista todas as tarefas de um quadro do Trello organizadas por lista.
    
    Args:
        board_id: ID do quadro do Trello
        
    Returns:
        dict: Todas as tarefas organizadas por lista
    """
    if not verificar_credenciais():
        return {
            "sucesso": False,
            "mensagem": "Credenciais do Trello não configuradas corretamente"
        }
    
    try:
        # Primeiro, obtém todas as listas do quadro
        listas_resultado = listar_listas(board_id)
        
        if not listas_resultado["sucesso"]:
            return listas_resultado
            
        listas = listas_resultado["listas"]
        log_debug(f"Processando {len(listas)} listas para o quadro {board_id}")
        
        # Cria o resultado final
        result = {
            "sucesso": True,
            "mensagem": f"Tarefas do quadro organizadas por lista",
            "tarefas_por_lista": []
        }
        
        # Para cada lista, obtém seus cartões
        for lista in listas:
            cartoes_resultado = listar_cartoes(lista["id"])
            
            if not cartoes_resultado["sucesso"]:
                log_debug(f"Erro ao listar cartões da lista {lista['nome']}: {cartoes_resultado['mensagem']}")
                continue
                
            result["tarefas_por_lista"].append({
                "lista_id": lista["id"],
                "lista_nome": lista["nome"],
                "cartoes": cartoes_resultado["cartoes"]
            })
        
        return result
        
    except Exception as e:
        log_debug(f"Erro ao listar tarefas do quadro {board_id}: {str(e)}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao listar tarefas do quadro: {str(e)}"
        }

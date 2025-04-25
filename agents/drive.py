import os
import json
import sys
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import pandas as pd
from typing import List, Dict, Any, Optional

# Configuração de diagnóstico e logging
def log_debug(message):
    print(f"DRIVE DEBUG: {message}", file=sys.stderr)

def init_drive_client():
    try:
        # Lê credenciais do JSON como string (vinda de variável de ambiente)
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            log_debug("ERRO: Variável GOOGLE_CREDENTIALS não encontrada")
            return None
            
        # Tenta analisar o JSON
        try:
            creds_dict = json.loads(creds_json)
            log_debug(f"JSON analisado com sucesso. Tipo da conta: {creds_dict.get('type')}")
            log_debug(f"Email da conta: {creds_dict.get('client_email')}")
        except json.JSONDecodeError as e:
            log_debug(f"Falha ao analisar JSON das credenciais: {e}")
            return None
            
        # Cria as credenciais com escopos específicos para Drive e Sheets
        SCOPES = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        
        try:
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES)
            log_debug("Credenciais criadas com sucesso")
        except Exception as e:
            log_debug(f"Falha ao criar credenciais: {e}")
            return None
            
        # Cria os serviços
        try:
            drive_service = build('drive', 'v3', credentials=credentials)
            sheets_service = build('sheets', 'v4', credentials=credentials)
            log_debug("Serviços Drive e Sheets criados com sucesso")
            return {
                'drive': drive_service,
                'sheets': sheets_service
            }
        except Exception as e:
            log_debug(f"Falha ao criar serviços: {e}")
            return None
    except Exception as e:
        log_debug(f"ERRO GERAL: {e}")
        return None

# Inicializa os serviços uma vez
services = init_drive_client()

# 1. Criar planilha do zero
def criar_planilha(nome_planilha: str, email_compartilhamento: str = "vinicius.matsumoto@fgv.br") -> Dict[str, Any]:
    """
    Cria uma nova planilha no Google Drive e a compartilha com o email especificado.
    
    Args:
        nome_planilha: Nome da nova planilha
        email_compartilhamento: Email com quem compartilhar (padrão: vinicius.matsumoto@fgv.br)
        
    Returns:
        Dicionário com informações da planilha criada
    """
    try:
        if not services:
            return {"erro": "Serviços Drive não inicializados corretamente"}
        
        drive_service = services['drive']
        sheets_service = services['sheets']
        
        # Cria a planilha
        spreadsheet_body = {
            'properties': {
                'title': nome_planilha
            },
            'sheets': [
                {
                    'properties': {
                        'title': 'Principal',
                        'gridProperties': {
                            'rowCount': 100,
                            'columnCount': 20
                        }
                    }
                }
            ]
        }
        
        log_debug(f"Criando planilha: {nome_planilha}")
        spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet_body).execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        log_debug(f"Planilha criada com ID: {spreadsheet_id}")
        
        # Compartilha a planilha
        if email_compartilhamento:
            user_permission = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': email_compartilhamento
            }
            
            log_debug(f"Compartilhando planilha com: {email_compartilhamento}")
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=user_permission,
                fields='id',
                sendNotificationEmail=False
            ).execute()
            log_debug("Planilha compartilhada com sucesso")
        
        # Retorna informações sobre a planilha criada
        return {
            "sucesso": True,
            "mensagem": f"Planilha '{nome_planilha}' criada com sucesso",
            "planilha_id": spreadsheet_id,
            "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
            "compartilhada_com": email_compartilhamento
        }
        
    except Exception as e:
        log_debug(f"Erro ao criar planilha: {str(e)}")
        return {
            "sucesso": False,
            "erro": str(e)
        }

# 2. Listar planilhas
def listar_planilhas(limite: int = 20) -> Dict[str, Any]:
    """
    Lista todas as planilhas às quais a conta de serviço tem acesso.
    
    Args:
        limite: Número máximo de planilhas a listar
        
    Returns:
        Dicionário com lista de planilhas
    """
    try:
        if not services:
            return {"erro": "Serviços Drive não inicializados corretamente"}
            
        drive_service = services['drive']
        
        # Consulta apenas arquivos do tipo spreadsheet
        query = "mimeType='application/vnd.google-apps.spreadsheet'"
        
        log_debug(f"Listando até {limite} planilhas")
        results = drive_service.files().list(
            q=query,
            pageSize=limite,
            fields="nextPageToken, files(id, name, webViewLink, owners, permissions, createdTime)"
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            log_debug("Nenhuma planilha encontrada")
            return {
                "sucesso": True,
                "mensagem": "Nenhuma planilha encontrada",
                "planilhas": []
            }
            
        # Formata os resultados
        planilhas = []
        for item in items:
            planilha = {
                "id": item['id'],
                "nome": item['name'],
                "url": f"https://docs.google.com/spreadsheets/d/{item['id']}/edit",
                "data_criacao": item.get('createdTime', '')
            }
            
            # Adiciona informações de proprietário se disponíveis
            if 'owners' in item and item['owners']:
                owner = item['owners'][0]
                planilha['proprietario'] = {
                    "nome": owner.get('displayName', ''),
                    "email": owner.get('emailAddress', '')
                }
                
            planilhas.append(planilha)
            
        log_debug(f"Encontradas {len(planilhas)} planilhas")
        return {
            "sucesso": True,
            "mensagem": f"Encontradas {len(planilhas)} planilhas",
            "planilhas": planilhas
        }
        
    except Exception as e:
        log_debug(f"Erro ao listar planilhas: {str(e)}")
        return {
            "sucesso": False,
            "erro": str(e)
        }

# 3. Criar novas abas (sheets) em uma planilha existente
def criar_nova_aba(
    planilha_id: str, 
    nome_aba: str, 
    linhas: int = 100, 
    colunas: int = 20
) -> Dict[str, Any]:
    """
    Cria uma nova aba em uma planilha existente.
    
    Args:
        planilha_id: ID da planilha no Google Drive
        nome_aba: Nome da nova aba
        linhas: Número de linhas na nova aba
        colunas: Número de colunas na nova aba
        
    Returns:
        Dicionário com informações da operação
    """
    try:
        if not services:
            return {"erro": "Serviços Sheets não inicializados corretamente"}
            
        sheets_service = services['sheets']
        
        # Verifica se a planilha existe e é acessível
        try:
            log_debug(f"Verificando acesso à planilha: {planilha_id}")
            sheets_service.spreadsheets().get(spreadsheetId=planilha_id).execute()
        except HttpError as e:
            log_debug(f"Erro ao acessar planilha: {str(e)}")
            return {
                "sucesso": False,
                "erro": f"Não foi possível acessar a planilha: {str(e)}"
            }
        
        # Cria a nova aba
        body = {
            'requests': [
                {
                    'addSheet': {
                        'properties': {
                            'title': nome_aba,
                            'gridProperties': {
                                'rowCount': linhas,
                                'columnCount': colunas
                            }
                        }
                    }
                }
            ]
        }
        
        log_debug(f"Criando nova aba '{nome_aba}' na planilha {planilha_id}")
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=planilha_id,
            body=body
        ).execute()
        
        # Extrai o ID da nova aba criada
        sheet_id = None
        if 'replies' in response and response['replies']:
            if 'addSheet' in response['replies'][0]:
                sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        
        log_debug(f"Nova aba criada com ID interno: {sheet_id}")
        return {
            "sucesso": True,
            "mensagem": f"Aba '{nome_aba}' criada com sucesso",
            "planilha_id": planilha_id,
            "aba_nome": nome_aba,
            "aba_id": sheet_id,
            "url": f"https://docs.google.com/spreadsheets/d/{planilha_id}/edit#gid={sheet_id}"
        }
        
    except HttpError as e:
        # Trata especificamente o erro de aba com nome duplicado
        if "already exists" in str(e):
            log_debug(f"Erro: Já existe uma aba com o nome '{nome_aba}'")
            return {
                "sucesso": False,
                "erro": f"Já existe uma aba com o nome '{nome_aba}'"
            }
        log_debug(f"Erro HTTP ao criar aba: {str(e)}")
        return {
            "sucesso": False,
            "erro": str(e)
        }
    except Exception as e:
        log_debug(f"Erro ao criar aba: {str(e)}")
        return {
            "sucesso": False,
            "erro": str(e)
        }

# 4. Sobrescrever conteúdo de uma aba
def sobrescrever_aba(
    planilha_id: str,
    nome_aba: str,
    dados: List[List[Any]]
) -> Dict[str, Any]:
    """
    Sobrescreve completamente o conteúdo de uma aba existente.
    
    Args:
        planilha_id: ID da planilha no Google Drive
        nome_aba: Nome da aba a ser sobrescrita
        dados: Lista de listas contendo os dados a serem escritos
        
    Returns:
        Dicionário com informações da operação
    """
    try:
        if not services:
            return {"erro": "Serviços Sheets não inicializados corretamente"}
            
        sheets_service = services['sheets']
        
        # Verifica se a planilha existe e é acessível
        try:
            log_debug(f"Verificando acesso à planilha: {planilha_id}")
            planilha_info = sheets_service.spreadsheets().get(spreadsheetId=planilha_id).execute()
            
            # Verifica se a aba especificada existe
            aba_encontrada = False
            for sheet in planilha_info.get('sheets', []):
                if sheet['properties']['title'] == nome_aba:
                    aba_encontrada = True
                    break
                    
            if not aba_encontrada:
                log_debug(f"Aba '{nome_aba}' não encontrada")
                return {
                    "sucesso": False,
                    "erro": f"Aba '{nome_aba}' não encontrada na planilha"
                }
                
        except HttpError as e:
            log_debug(f"Erro ao acessar planilha: {str(e)}")
            return {
                "sucesso": False,
                "erro": f"Não foi possível acessar a planilha: {str(e)}"
            }
        
        # Define o intervalo para toda a aba
        range_name = f"{nome_aba}"
        
        # Prepara os dados para envio
        log_debug(f"Enviando {len(dados)} linhas de dados para {nome_aba}")
        body = {
            'values': dados
        }
        
        # Limpa todos os dados existentes e escreve os novos
        sheets_service.spreadsheets().values().clear(
            spreadsheetId=planilha_id,
            range=range_name
        ).execute()
        
        log_debug(f"Sobrescrevendo dados na aba '{nome_aba}'")
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=planilha_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        log_debug(f"Dados sobrescritos: {result.get('updatedCells')} células atualizadas")
        return {
            "sucesso": True,
            "mensagem": f"Dados sobrescritos na aba '{nome_aba}'",
            "planilha_id": planilha_id,
            "aba_nome": nome_aba,
            "celulas_atualizadas": result.get('updatedCells'),
            "url": f"https://docs.google.com/spreadsheets/d/{planilha_id}/edit#gid=0"
        }
        
    except Exception as e:
        log_debug(f"Erro ao sobrescrever aba: {str(e)}")
        return {
            "sucesso": False,
            "erro": str(e)
        }

# 5. Adicionar células (append) a uma planilha
def adicionar_celulas(
    planilha_id: str,
    nome_aba: str,
    dados: List[List[Any]]
) -> Dict[str, Any]:
    """
    Adiciona dados a uma aba existente, sem sobrescrever dados existentes.
    
    Args:
        planilha_id: ID da planilha no Google Drive
        nome_aba: Nome da aba onde adicionar dados
        dados: Lista de listas contendo os dados a serem adicionados
        
    Returns:
        Dicionário com informações da operação
    """
    try:
        if not services:
            return {"erro": "Serviços Sheets não inicializados corretamente"}
            
        sheets_service = services['sheets']
        
        # Verifica se a planilha existe e é acessível
        try:
            log_debug(f"Verificando acesso à planilha: {planilha_id}")
            planilha_info = sheets_service.spreadsheets().get(spreadsheetId=planilha_id).execute()
            
            # Verifica se a aba especificada existe
            aba_encontrada = False
            for sheet in planilha_info.get('sheets', []):
                if sheet['properties']['title'] == nome_aba:
                    aba_encontrada = True
                    break
                    
            if not aba_encontrada:
                log_debug(f"Aba '{nome_aba}' não encontrada")
                return {
                    "sucesso": False,
                    "erro": f"Aba '{nome_aba}' não encontrada na planilha"
                }
                
        except HttpError as e:
            log_debug(f"Erro ao acessar planilha: {str(e)}")
            return {
                "sucesso": False,
                "erro": f"Não foi possível acessar a planilha: {str(e)}"
            }
        
        # Define o intervalo para a aba
        range_name = f"{nome_aba}"
        
        # Prepara os dados para envio
        log_debug(f"Adicionando {len(dados)} linhas de dados para {nome_aba}")
        body = {
            'values': dados
        }
        
        # Adiciona os dados no final da planilha
        log_debug(f"Adicionando dados à aba '{nome_aba}'")
        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=planilha_id,
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        # Extrair informações da operação
        updated_range = result.get('updates', {}).get('updatedRange', '')
        updated_cells = result.get('updates', {}).get('updatedCells', 0)
        
        log_debug(f"Dados adicionados: {updated_cells} células no intervalo {updated_range}")
        return {
            "sucesso": True,
            "mensagem": f"Dados adicionados à aba '{nome_aba}'",
            "planilha_id": planilha_id,
            "aba_nome": nome_aba,
            "celulas_adicionadas": updated_cells,
            "intervalo_atualizado": updated_range,
            "url": f"https://docs.google.com/spreadsheets/d/{planilha_id}/edit#gid=0"
        }
        
    except Exception as e:
        log_debug(f"Erro ao adicionar células: {str(e)}")
        return {
            "sucesso": False,
            "erro": str(e)
        }

# Função auxiliar para converter dataframes do pandas para o formato esperado pelas funções acima
def dataframe_para_lista(df: pd.DataFrame) -> List[List[Any]]:
    """
    Converte um DataFrame do pandas para o formato de lista de listas
    usado pelas funções de planilhas Google.
    
    Args:
        df: DataFrame do pandas
        
    Returns:
        Lista de listas com os dados do DataFrame, incluindo cabeçalhos
    """
    # Obtém as colunas como primeira linha
    headers = df.columns.tolist()
    
    # Converte os dados para listas
    data = df.values.tolist()
    
    # Retorna cabeçalhos + dados
    return [headers] + data

# Função para converter uma string JSON ou CSV para o formato de lista de listas
def dados_para_lista(dados: str, formato: str = "auto") -> List[List[Any]]:
    """
    Converte uma string JSON ou CSV para o formato de lista de listas
    usado pelas funções de planilhas Google.
    
    Args:
        dados: String contendo dados em formato JSON ou CSV
        formato: "json", "csv" ou "auto" para detecção automática
        
    Returns:
        Lista de listas com os dados convertidos
    """
    if formato == "auto":
        # Tentativa de detecção automática
        dados = dados.strip()
        if dados.startswith('[') and dados.endswith(']'):
            formato = "json"
        else:
            formato = "csv"
    
    try:
        if formato == "json":
            # Tenta interpretar como JSON
            json_data = json.loads(dados)
            
            # Se for uma lista de dicionários, converte para DataFrame e depois para lista
            if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict):
                df = pd.DataFrame(json_data)
                return dataframe_para_lista(df)
            
            # Se for uma lista de listas, retorna diretamente
            elif isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], list):
                return json_data
            
            # Caso contrário, cria um DataFrame com uma única coluna
            else:
                df = pd.DataFrame({'dados': [json_data]})
                return dataframe_para_lista(df)
                
        elif formato == "csv":
            # Tenta interpretar como CSV
            df = pd.read_csv(pd.StringIO(dados))
            return dataframe_para_lista(df)
            
        else:
            raise ValueError(f"Formato desconhecido: {formato}")
            
    except Exception as e:
        log_debug(f"Erro ao converter dados: {str(e)}")
        # Retorna uma matriz com uma mensagem de erro
        return [["Erro ao processar dados", str(e)]]

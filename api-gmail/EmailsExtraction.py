#python3 -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

import base64
import json
import os.path
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path

import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Escopos de acesso/ExtractEmais.py
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Definição dos caminhos (ajuste se necessário)

PATH_BASE = Path.cwd()/'api-gmail'  # diretório base do projeto (ajuste se necessário)
print(f"Diretório de trabalho: {PATH_BASE}")
TOKEN = PATH_BASE / "token.json"  # arquivo onde o token de acesso será salvo
CREDENTIAL = PATH_BASE / "credential.json"

# diretório onde os anexos serão gravados. fica dentro de `data/attachments`.
# garantimos que a hierarquia exista no momento da importação/executação.

DOWNLOAD_DIR = PATH_BASE / "data"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# estrutura de dados geral dentro do diretório de trabalho
PROCESSED_IDS_PATH = PATH_BASE / "data"

def get_gmail_service():
    """Autentica e retorna o serviço da Gmail API."""
    creds = None

    # Carrega token existente, se houver
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)

    # Se não há credenciais válidas, faz login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIAL):
                print(f"Erro: arquivo de credenciais não encontrado: {CREDENTIAL}")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIAL, SCOPES)
            creds = flow.run_local_server(port=0)

        # Salva o token para a próxima execução
        with open(TOKEN, "w") as token:
            token.write(creds.to_json())

    try:
        # Testa a autenticação listando as labels
        service = build("gmail", "v1", credentials=creds)
        service.users().labels().list(userId="me").execute()
        print("Autenticação bem-sucedida!")
        return service
    except HttpError as error:
        print(f"Falha ao autenticar o serviço do Gmail: {error}")
        return None

def build_query(days_back=None, has_attachments=None, from_email=None, format=None):
    """
    Constrói a query de busca para a Gmail API com base nos filtros fornecidos.
    
    Args:
        days_back: Número de dias para trás (se None, busca todos).
        has_attachments: Se True, filtra apenas e-mails com anexos. Se False, filtra apenas sem anexos. Se None, sem filtro.
        from_email: E-mail do remetente para filtrar (se None, sem filtro).
        format: Formato do arquivo para filtrar (se None, sem filtro).
    
    Returns:
        String de query para a Gmail API.
    """

    if days_back is not None and days_back < 0:
        print("Aviso: 'days_back' não pode ser negativo. Ignorando este filtro.")
        days_back = None

    query_parts = ["in:inbox"]

    if days_back is not None:
        query_parts.append(f"newer_than:{days_back}d")

    if has_attachments == 'True':
        query_parts.append("has:attachment")
    elif has_attachments == 'False':
        query_parts.append("-has:attachment")

    if from_email is not None:
        query_parts.append(f"from:{from_email}")

    if format is not None:
        query_parts.append(f"filename:{format}")

    return " ".join(query_parts)

def paginate_results(service, query, max_results=None):
    """
    Gerencia a paginação dos resultados da Gmail API.
    
    Args:
        service: Serviço autenticado da Gmail API.
        query: String de query para a busca.
        max_results: Número máximo de IDs a retornar (se None, busca todos via paginação).

    Returns:
        Lista de IDs (strings).
    """
    if max_results is not None and max_results <= 0:
        print("Aviso: 'max_results' deve ser um número positivo. Ignorando este filtro.")
        max_results = None  
        
    all_ids = []
    page_token = None
    page_size = 500

    if max_results is not None and max_results < page_size:
        page_size = max_results

    while True:
        try:
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=page_size,
                pageToken=page_token
            ).execute()
        except HttpError as error:
            print(f"Erro na chamada da API: {error}")
            break

        messages = results.get('messages', [])

        if messages:
            ids = [msg['id'] for msg in messages]
            all_ids.extend(ids)

        if max_results is not None and len(all_ids) >= max_results:
            return all_ids[:max_results]

        page_token = results.get('nextPageToken')
        if not page_token:
            break
        
    return all_ids

def fetch_email_ids(service, days_back=None, max_results=None, has_attachments=None, from_email=None, format=None):
    """
    Busca IDs de e-mails da caixa de entrada com filtros opcionais.
    
    Args:
        service: Serviço autenticado da Gmail API.
        days_back: Número de dias para trás (se None, busca todos).
        max_results: Número máximo de IDs a retornar (se None, busca todos via paginação).
        has_attachments: Se True, filtra apenas e-mails com anexos.
        format: Formato do arquivo (csv, json).
    
    Returns:
        Lista de IDs (strings).
    """
    
    print(f'''Filtros aplicados: 
          days_back={days_back} dias, 
          max_results={max_results}, 
          has_attachments={has_attachments}, 
          from_email={from_email}, 
          format={format}''')
    
    if service is None:
        print("Serviço não disponível.")
        return []

    all_ids = []
    page_token = None
    
    query = build_query(days_back, has_attachments, from_email, format)

    print(f"Query de busca: {query}")

    all_ids = paginate_results(service, query, max_results)
    
    return all_ids

def save_processed_ids(processed_ids):
    """
    Salva o conjunto de IDs processados no arquivo JSON.
    
    Args:
        processed_ids: Conjunto de IDs processados (set ou list).
    """
    
    # Garante que o diretório existe
    PROCESSED_IDS_PATH = Path(DOWNLOAD_DIR)
    PROCESSED_IDS_PATH.mkdir(parents=True, exist_ok=True)   
    print(f"Salvando IDs processados em no diretório {PROCESSED_IDS_PATH / 'processed_ids.json'}")
    
    with open(Path(PROCESSED_IDS_PATH) / "processed_ids.json", 'w') as f:
        json.dump(list(processed_ids), f, indent=2)

def download_attachments(service, message_id):
    """
    Baixa todos os anexos de uma mensagem específica do Gmail.
    
    Args:
        service: Serviço autenticado da Gmail API.
        message_id: ID da mensagem (string).
    
    Returns:
        Lista de caminhos dos arquivos baixados (strings).
    """
    downloaded_files = []
    
    try:
        # 1. Obtém a mensagem completa com formato 'full' para ter acesso aos parts
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        
        # 2. Cria o diretório de download se não existir
        download_dir=Path(DOWNLOAD_DIR)/"attachments"
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Função recursiva para percorrer as partes da mensagem
        def _process_parts(parts, parent_path=""):
            """Processa recursivamente as partes da mensagem para encontrar anexos.
            
            A função percorre as partes da mensagem, verificando se cada parte é um anexo (verificando a presença de 'filename').
            Se for um anexo, ela baixa o arquivo usando o 'attachmentId' e salva no diretório especificado. Se a parte tiver subpartes (indicando uma estrutura de mensagem
            """

            nonlocal downloaded_files
            
            if not parts:
                return
            
            for part in parts:
                # Verifica se esta parte tem filename (é um anexo)
                if 'filename' in part and part['filename']:
                    filename = part['filename']
                    
                    # Constrói caminho seguro para o arquivo
                    safe_filename = filename.replace('/', '_').replace('\\', '_')
                    filepath = os.path.join(download_dir, safe_filename)
                    
                    # Evita sobrescrever arquivos com nomes iguais
                    if os.path.exists(filepath):
                        base, ext = os.path.splitext(safe_filename)
                        counter = 1
                        while os.path.exists(filepath):
                            new_filename = f"{base}_{counter}{ext}"
                            filepath = os.path.join(download_dir, new_filename)
                            counter += 1
                    
                    # Obtém o attachmentId
                    if 'body' in part and 'attachmentId' in part['body']:
                        attachment_id = part['body']['attachmentId']
                        
                        try:
                            # 4. Baixa o anexo usando attachments().get()
                            attachment = service.users().messages().attachments().get(
                                userId='me',
                                messageId=message_id,
                                id=attachment_id
                            ).execute()
                            
                            # 5. Decodifica os dados (base64url) 
                            file_data = base64.urlsafe_b64decode(attachment['data'])
                            
                            # 6. Salva o arquivo
                            with open(filepath, 'wb') as f:
                                f.write(file_data)
                            
                            print(f" Anexo salvo: {filepath}")
                            downloaded_files.append(filepath)
                            
                        except HttpError as e:
                            print(f"  Erro ao baixar anexo {filename}: {e}")
                        except Exception as e:
                            print(f"  Erro inesperado ao baixar {filename}: {e}")
                
                # Processa recursivamente subpartes (mensagens com partes aninhadas)
                if 'parts' in part:
                    _process_parts(part['parts'], parent_path)
        
        # Inicia o processamento a partir do payload principal
        if 'payload' in message:
            payload = message['payload']
            
            # Se o payload principal já for um anexo
            if 'filename' in payload and payload['filename']:
                _process_parts([payload])
            # Se tiver partes, processa-as
            elif 'parts' in payload:
                _process_parts(payload['parts'])
        
        return downloaded_files
        
    except HttpError as error:
        print(f"Erro na API ao processar mensagem {message_id}: {error}")
        return []
    except Exception as error:
        print(f"Erro inesperado: {error}")
        return []

def main():
     
    parser = ArgumentParser(
        description='Extrai os anexos dos e-mails da caixa de entrada do Gmail e os salva em um diretório.',
        formatter_class=ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--max_results',
        type=int,
        default=None,
        help='Número máximo de e-mails a processar (padrão: todos)'
    )

    parser.add_argument(
        '--days_back',
        type=int,
        default=None,
        help='Número de dias para trás a partir da data atual para buscar e-mails (padrão: todos)'
    )

    parser.add_argument(
        '--has_attachments',
        choices=['True', 'False'],
        default=None,
        help='True: apenas com anexos. False: apenas sem anexos. Omitido sem filtro (padrão: nenhum filtro)'
    )

    parser.add_argument(
        '--from_email',
        type=str,
        default=None,
        help='E-mail do remetente (padrão: nenhum filtro)'
    )

    parser.add_argument(
        '--format',
        type=str,
        default=None,
        help='Tipo de exportação (csv, json) (padrão: nenhum filtro)'
    )

    args = parser.parse_args()

    print(f"Argumentos recebidos: {args}")

    # Obtém serviço autenticado
    service = get_gmail_service()
    print(f"Serviço do Gmail obtido: {'Sim' if service else 'Não'}")

    if service is None:
        print("Não foi possível autenticar o serviço do Gmail. Verifique as credenciais e tente novamente.")
        return  # encerra se não conseguiu autenticar

    # Busca os IDs com os filtros
    print("\n Buscando IDs de e-mails com os filtros aplicados...")

    ids = fetch_email_ids(
        service,
        days_back=args.days_back,
        max_results=args.max_results,
        has_attachments=args.has_attachments,
        from_email=args.from_email,
        format=args.format
    )

    print(f"\n Foram encontrados {len(ids)} e-mails com os filtros aplicados.")

    if not ids:
        print("Nenhum ID encontrado com os filtros atuais.")
        return  # encerra a função se não houver IDs

    print("\n Baixando anexos...")
    all_downloaded = []

    # garante que o diretório de download solicitado existe
    downloads_dir_path = Path(DOWNLOAD_DIR)/"attachments"
    downloads_dir_path.mkdir(parents=True, exist_ok=True)

    for i, msg_id in enumerate(ids, 1):
        print(f"\nProcessando e-mail {i}/{len(ids)} (ID: {msg_id})")
        downloaded = download_attachments(
            service,
            msg_id
        )
        all_downloaded.extend(downloaded)
        # Pequena pausa para não sobrecarregar a API
        if i < len(ids):
            time.sleep(0.5)

    print(f"\n Total de anexos baixados: {len(all_downloaded)}")

    # Salva os IDs processados (opcional)
    save_processed_ids(ids)

if __name__ == "__main__":
    main()
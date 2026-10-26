from TenhouLog import get_log

import os.path
import json
import re
import database as db

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def result(logs):
    players = []

    for log in logs:
        score = []
        j_log = get_log(log)
        sc = j_log['sc']
        names = j_log['name']

        for i in range(4):
            score.append(sc[i*2])

        organizado = sorted(score, reverse=True)

        for i in range(4):
            player = []
            player.append(names[i])
            player.append(score[i])
            for j in range(4):
                if score[i] == organizado[j]:
                    player.append(j+1)
                    break
            players.append(player)

    return players

def formatacao(players, fase, numero, tabela):
    range_celulas = ''
    linhas_formatadas = []

    for linha in tabela:
        r = []
        v = False
        for player in players:
            if len(linha) > 1 and linha[1] == player[0]:
                v = True
                if fase == 'Classificatória':
                    r = [player[1], player[2]]
                    linhas_formatadas.append(r)
                    if numero == "1": range_celulas = 'Classificatória!D4:E'
                    elif numero == "2": range_celulas = 'Classificatória!H4:I'
                    elif numero == "3": range_celulas = 'Classificatória!L4:M'
                    elif numero == "4": range_celulas = 'Classificatória!P4:Q'
                elif fase == 'Semifinais':
                    range_celulas = 'Semifinais!C4'
                    r = [player[1]]
                    linhas_formatadas.append(r)
                elif fase == 'Final':
                    range_celulas = 'Final!C4'
                    r = [player[1]]
                    linhas_formatadas.append(r)
                break
        if not v:
            linhas_formatadas.append(r)

    return [range_celulas, linhas_formatadas]

class Mesa(list):
    """
    Representa uma mesa de jogo mantendo total compatibilidade com listas (list[str]).
    Permite acesso aos metadados da mesa (nome e numero).
    """
    def __init__(self, players, nome="", numero=0):
        super().__init__(players)
        self.nome = nome
        self.numero = numero

    def __getitem__(self, item):
        if isinstance(item, str):
            if item == "nome": return self.nome
            if item == "numero": return self.numero
            if item == "jogadores": return list(self)
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, key, default=None):
        if key == "nome": return self.nome
        if key == "numero": return self.numero
        if key == "jogadores": return list(self)
        return default

def _col_idx_to_a1(col_idx):
    if col_idx < 26:
        return chr(ord('A') + col_idx)
    return f"{chr(ord('A') + col_idx // 26 - 1)}{chr(ord('A') + col_idx % 26)}"

def _find_cell_by_text(sheet, planilha_id, search_range, target_text):
    """
    Busca uma célula cujo conteúdo textual corresponda ao target_text dentro de search_range.
    Retorna a coordenada no formato 'Aba!ColLinha' (ex: 'Partidas!N4') ou None.
    """
    try:
        r = sheet.values().get(spreadsheetId=planilha_id, range=search_range).execute()
        values = r.get('values', [])
        if not values:
            return None

        sheet_name, cell_range = search_range.split('!')
        start_col_str = re.search(r'([A-Z]+)', cell_range).group(1)
        start_row = int(re.search(r'(\d+)', cell_range).group(1))

        start_col_idx = 0
        for char in start_col_str:
            start_col_idx = start_col_idx * 26 + (ord(char) - ord('A') + 1)
        start_col_idx -= 1

        target_clean = target_text.strip().lower()

        # 1ª tentativa: correspondência exata
        for r_offset, row in enumerate(values):
            current_row = start_row + r_offset
            for c_offset, val in enumerate(row):
                val_clean = str(val).strip().lower()
                if val_clean == target_clean:
                    col_letter = _col_idx_to_a1(start_col_idx + c_offset)
                    return f"{sheet_name}!{col_letter}{current_row}"

        # 2ª tentativa: correspondência de palavra inteira
        for r_offset, row in enumerate(values):
            current_row = start_row + r_offset
            for c_offset, val in enumerate(row):
                val_clean = str(val).strip().lower()
                if val_clean and re.search(rf'(?<!\w){re.escape(target_clean)}(?!\w)', val_clean):
                    col_letter = _col_idx_to_a1(start_col_idx + c_offset)
                    return f"{sheet_name}!{col_letter}{current_row}"

    except Exception as err:
        print(f"Erro ao buscar célula por texto: {err}")

    return None

def _fallback_range(fase, numero, mesa_info):
    m_num = getattr(mesa_info, 'numero', None)
    if m_num is None and isinstance(mesa_info, dict):
        m_num = mesa_info.get('numero', 1)
    if m_num is None:
        m_num = 1

    m_nome = getattr(mesa_info, 'nome', None)
    if not m_nome and isinstance(mesa_info, dict):
        m_nome = mesa_info.get('nome', '')

    if fase == 'Classificatória':
        col = 'N' if str(numero) == '1' else 'V'
        return f'Partidas!{col}{3 + m_num}'
    elif fase == 'Semifinais':
        if 'A' in m_nome or m_num == 1: return 'Partidas!N17'
        elif 'B' in m_nome or m_num == 2: return 'Partidas!N18'
        elif 'C' in m_nome or m_num == 3: return 'Partidas!V17'
        elif 'D' in m_nome or m_num == 4: return 'Partidas!V18'
        return f'Partidas!N{16 + m_num}'
    elif fase == 'Final':
        return 'Partidas!N20'
    return 'Partidas!N4'

def formatacao_link_log(mesas, resultados, logs, fase, numero, sheet=None, planilha_id=None):
    link = f'https://tenhou.net/0/?log={logs[0]}&tw=0'
    jogadores_log = {str(player[0]).strip().lower() for player in resultados}

    # 1. Localiza a mesa correta comparando exatamente os 4 jogadores do log com os da mesa
    mesa_encontrada = None
    for mesa in mesas:
        mesa_jogadores = {str(p).strip().lower() for p in mesa}
        if len(mesa_jogadores) == 4 and mesa_jogadores == jogadores_log:
            mesa_encontrada = mesa
            break

    # Se não houver match exato dos 4 jogadores, não insere nada (barreira para logs não correlacionados)
    if not mesa_encontrada:
        print("Aviso: Nenhuma mesa com match exato dos 4 jogadores encontrada para:", jogadores_log)
        return [None, []]

    # 2. Define o texto que já deve estar na planilha
    if fase == 'Classificatória':
        m_num = getattr(mesa_encontrada, 'numero', None)
        if m_num is None and isinstance(mesa_encontrada, dict):
            m_num = mesa_encontrada.get('numero')
        if m_num is None:
            m_num = mesas.index(mesa_encontrada) + 1 if mesa_encontrada in mesas else 1
        texto_alvo = f'Rodada {numero} - Mesa {m_num}'
    elif fase == 'Semifinais':
        m_nome = getattr(mesa_encontrada, 'nome', None)
        if not m_nome and isinstance(mesa_encontrada, dict):
            m_nome = mesa_encontrada.get('nome')
        if not m_nome:
            idx = mesas.index(mesa_encontrada) if mesa_encontrada in mesas else 0
            d = {0: 'A', 1: 'B', 2: 'C', 3: 'D'}
            m_nome = f'Mesa {d.get(idx, "A")}'
        texto_alvo = m_nome
    elif fase == 'Final':
        texto_alvo = 'Final'
    else:
        texto_alvo = f'Rodada {numero}'

    texto_formula = f'=HIPERLINK("{link}","{texto_alvo}")'

    # 3. Localiza dinamicamente a célula pelo texto existente na aba Partidas
    range_celula = None
    if sheet is not None and planilha_id:
        range_celula = _find_cell_by_text(sheet, planilha_id, 'Partidas!M1:Z60', texto_alvo)

    # Fallback se a busca dinâmica não encontrar
    if not range_celula:
        range_celula = _fallback_range(fase, numero, mesa_encontrada)

    return [range_celula, [[texto_formula]]]
        
def set_torneio(planilha_id):
    with open('SetedTorneio.json', 'w') as f:
        arq = {'planilha_id' : planilha_id}
        json.dump(arq, f)

def set_rodada(fase, rodada):
    with open('SetedRodada.json', 'w') as f:
        fase = fase.capitalize()
        if fase == 'Classificatoria': fase = 'Classificatória'
        arq = {'fase': fase, 'rodada' : rodada}
        json.dump(arq, f)

def CreateService():
    creds = None
    tokens_file = "tokens.json"

    # 1. Carrega do arquivo unificado tokens.json se ele existir
    if os.path.exists(tokens_file):
        with open(tokens_file, "r", encoding="utf-8") as f:
            tokens_data = json.load(f)

        google_token = tokens_data.get("google_token")
        google_creds = tokens_data.get("google_credentials")

        if google_token:
            creds = Credentials.from_authorized_user_info(google_token, SCOPES)

        if not creds or not creds.valid:
            refreshed = False
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    refreshed = True
                except Exception as e:
                    print(f"Token expirado não pôde ser atualizado automaticamente: {e}")
                    creds = None

            if not refreshed:
                if google_creds:
                    flow = InstalledAppFlow.from_client_config(google_creds, SCOPES)
                elif os.path.exists("credentials.json"):
                    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                else:
                    raise FileNotFoundError(
                        "Credenciais do Google não encontradas em 'tokens.json' nem em 'credentials.json'."
                    )
                creds = flow.run_local_server(port=0)

        tokens_data["google_token"] = json.loads(creds.to_json())
        with open(tokens_file, "w", encoding="utf-8") as f:
            json.dump(tokens_data, f, indent=4, ensure_ascii=False)

        return creds

    # 2. Fallback para arquivos individuais legados
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except Exception:
                creds = None
        if not refreshed:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

    with open("token.json", "w") as token:
        token.write(creds.to_json())

    return creds

def _resolve_torneio_settings(planilha_id=None, fase=None, numero=None, guild_id="default"):
    if planilha_id is None or fase is None or numero is None:
        settings = db.get_guild_settings_sync(guild_id)
        if planilha_id is None:
            planilha_id = settings.get("planilha_id", "")
        if fase is None:
            fase = settings.get("fase", "Classificatória")
        if numero is None:
            numero = settings.get("rodada", "1")

    if not planilha_id and os.path.exists("SetedTorneio.json"):
        try:
            with open("SetedTorneio.json", "r", encoding="utf-8") as f:
                planilha_id = json.load(f).get("planilha_id", "")
        except Exception:
            pass

    if (not fase or not numero) and os.path.exists("SetedRodada.json"):
        try:
            with open("SetedRodada.json", "r", encoding="utf-8") as f:
                d = json.load(f)
                fase = fase or d.get("fase", "Classificatória")
                numero = numero or d.get("rodada", "1")
        except Exception:
            pass

    return planilha_id, fase or "Classificatória", str(numero or "1")

def doc(logs, planilha_id=None, fase=None, numero=None, guild_id="default"):
    planilha_id, fase, numero = _resolve_torneio_settings(planilha_id, fase, numero, guild_id)
    if not planilha_id:
        return -2

    players = result(logs)
    range_planilha = f'{fase}!A4:T'

    creds = CreateService()

    tabela = None

    try:
        service = build("sheets", "v4", credentials=creds)

        sheet = service.spreadsheets()
        r = sheet.values().get(spreadsheetId=planilha_id, range=range_planilha).execute()
        tabela = r['values']

    except HttpError as err:
        print(err)
        return -2
    
    try:
        f = formatacao(players, fase, numero, tabela)
        sheet.values().update(spreadsheetId=planilha_id, range=f[0], valueInputOption='USER_ENTERED', body={'values': f[1]}).execute()

    except HttpError as err:
        print(err)
        return -1
    
    try:
        mesas = GetPLayerListBySheet(planilha_id, fase, numero, guild_id)
        f = formatacao_link_log(mesas, players, logs, fase, numero, sheet=sheet, planilha_id=planilha_id)
        if f and f[0]:
            sheet.values().update(spreadsheetId=planilha_id, range=f[0], valueInputOption='USER_ENTERED', body={'values': f[1]}).execute()

    except HttpError as err:
        print(err)
        return -1

    return 1

def GetPLayerListBySheet(planilha_id=None, fase=None, numero=None, guild_id="default"):
    planilha_id, fase, numero = _resolve_torneio_settings(planilha_id, fase, numero, guild_id)
    if not planilha_id:
        return -2

    creds = CreateService()
    tabela = None

    if fase == 'Classificatória':
        range_planilha = 'Partidas!A4:K100'
        try:
            service = build("sheets", "v4", credentials=creds)
            sheet = service.spreadsheets()
            sheet.values().update(spreadsheetId=planilha_id, range='Partidas!G1', valueInputOption='USER_ENTERED', body={'values': [[numero]]}).execute()

        except HttpError as err:
            print(err)
            return -1
        
        try:
            r = sheet.values().get(spreadsheetId=planilha_id, range=range_planilha).execute()
            tabela = r.get('values', [])
            tabela = list(filter(None, tabela))

            mesas = []

            for i, coluna in enumerate(tabela):
                if len(coluna) > 2 and 'Mesa' in coluna[2]:
                    players = []
                    for e in range(1, 5):
                        if i + e < len(tabela) and len(tabela[i+e]) > 2 and tabela[i+e][2] != '-':
                            players.append(tabela[i+e][2])
                    if players:
                        m_match = re.search(r'\d+', coluna[2])
                        m_num = int(m_match.group()) if m_match else len(mesas) + 1
                        mesas.append(Mesa(players, nome=f"Mesa {m_num}", numero=m_num))

                if len(coluna) > 10 and 'Mesa' in coluna[10]:
                    players = []
                    for e in range(1, 5):
                        if i + e < len(tabela) and len(tabela[i+e]) > 10 and tabela[i+e][10] != '-':
                            players.append(tabela[i+e][10])
                    if players:
                        m_match = re.search(r'\d+', coluna[10])
                        m_num = int(m_match.group()) if m_match else len(mesas) + 1
                        mesas.append(Mesa(players, nome=f"Mesa {m_num}", numero=m_num))

            return mesas
                
        except HttpError as err:
            print(err)
            return -2

    elif fase in ("Semifinais", "Final"):
        # Lê apenas colunas A e B para ignorar qualquer poluição nas colunas laterais (C até Z)
        range_planilha = f'{fase}!A1:B100'
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        try:
            r = sheet.values().get(spreadsheetId=planilha_id, range=range_planilha).execute()
            tabela = r.get('values', [])

            mesas = []
            mesa_atual = None
            players_atual = []

            for row in tabela:
                col_a = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ''
                col_b = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''

                # Detecta início de uma nova mesa (ex: 'Semifinal - Mesa 1', 'Mesa A', 'Final')
                is_header = False
                nome_mesa = ""
                if fase == 'Final' and 'final' in col_a.lower():
                    is_header = True
                    nome_mesa = 'Final'
                elif fase == 'Semifinais' and ('mesa' in col_a.lower() or 'semifinal' in col_a.lower()):
                    is_header = True
                    match = re.search(r'Mesa\s+([A-Za-z0-9]+)', col_a, re.IGNORECASE)
                    nome_mesa = f'Mesa {match.group(1)}' if match else f'Mesa {chr(ord("A") + len(mesas))}'

                if is_header:
                    if mesa_atual and players_atual:
                        m_num = len(mesas) + 1
                        mesas.append(Mesa(players_atual, nome=mesa_atual, numero=m_num))
                    mesa_atual = nome_mesa
                    players_atual = []
                    continue

                # Coleta jogador se a coluna A for 1, 2, 3 ou 4 e coluna B for um jogador válido
                if mesa_atual and col_a in ('1', '2', '3', '4'):
                    if col_b and col_b != '-' and col_b.lower() != 'jogador':
                        players_atual.append(col_b)
                        if len(players_atual) == 4:
                            m_num = len(mesas) + 1
                            mesas.append(Mesa(players_atual, nome=mesa_atual, numero=m_num))
                            mesa_atual = None
                            players_atual = []

            if mesa_atual and players_atual:
                m_num = len(mesas) + 1
                mesas.append(Mesa(players_atual, nome=mesa_atual, numero=m_num))

            return mesas

        except HttpError as err:
            print(err)
            return -2      
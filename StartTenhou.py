import urllib.parse
import random
import asyncio
import aiohttp
import discord

endpoint_chat = "https://tenhou.net/cs/edit/cmd_chat.cgi"
endpoint_start = "https://tenhou.net/cs/edit/cmd_start.cgi"

def filtro(lista):
    return lista != ['OK']

def create_header(content_length, id_torneio):
    HEADERS = {
        'Host': 'tenhou.net',
        'Content-Length': f'{content_length}',
        'Cache-Control': 'no-cache',
        'Sec-Ch-Ua': '"Not(A:Brand";v="24", "Chromium";v="122"',
        'Pragma': 'no-cache',
        'Sec-Ch-Ua-Mobile': '?0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.112 Safari/537.36',
        'Content-Type': 'text/plain;charset=UTF-8',
        'If-Modified-Since': 'Thu, 01 Jun 1970 00:00:00 GMT',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Accept': '*/*',
        'Origin': 'https://tenhou.net',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': f'https://tenhou.net/cs/edit/?{id_torneio}',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Priority': 'u=1, i',
        'Connection': 'close',
    }
    return HEADERS

def decodeString(r):
    string = r.decode('utf-8')
    string2 = urllib.parse.unquote(string)
    string3 = string2.replace('\r', '')
    string4 = string3.split('\n')
    string5 = list(filter(None, string4))
    return string5

async def send_chat(id_torneio, color, chat, session=None):
    """Envia uma mensagem de chat para o lobby do Tenhou."""
    data_chat = f'L={id_torneio}&COLOR={color}&HIDDEN=0&CSLOG=0&CHAT={chat}'
    header = create_header(len(data_chat), id_torneio)

    if session is None:
        async with aiohttp.ClientSession() as own_session:
            async with own_session.post(endpoint_chat, headers=header, data=data_chat) as response:
                return await response.content.read()
    else:
        async with session.post(endpoint_chat, headers=header, data=data_chat) as response:
            return await response.content.read()

async def start_game(id_torneio, playersD, v_random, session=None):
    """Envia o comando de início de partida para uma mesa no Tenhou."""
    if v_random:
        random.shuffle(playersD)

    TO = f'{playersD[0]}%0A{playersD[1]}%0A{playersD[2]}%0A{playersD[3]}'
    data_start = f'L={id_torneio}&R2=000b&M={TO}&RND=default&WG=1&PW='
    header = create_header(len(data_start), id_torneio)

    async def _execute(s):
        async with s.post(endpoint_start, headers=header, data=data_start) as response:
            r = await response.content.read()
            string = decodeString(r)
            if string and string[0] == 'MEMBER NOT FOUND':
                color = 'FA0019'  # Vermelho
                TO2 = f'{playersD[0]},{playersD[1]},{playersD[2]},{playersD[3]}'
                data_chat = f'L={id_torneio}&COLOR={color}&HIDDEN=0&CSLOG=0&TO={TO2}&CHAT=Problema ao iniciar a partida'
                header2 = create_header(len(data_chat), id_torneio)
                async with s.post(endpoint_chat, data=data_chat, headers=header2) as response2:
                    await response2.content.read()
            return string

    if session is None:
        async with aiohttp.ClientSession() as own_session:
            return await _execute(own_session)
    else:
        return await _execute(session)

async def start_torneio(id_torneio, playersList, tempo, v_random, ctx):
    """
    Executa a contagem regressiva sincronizada com o Tenhou e Discord,
    iniciando as partidas no final do tempo com precisão de timestamp.
    """
    color = 'FF5500'  # Laranja
    tempo = max(3, min(int(tempo), 600))

    # Prepara lista de jogadores encodados para URL
    pld = [[urllib.parse.quote(player) for player in players] for players in playersList]

    # Tabela de alertas pré-definidos (segundos restantes, texto)
    alertas = [
        (300, 'Partida vai iniciar em 5 minutos'),
        (180, 'Partida vai iniciar em 3 minutos'),
        (60,  'Partida vai iniciar em 1 minuto'),
        (10,  'Partida vai iniciar em 10 segundos'),
        (3,   'Partida vai iniciar em 3 segundos')
    ]

    async with aiohttp.ClientSession() as session:
        async def broadcast(mensagem):
            """Dispara a mensagem em paralelo para Tenhou e Discord sem acumular latência."""
            await asyncio.gather(
                send_chat(id_torneio, color, mensagem, session=session),
                ctx.send(mensagem),
                return_exceptions=True
            )

        loop = asyncio.get_running_loop()
        target_time = loop.time() + tempo

        # Aviso inicial no Tenhou se não coincidir exatamente com os alertas padrão
        if tempo not in (300, 180, 60, 10, 3):
            if tempo < 60:
                chat_inicial = f'Partida vai iniciar em {tempo} segundos'
            else:
                m = tempo // 60
                s = tempo % 60
                chat_inicial = f'Partida vai iniciar em {m} Minutos e {s} Segundos'
            await send_chat(id_torneio, color, chat_inicial, session=session)

        try:
            # Itera pelos alertas principais esperando pelo tempo alvo preciso
            for segundos_alerta, texto_alerta in alertas:
                if tempo >= segundos_alerta:
                    espera = (target_time - segundos_alerta) - loop.time()
                    if espera > 0:
                        await asyncio.sleep(espera)
                    await broadcast(texto_alerta)

            # Contagem final segundo a segundo (3, 2, 1) no chat do Tenhou
            for contagem in (3, 2, 1):
                espera = (target_time - contagem) - loop.time()
                if espera > 0:
                    await asyncio.sleep(espera)
                await send_chat(id_torneio, color, str(contagem), session=session)

            # Momento final (0s): partida iniciada
            espera_final = target_time - loop.time()
            if espera_final > 0:
                await asyncio.sleep(espera_final)

            await broadcast('Iniciando Partida')

            # Disparo concorrente de todas as mesas
            tasks = [start_game(id_torneio, players, v_random, session=session) for players in pld]
            results = await asyncio.gather(*tasks)
            return results

        except asyncio.CancelledError:
            # Notificação caso a tarefa seja interrompida
            await send_chat(id_torneio, 'FA0019', 'Início da partida cancelado', session=session)
            raise
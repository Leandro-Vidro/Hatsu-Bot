import discord
from discord.ext import commands
import json
import os
import database as db
from torneio import doc, GetPLayerListBySheet
from StartTenhou import start_torneio, filtro

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='h!', intents=intents)

@bot.event
async def on_ready():
    await db.init_db()
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):

    if message.author == bot.user:
        return

    if not message.guild:
        await bot.process_commands(message)
        return

    msg = message.content    
    guild_id = str(message.guild.id)
    settings = await db.get_guild_settings(guild_id)
    log_channel_id = settings.get('log_channel_id', '')

    # Verifica se a mensagem veio do canal configurado para logs no servidor
    if log_channel_id and str(message.channel.id) == log_channel_id:
        if 'tenhou.net/' in msg and 'log=' in msg and settings['log_on']:
            log = ''
            texto = msg.split('log=')
            for separado in texto:
                if 'gm' in separado:
                    txt = separado.split('&')
                    log = txt[0]
            logs = []
            logs.append(log)

            if not settings['planilha_id']:
                await message.reply("A planilha do torneio ainda não foi configurada! Use h!SetTorneio <id_da_planilha>.")
            else:
                v = doc(logs, settings['planilha_id'], settings['fase'], settings['rodada'], guild_id)
                if v == -1: await message.reply("Não foi possivel ler a planilha")
                elif v == -2: await message.reply("Não foi possivel adicionar a planilha")
                elif v == 1: await message.add_reaction("✅")

    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def SetGetLog(ctx, canal: discord.TextChannel = None):
    if not ctx.guild:
        await ctx.reply("Este comando só pode ser usado em um servidor.")
        return

    if canal is None:
        canal = ctx.channel

    guild_id = str(ctx.guild.id)
    await db.set_guild_log_channel(guild_id, canal.id)
    await ctx.reply(f"Canal de coleta de logs configurado para {canal.mention} (`{canal.id}`)!")

@bot.command()
@commands.has_permissions(administrator=True)
async def SetTorneio(ctx, arg):
    if not ctx.guild:
        await ctx.reply("Este comando só pode ser usado em um servidor.")
        return
    guild_id = str(ctx.guild.id)
    await db.set_guild_torneio(guild_id, arg)
    await ctx.message.add_reaction("✅")

@bot.command()
@commands.has_permissions(administrator=True)
async def SetRodada(ctx, arg1, arg2):
    if not ctx.guild:
        await ctx.reply("Este comando só pode ser usado em um servidor.")
        return
    guild_id = str(ctx.guild.id)
    await db.set_guild_rodada(guild_id, arg1, arg2)
    await ctx.message.add_reaction("✅")

@bot.command()
@commands.has_permissions(administrator=True)
async def GetLog(ctx, arg1):
    if not ctx.guild:
        await ctx.reply("Este comando só pode ser usado em um servidor.")
        return
    guild_id = str(ctx.guild.id)
    settings = await db.get_guild_settings(guild_id)
    log_on = settings['log_on']
    arg = arg1.lower()

    if not log_on and arg == 'on': 
        await db.set_guild_log_on(guild_id, True)
        await ctx.reply("GetLog ligado neste servidor")
    elif not log_on and arg == 'off':
        await ctx.reply("GetLog já esta desligado")
    elif log_on and arg == 'on':
        await ctx.reply("GetLog já esta ligado")
    elif log_on and arg == 'off': 
        await db.set_guild_log_on(guild_id, False)
        await ctx.reply("GetLog desligado neste servidor")
    else:
        await ctx.reply("Argumento inválido. Use 'on' ou 'off'.")

@bot.command()
@commands.has_permissions(administrator=True)
async def StartMatch(ctx, arg1, arg2, arg3, arg4 = None):
    v = False
    if arg4 == None:
        v = False
    playerlist = []
    s1 = arg1.split('/')
    for string in s1:
        s2 = string.split(',')
        playerlist.append(s2)
    if arg4 == 'on': v = True
    elif arg4 == 'off': v = False
    tempo = int(arg3)
    if tempo < 3:
        tempo = 3
    if tempo <= 600:
        if tempo < 60:
            chat = f'Partida vai iniciar em {tempo} segundos'
        else:
            min = tempo // 60
            seg = tempo % 60
            chat = f'Partida vai iniciar em {min} Minutos e {seg} Segundos'
        await ctx.reply(chat)
        r = await start_torneio(arg2, playerlist, int(arg3), v, ctx)
        r = list(filter(filtro, r))
        mnf = ''
        for mesa in r:
            for player in mesa:
                if player != 'MEMBER NOT FOUND':
                    mnf = mnf + '\n' + player
        chat_discord = 'Jogadores fora do Lobby:'+mnf
        if mnf != '':
            await ctx.send(chat_discord)
        else: await ctx.message.add_reaction("✅")
    else: await ctx.reply('Tempo inválido!')

@bot.command()
@commands.has_permissions(administrator=True)
async def StartBySheet(ctx, arg1, arg2, arg3 = None):
    if not ctx.guild:
        await ctx.reply("Este comando só pode ser usado em um servidor.")
        return
    guild_id = str(ctx.guild.id)
    settings = await db.get_guild_settings(guild_id)
    if not settings['planilha_id']:
        await ctx.reply("Planilha não configurada neste servidor. Use h!SetTorneio <id_da_planilha>.")
        return

    v = False
    if arg3 == 'on': v = True
    elif arg3 == 'off': v = False

    mesas = GetPLayerListBySheet(settings['planilha_id'], settings['fase'], settings['rodada'], guild_id)
    if mesas in (-1, -2) or not mesas:
        await ctx.reply("Não foi possível ler as mesas da planilha.")
        return

    playerlist = mesas
    tempo = int(arg2)
    if tempo < 3:
        tempo = 3
    if tempo <= 600:
        if tempo < 60:
            chat = f'Partida vai iniciar em {tempo} segundos'
        else:
            min = tempo // 60
            seg = tempo % 60
            chat = f'Partida vai iniciar em {min} Minutos e {seg} Segundos'
        await ctx.reply(chat)
        r = await start_torneio(arg1, playerlist, int(arg2), v, ctx)
        r = list(filter(filtro, r))
        mnf = ''
        for mesa in r:
            for player in mesa:
                if player != 'MEMBER NOT FOUND':
                    mnf = mnf + '\n' + player
        chat_discord = 'Jogadores fora do Lobby:'+mnf
        if mnf != '':
            await ctx.send(chat_discord)
        else: await ctx.message.add_reaction("✅")
    else: await ctx.reply('Tempo inválido!')

@bot.command()
@commands.has_permissions(administrator=True)
async def Seted(ctx):
    if not ctx.guild:
        await ctx.reply("Este comando só pode ser usado em um servidor.")
        return
    guild_id = str(ctx.guild.id)
    settings = await db.get_guild_settings(guild_id)

    l = 'Ligado' if settings['log_on'] else 'Desligado'
    planilha_id = settings['planilha_id'] if settings['planilha_id'] else 'Não definida'
    fase = settings['fase'] if settings['fase'] else 'Não definida'
    numero2 = settings['rodada'] if settings['rodada'] else 'Não definida'
    canal_id = settings.get('log_channel_id', '')
    canal_texto = f"<#{canal_id}>" if canal_id else 'Não definido'

    texto = (
        f'**Servidor:** {ctx.guild.name}\n'
        f'**GetLog:** {l}\n'
        f'**Canal de Logs:** {canal_texto}\n'
        f'**Planilha:** {planilha_id}\n'
        f'**Fase:** {fase.capitalize()} **Rodada:** {numero2}'
    )
    await ctx.reply(texto)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("Você precisa ter permissão de administrador para usar este comando.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.reply(f"Canal `{error.argument}` não encontrado! Use a menção `#canal` ou o ID numérico do canal.")
    else:
        raise error

def get_discord_token():
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("discord_token")
    elif os.path.exists("tokend.json"):
        with open("tokend.json", "r", encoding="utf-8") as f:
            return json.load(f).get("token")
    return None

if __name__ == '__main__':
    token = get_discord_token()
    if not token:
        raise FileNotFoundError(
            "Token do Discord não encontrado! Configure o arquivo 'tokens.json' com base em 'tokens.example.json'."
        )
    bot.run(token)
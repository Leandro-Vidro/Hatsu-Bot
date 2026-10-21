import aiosqlite
import sqlite3
import os
import json

DB_PATH = "hatsu_bot.db"

async def init_db():
    """Inicializa o banco de dados e cria a tabela de configurações se não existir."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                log_on INTEGER NOT NULL DEFAULT 0,
                planilha_id TEXT NOT NULL DEFAULT '',
                fase TEXT NOT NULL DEFAULT 'Classificatória',
                rodada TEXT NOT NULL DEFAULT '1',
                log_channel_id TEXT NOT NULL DEFAULT ''
            )
        """)
        # Adiciona a coluna se o banco já existia de uma versão anterior
        try:
            await db.execute("ALTER TABLE guild_settings ADD COLUMN log_channel_id TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass

        # Tabela de vínculo de contas de jogos com usuários do Discord
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_accounts (
                discord_id TEXT PRIMARY KEY,
                tenhou_nick TEXT NOT NULL DEFAULT '',
                riichi_city_id TEXT NOT NULL DEFAULT '',
                riichi_city_nick TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_tenhou ON user_accounts(tenhou_nick)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_rc_id ON user_accounts(riichi_city_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_rc_nick ON user_accounts(riichi_city_nick)")

        await db.commit()
    
    await _migrate_legacy_settings()

async def _migrate_legacy_settings():
    """Migra dados de SetedTorneio.json e SetedRodada.json para o banco se existirem."""
    legacy_planilha = ""
    legacy_fase = "Classificatória"
    legacy_rodada = "1"

    if os.path.exists("SetedTorneio.json"):
        try:
            with open("SetedTorneio.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                legacy_planilha = data.get("planilha_id", "")
        except Exception:
            pass

    if os.path.exists("SetedRodada.json"):
        try:
            with open("SetedRodada.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                legacy_fase = data.get("fase", "Classificatória")
                legacy_rodada = data.get("rodada", "1")
        except Exception:
            pass

    if legacy_planilha:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO guild_settings (guild_id, log_on, planilha_id, fase, rodada, log_channel_id)
                VALUES (?, ?, ?, ?, ?, '')
            """, ("default", 0, legacy_planilha, legacy_fase, legacy_rodada))
            await db.commit()

async def get_guild_settings(guild_id: str | int) -> dict:
    """Retorna as configurações do servidor. Se não existir, cria com os valores padrão."""
    guild_id = str(guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                keys = row.keys()
                return {
                    "guild_id": row["guild_id"],
                    "log_on": bool(row["log_on"]),
                    "planilha_id": row["planilha_id"],
                    "fase": row["fase"],
                    "rodada": row["rodada"],
                    "log_channel_id": row["log_channel_id"] if "log_channel_id" in keys else ""
                }
            
            default_fase = "Classificatória"
            default_rodada = "1"
            await db.execute("""
                INSERT INTO guild_settings (guild_id, log_on, planilha_id, fase, rodada, log_channel_id)
                VALUES (?, 0, '', ?, ?, '')
            """, (guild_id, default_fase, default_rodada))
            await db.commit()
            return {
                "guild_id": guild_id,
                "log_on": False,
                "planilha_id": "",
                "fase": default_fase,
                "rodada": default_rodada,
                "log_channel_id": ""
            }

async def set_guild_torneio(guild_id: str | int, planilha_id: str):
    """Atualiza o ID da planilha do servidor."""
    guild_id = str(guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, planilha_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET planilha_id = excluded.planilha_id
        """, (guild_id, planilha_id))
        await db.commit()

async def set_guild_rodada(guild_id: str | int, fase: str, rodada: str):
    """Atualiza a fase e a rodada do servidor."""
    guild_id = str(guild_id)
    fase = fase.capitalize()
    if fase == 'Classificatoria':
        fase = 'Classificatória'
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, fase, rodada)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET fase = excluded.fase, rodada = excluded.rodada
        """, (guild_id, fase, str(rodada)))
        await db.commit()

async def set_guild_log_on(guild_id: str | int, status: bool):
    """Atualiza o status do GetLog do servidor."""
    guild_id = str(guild_id)
    val = 1 if status else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, log_on)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET log_on = excluded.log_on
        """, (guild_id, val))
        await db.commit()

async def set_guild_log_channel(guild_id: str | int, channel_id: str | int):
    """Atualiza o canal configurado para receber os logs no servidor."""
    guild_id = str(guild_id)
    channel_id = str(channel_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, log_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = excluded.log_channel_id
        """, (guild_id, channel_id))
        await db.commit()

def get_guild_settings_sync(guild_id: str | int = "default") -> dict:
    """Versão síncrona para consultas fora do loop assíncrono."""
    guild_id = str(guild_id)
    if not os.path.exists(DB_PATH):
        return {
            "guild_id": guild_id,
            "log_on": False,
            "planilha_id": "",
            "fase": "Classificatória",
            "rodada": "1",
            "log_channel_id": ""
        }
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
        row = cur.fetchone()
        if row:
            keys = row.keys()
            return {
                "guild_id": row["guild_id"],
                "log_on": bool(row["log_on"]),
                "planilha_id": row["planilha_id"],
                "fase": row["fase"],
                "rodada": row["rodada"],
                "log_channel_id": row["log_channel_id"] if "log_channel_id" in keys else ""
            }
        return {
            "guild_id": guild_id,
            "log_on": False,
            "planilha_id": "",
            "fase": "Classificatória",
            "rodada": "1",
            "log_channel_id": ""
        }

# ==========================================
# Gestão de Contas de Jogos (Tenhou / Riichi City)
# ==========================================

async def link_tenhou(discord_id: str | int, tenhou_nick: str) -> None:
    """Vincula ou atualiza o nick do Tenhou para um usuário do Discord."""
    discord_id = str(discord_id)
    tenhou_nick = str(tenhou_nick).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_accounts (discord_id, tenhou_nick, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id) DO UPDATE SET 
                tenhou_nick = excluded.tenhou_nick,
                updated_at = CURRENT_TIMESTAMP
        """, (discord_id, tenhou_nick))
        await db.commit()

async def link_riichi_city(discord_id: str | int, riichi_city_id: str | int, riichi_city_nick: str = "") -> None:
    """Vincula ou atualiza o ID e nick do Riichi City para um usuário do Discord."""
    discord_id = str(discord_id)
    riichi_city_id = str(riichi_city_id).strip()
    riichi_city_nick = str(riichi_city_nick).strip() if riichi_city_nick else ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_accounts (discord_id, riichi_city_id, riichi_city_nick, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id) DO UPDATE SET 
                riichi_city_id = excluded.riichi_city_id,
                riichi_city_nick = CASE WHEN excluded.riichi_city_nick != '' THEN excluded.riichi_city_nick ELSE user_accounts.riichi_city_nick END,
                updated_at = CURRENT_TIMESTAMP
        """, (discord_id, riichi_city_id, riichi_city_nick))
        await db.commit()

async def unlink_game_account(discord_id: str | int, game: str) -> bool:
    """
    Desvincula a conta de um jogo para um usuário do Discord.
    Argumento game: 'tenhou' ou 'riichi_city'.
    """
    discord_id = str(discord_id)
    game = game.lower().strip()
    async with aiosqlite.connect(DB_PATH) as db:
        if game == 'tenhou':
            await db.execute("UPDATE user_accounts SET tenhou_nick = '', updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?", (discord_id,))
        elif game in ('riichi_city', 'riichicity', 'rc', 'riichi'):
            await db.execute("UPDATE user_accounts SET riichi_city_id = '', riichi_city_nick = '', updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?", (discord_id,))
        else:
            return False
        await db.commit()
        return True

async def get_user_accounts(discord_id: str | int) -> dict | None:
    """Retorna as contas vinculadas a um ID do Discord ou None se não houver registro."""
    discord_id = str(discord_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_accounts WHERE discord_id = ?", (discord_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "discord_id": row["discord_id"],
                    "tenhou_nick": row["tenhou_nick"] or "",
                    "riichi_city_id": row["riichi_city_id"] or "",
                    "riichi_city_nick": row["riichi_city_nick"] or "",
                    "updated_at": row["updated_at"]
                }
            return None

async def get_discord_by_tenhou(tenhou_nick: str) -> str | None:
    """Busca o discord_id a partir do nick do Tenhou (case-insensitive)."""
    tenhou_nick = str(tenhou_nick).strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discord_id FROM user_accounts WHERE LOWER(tenhou_nick) = ? LIMIT 1", (tenhou_nick,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_discord_by_riichi_city(identifier: str | int) -> str | None:
    """Busca o discord_id a partir do ID ou nick do Riichi City (case-insensitive)."""
    ident = str(identifier).strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT discord_id FROM user_accounts 
            WHERE LOWER(riichi_city_id) = ? OR LOWER(riichi_city_nick) = ? 
            LIMIT 1
        """, (ident, ident)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

def get_user_accounts_sync(discord_id: str | int) -> dict | None:
    """Versão síncrona para consulta de contas de usuário."""
    discord_id = str(discord_id)
    if not os.path.exists(DB_PATH):
        return None
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_accounts WHERE discord_id = ?", (discord_id,))
        row = cur.fetchone()
        if row:
            return {
                "discord_id": row["discord_id"],
                "tenhou_nick": row["tenhou_nick"] or "",
                "riichi_city_id": row["riichi_city_id"] or "",
                "riichi_city_nick": row["riichi_city_nick"] or "",
                "updated_at": row["updated_at"]
            }
        return None

def get_discord_by_tenhou_sync(tenhou_nick: str) -> str | None:
    """Versão síncrona para buscar discord_id pelo nick do Tenhou."""
    tenhou_nick = str(tenhou_nick).strip().lower()
    if not os.path.exists(DB_PATH):
        return None
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT discord_id FROM user_accounts WHERE LOWER(tenhou_nick) = ? LIMIT 1", (tenhou_nick,))
        row = cur.fetchone()
        return row[0] if row else None

def get_discord_by_riichi_city_sync(identifier: str | int) -> str | None:
    """Versão síncrona para buscar discord_id pelo ID ou nick do Riichi City."""
    ident = str(identifier).strip().lower()
    if not os.path.exists(DB_PATH):
        return None
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT discord_id FROM user_accounts 
            WHERE LOWER(riichi_city_id) = ? OR LOWER(riichi_city_nick) = ? 
            LIMIT 1
        """, (ident, ident))
        row = cur.fetchone()
        return row[0] if row else None


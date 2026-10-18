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

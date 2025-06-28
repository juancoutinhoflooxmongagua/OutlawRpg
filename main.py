# main.py

# --- ADICIONE ESTAS DUAS LINHAS NO TOPO ---
from dotenv import load_dotenv

load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env

import discord
import os
from discord.ext import commands, tasks
from datetime import datetime

from config import TOKEN, STATUS_BOT, PREFIXO, REGEN_ENERGIA, ENERGIA_MAXIMA
from utils.game_logic import fichas_db, salvar_fichas, get_dynamic_stat

# --- INTENTS ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class OutlawBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIXO, intents=intents)

    async def setup_hook(self):
        # Carrega as cogs
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print(f"✅ Cog '{filename[:-3]}' carregada.")
                except Exception as e:
                    print(f"❌ Falha ao carregar a cog '{filename[:-3]}': {e}")

        # Sincroniza os comandos com o Discord
        try:
            synced = await self.tree.sync()
            print(f"🔄 {len(synced)} comandos sincronizados com sucesso.")
        except Exception as e:
            print(f"⚠️ Erro ao sincronizar comandos: {e}")

        # Inicia os loops de fundo
        self.background_tasks.start()

    async def on_ready(self):
        print(f"🚀 Bot conectado como {self.user.name} ({self.user.id})")
        print("------------------------------------------------------")
        await self.change_presence(activity=STATUS_BOT)

    # --- LOOP DE FUNDO PARA TAREFAS RECORRENTES ---
    @tasks.loop(minutes=1)
    async def background_tasks(self):
        """Executa tarefas de manutenção a cada minuto."""
        agora = datetime.now()
        mudanca_feita = False

        # Usar .copy() para evitar problemas ao modificar o dicionário durante a iteração
        for user_id, jogador in fichas_db.copy().items():
            # 1. Regeneração de Energia
            energia_atual = get_dynamic_stat(user_id, "energia")
            if energia_atual < ENERGIA_MAXIMA:
                jogador["energia"] = min(ENERGIA_MAXIMA, energia_atual + REGEN_ENERGIA)
                mudanca_feita = True

            # 2. Limpeza de Buffs Expirados
            if "buffs" in jogador and jogador["buffs"]:
                buffs_ativos = {
                    buff_id: buff_info
                    for buff_id, buff_info in jogador["buffs"].items()
                    if datetime.fromisoformat(buff_info["fim"]) > agora
                }
                if len(buffs_ativos) < len(jogador["buffs"]):
                    jogador["buffs"] = buffs_ativos
                    mudanca_feita = True

        if mudanca_feita:
            salvar_fichas()

    @background_tasks.before_loop
    async def before_background_tasks(self):
        await self.wait_until_ready()  # Espera o bot estar pronto


bot = OutlawBot()
bot.run(TOKEN)

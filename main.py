import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

from config import (
    TOKEN,
    PREFIXO,
    STATUS_BOT,
    FICHAS_DB_FILE,
    GIFS_DB_FILE,
    BOSS_DB_FILE,
)


class OutlawBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=PREFIXO, intents=intents)

        # Carregar dados na inicialização
        self.fichas_db = self.load_json(FICHAS_DB_FILE)
        self.gifs_db = self.load_json(GIFS_DB_FILE)
        self.boss_data = self.load_json(BOSS_DB_FILE)

    def load_json(self, filename):
        """Carrega um arquivo JSON de forma segura."""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return (
                {}
            )  # Retorna um dicionário vazio se o arquivo não existir ou for inválido

    def save_fichas(self):
        """Salva o banco de dados de fichas em um arquivo."""
        with open(FICHAS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.fichas_db, f, indent=4)

    def save_boss_data(self):
        """Salva os dados do chefe mundial em um arquivo."""
        with open(BOSS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.boss_data, f, indent=4)

    async def setup_hook(self):
        """Carrega as extensões (cogs) do bot."""
        cogs_dir = "cogs"
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                try:
                    await self.load_extension(f"{cogs_dir}.{filename[:-3]}")
                    print(f"✅ Cog '{filename[:-3]}' carregado.")
                except Exception as e:
                    print(f"❌ Falha ao carregar o cog '{filename[:-3]}': {e}")

    async def on_ready(self):
        print(f"🚀 Bot conectado como {self.user}!")
        print(f"ID do Bot: {self.user.id}")
        await self.change_presence(activity=STATUS_BOT)
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} comandos de barra sincronizados.")
        except Exception as e:
            print(f"❌ Falha ao sincronizar comandos: {e}")


if __name__ == "__main__":
    bot = OutlawBot()
    bot.run(TOKEN)
